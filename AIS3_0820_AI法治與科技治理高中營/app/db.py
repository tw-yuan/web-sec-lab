"""SQLite 儲存層（spec §4）。WAL 模式以支撐活動當天的併發寫入。

ASSUMPTION: 單一 uvicorn worker（見 Dockerfile），因此使用單一共享連線。
"""

from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import aiosqlite

log = logging.getLogger("ctf.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    token        TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(user_id),
    created_at   REAL NOT NULL,
    last_seen_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS solves (
    user_id      TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    solved_at    TEXT NOT NULL,
    method       TEXT,
    PRIMARY KEY (user_id, challenge_id)
);

CREATE TABLE IF NOT EXISTS scores (
    user_id      TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    points       INTEGER NOT NULL,
    solved_at    TEXT NOT NULL,
    PRIMARY KEY (user_id, challenge_id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT NOT NULL,
    challenge_id  TEXT NOT NULL,
    ts            TEXT NOT NULL,
    input_excerpt TEXT,
    verdict       TEXT,
    tokens_used   INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_attempts_user_ch ON attempts(user_id, challenge_id);

CREATE TABLE IF NOT EXISTS defense_submissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    system_prompt   TEXT NOT NULL,
    blocked_count   INTEGER NOT NULL,
    total_payloads  INTEGER NOT NULL,
    usability_pass  INTEGER NOT NULL DEFAULT 0,
    usability_total INTEGER NOT NULL DEFAULT 0,
    points          INTEGER NOT NULL DEFAULT 0,
    ts              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_def_user ON defense_submissions(user_id);

CREATE TABLE IF NOT EXISTS flag_submissions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        TEXT NOT NULL,
    challenge_id   TEXT NOT NULL,
    submitted      TEXT NOT NULL,
    correct        INTEGER NOT NULL,
    suspected_owner TEXT,
    ts             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hints_taken (
    user_id      TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    hint_index   INTEGER NOT NULL,
    ts           TEXT NOT NULL,
    PRIMARY KEY (user_id, challenge_id, hint_index)
);

CREATE TABLE IF NOT EXISTS xss_nonces (
    nonce        TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    created_at   REAL NOT NULL,
    used         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);

-- 學員解題過程中「完整」的每一輪 prompt 與模型回覆（教學復盤用）。
-- 與 attempts 分開：attempts 給統計/限流（只留 300 字摘要），這裡留全文。
-- role: 'user'（自由對話）/ 'document'（間接注入的文件）/ 'assistant'（模型回覆）。
CREATE TABLE IF NOT EXISTS prompt_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    session_id   TEXT,
    turn         INTEGER,
    role         TEXT NOT NULL,
    content      TEXT,
    verdict      TEXT,
    tokens_used  INTEGER DEFAULT 0,
    ts           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_promptlogs_user_ch ON prompt_logs(user_id, challenge_id);
CREATE INDEX IF NOT EXISTS idx_promptlogs_session ON prompt_logs(session_id, challenge_id);
"""

# token 用不易看錯的字母集（去掉 0/O/1/I/L）
_TOKEN_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_user_token() -> str:
    part = lambda n: "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(n))  # noqa: E731
    return f"{part(4)}-{part(4)}"


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(str(self.path))
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()
        log.info("SQLite 已就緒：%s", self.path)

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()
            self.conn = None

    @property
    def _c(self) -> aiosqlite.Connection:
        if self.conn is None:
            raise RuntimeError("Database 尚未 connect()")
        return self.conn

    # ---------------- users / sessions ----------------

    async def create_user(self, user_id: str, display_name: str, token: str) -> None:
        await self._c.execute(
            "INSERT OR IGNORE INTO users(user_id, display_name, token, created_at)"
            " VALUES (?,?,?,?)",
            (user_id, display_name, token, _now_iso()),
        )
        await self._c.commit()

    async def count_users(self) -> int:
        async with self._c.execute("SELECT COUNT(*) AS n FROM users") as cur:
            row = await cur.fetchone()
        return int(row["n"]) if row else 0

    async def all_user_ids(self) -> list[str]:
        async with self._c.execute("SELECT user_id FROM users") as cur:
            return [r["user_id"] for r in await cur.fetchall()]

    async def list_users(self) -> list[dict]:
        async with self._c.execute(
            "SELECT user_id, display_name, token, created_at FROM users ORDER BY user_id"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def user_by_token(self, token: str) -> dict | None:
        async with self._c.execute(
            "SELECT user_id, display_name FROM users WHERE token = ?", (token,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def set_display_name(self, user_id: str, name: str) -> None:
        await self._c.execute(
            "UPDATE users SET display_name = ? WHERE user_id = ?", (name, user_id)
        )
        await self._c.commit()

    async def create_session(self, user_id: str) -> str:
        sid = secrets.token_urlsafe(24)
        now = time.time()
        await self._c.execute(
            "INSERT INTO sessions(session_id, user_id, created_at, last_seen_at)"
            " VALUES (?,?,?,?)",
            (sid, user_id, now, now),
        )
        await self._c.commit()
        return sid

    async def session_user(self, session_id: str, ttl: int) -> dict | None:
        async with self._c.execute(
            "SELECT s.session_id, s.user_id, s.created_at, u.display_name"
            " FROM sessions s JOIN users u ON u.user_id = s.user_id"
            " WHERE s.session_id = ?",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        if time.time() - float(row["created_at"]) > ttl:
            await self._c.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await self._c.commit()
            return None
        await self._c.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        await self._c.commit()
        return dict(row)

    # ---------------- solves / scores ----------------

    async def record_solve(
        self, user_id: str, challenge_id: str, points: int, method: str
    ) -> bool:
        """回傳 True 表示這次是「首次」破關（用來決定要不要加分／回饋）。"""
        now = _now_iso()
        cur = await self._c.execute(
            "INSERT OR IGNORE INTO solves(user_id, challenge_id, solved_at, method)"
            " VALUES (?,?,?,?)",
            (user_id, challenge_id, now, method),
        )
        first = cur.rowcount > 0
        if first:
            await self._c.execute(
                "INSERT OR IGNORE INTO scores(user_id, challenge_id, points, solved_at)"
                " VALUES (?,?,?,?)",
                (user_id, challenge_id, points, now),
            )
        await self._c.commit()
        return first

    async def solved_map(self, user_id: str) -> dict[str, int]:
        async with self._c.execute(
            "SELECT s.challenge_id, COALESCE(sc.points, 0) AS points"
            " FROM solves s LEFT JOIN scores sc"
            " ON sc.user_id = s.user_id AND sc.challenge_id = s.challenge_id"
            " WHERE s.user_id = ?",
            (user_id,),
        ) as cur:
            return {r["challenge_id"]: int(r["points"]) for r in await cur.fetchall()}

    async def upsert_defense_score(self, user_id: str, points: int) -> None:
        """DEF 取歷次最佳分數。"""
        now = _now_iso()
        await self._c.execute(
            "INSERT INTO scores(user_id, challenge_id, points, solved_at) VALUES (?,'def',?,?)"
            " ON CONFLICT(user_id, challenge_id) DO UPDATE SET"
            "   points = MAX(points, excluded.points),"
            "   solved_at = CASE WHEN excluded.points > points THEN excluded.solved_at"
            "                    ELSE solved_at END",
            (user_id, points, now),
        )
        if points > 0:
            await self._c.execute(
                "INSERT OR IGNORE INTO solves(user_id, challenge_id, solved_at, method)"
                " VALUES (?,'def',?,'defense')",
                (user_id, now),
            )
        await self._c.commit()

    async def leaderboard(self) -> list[dict]:
        """回傳每位使用者的解題清單與「當初存下的分數」。

        總分**不在這裡算** —— 由 main.py 依 challenges.json 的當前分數重算，
        否則活動中途調整某題分數時，舊紀錄會停在舊分數（曾經出現總分超過滿分的 bug）。
        """
        async with self._c.execute(
            "SELECT u.user_id, u.display_name,"
            "       MAX(sc.solved_at) AS last_solved_at"
            " FROM users u LEFT JOIN scores sc ON sc.user_id = u.user_id"
            " GROUP BY u.user_id"
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
        async with self._c.execute(
            "SELECT s.user_id, s.challenge_id, COALESCE(sc.points, 0) AS points"
            " FROM solves s LEFT JOIN scores sc"
            "   ON sc.user_id = s.user_id AND sc.challenge_id = s.challenge_id"
            " ORDER BY s.solved_at"
        ) as cur:
            stored: dict[str, dict[str, int]] = {}
            for r in await cur.fetchall():
                stored.setdefault(r["user_id"], {})[r["challenge_id"]] = int(r["points"])
        for row in rows:
            row["stored"] = stored.get(row["user_id"], {})
            row["solved"] = list(row["stored"].keys())
        return rows

    # ---------------- attempts / 限流輔助 ----------------

    async def log_attempt(
        self,
        user_id: str,
        challenge_id: str,
        input_excerpt: str,
        verdict: str,
        tokens_used: int,
    ) -> None:
        await self._c.execute(
            "INSERT INTO attempts(user_id, challenge_id, ts, input_excerpt, verdict, tokens_used)"
            " VALUES (?,?,?,?,?,?)",
            (user_id, challenge_id, _now_iso(), input_excerpt[:300], verdict, tokens_used),
        )
        await self._c.commit()

    async def attempt_count(self, user_id: str, challenge_id: str) -> int:
        async with self._c.execute(
            "SELECT COUNT(*) AS n FROM attempts WHERE user_id = ? AND challenge_id = ?",
            (user_id, challenge_id),
        ) as cur:
            row = await cur.fetchone()
        return int(row["n"]) if row else 0

    async def attempts_by_challenge(self) -> dict[str, int]:
        async with self._c.execute(
            "SELECT challenge_id, COUNT(*) AS n FROM attempts GROUP BY challenge_id"
        ) as cur:
            return {r["challenge_id"]: int(r["n"]) for r in await cur.fetchall()}

    # ---------------- prompt 全文紀錄（教學復盤）----------------

    async def log_turn(
        self,
        user_id: str,
        challenge_id: str,
        session_id: str,
        *,
        user_role: str,          # 'user' 或 'document'
        user_content: str,
        assistant_content: str | None,
        verdict: str,
        tokens_used: int,
    ) -> None:
        """記錄一輪對話：學員這次送的完整輸入 + 模型的完整回覆。

        turn = 這場對話（同一 session、同一題）目前的輸入輪數 + 1，方便重建順序。
        assistant_content 為 None 表示這輪沒有模型回覆（輸入被擋 / 模型出錯）。
        """
        async with self._c.execute(
            "SELECT COUNT(*) AS n FROM prompt_logs"
            " WHERE session_id = ? AND challenge_id = ? AND role != 'assistant'",
            (session_id, challenge_id),
        ) as cur:
            row = await cur.fetchone()
        turn = (int(row["n"]) if row else 0) + 1
        now = _now_iso()
        await self._c.execute(
            "INSERT INTO prompt_logs"
            "(user_id, challenge_id, session_id, turn, role, content, verdict, tokens_used, ts)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (user_id, challenge_id, session_id, turn, user_role, user_content, verdict, 0, now),
        )
        if assistant_content is not None:
            await self._c.execute(
                "INSERT INTO prompt_logs"
                "(user_id, challenge_id, session_id, turn, role, content, verdict, tokens_used, ts)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (user_id, challenge_id, session_id, turn, "assistant",
                 assistant_content, verdict, tokens_used, now),
            )
        await self._c.commit()

    async def fetch_prompts(
        self, challenge_id: str | None, user_id: str | None, limit: int
    ) -> list[dict]:
        """取最近的 prompt 紀錄（可依題目 / 學員過濾）。回傳依時間新→舊。"""
        limit = max(1, min(2000, limit))
        sql = (
            "SELECT id, user_id, challenge_id, session_id, turn, role, content,"
            " verdict, tokens_used, ts FROM prompt_logs"
            " WHERE (? IS NULL OR challenge_id = ?) AND (? IS NULL OR user_id = ?)"
            " ORDER BY id DESC LIMIT ?"
        )
        async with self._c.execute(
            sql, (challenge_id, challenge_id, user_id, user_id, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def log_flag_submission(
        self,
        user_id: str,
        challenge_id: str,
        submitted: str,
        correct: bool,
        suspected_owner: str | None,
    ) -> None:
        await self._c.execute(
            "INSERT INTO flag_submissions"
            "(user_id, challenge_id, submitted, correct, suspected_owner, ts)"
            " VALUES (?,?,?,?,?,?)",
            (user_id, challenge_id, submitted[:200], int(correct), suspected_owner, _now_iso()),
        )
        await self._c.commit()

    async def suspicious_submissions(self) -> list[dict]:
        async with self._c.execute(
            "SELECT user_id, challenge_id, suspected_owner, ts FROM flag_submissions"
            " WHERE suspected_owner IS NOT NULL AND suspected_owner <> user_id"
            " ORDER BY ts DESC LIMIT 200"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def take_hint(self, user_id: str, challenge_id: str, idx: int) -> None:
        await self._c.execute(
            "INSERT OR IGNORE INTO hints_taken(user_id, challenge_id, hint_index, ts)"
            " VALUES (?,?,?,?)",
            (user_id, challenge_id, idx, _now_iso()),
        )
        await self._c.commit()

    async def hint_stats(self) -> list[dict]:
        async with self._c.execute(
            "SELECT challenge_id, hint_index, COUNT(*) AS n FROM hints_taken"
            " GROUP BY challenge_id, hint_index ORDER BY challenge_id, hint_index"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    # ---------------- DEF ----------------

    async def log_defense(
        self,
        user_id: str,
        system_prompt: str,
        blocked: int,
        total: int,
        usability_pass: int,
        usability_total: int,
        points: int,
    ) -> None:
        await self._c.execute(
            "INSERT INTO defense_submissions"
            "(user_id, system_prompt, blocked_count, total_payloads,"
            " usability_pass, usability_total, points, ts)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                user_id, system_prompt[:8000], blocked, total,
                usability_pass, usability_total, points, _now_iso(),
            ),
        )
        await self._c.commit()

    async def defense_submission_count(self, user_id: str) -> int:
        async with self._c.execute(
            "SELECT COUNT(*) AS n FROM defense_submissions WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        return int(row["n"]) if row else 0

    async def defense_history(self, user_id: str) -> list[dict]:
        async with self._c.execute(
            "SELECT blocked_count, total_payloads, usability_pass, usability_total,"
            " points, ts FROM defense_submissions WHERE user_id = ? ORDER BY ts DESC LIMIT 20",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    # ---------------- XSS nonce（spec §7.3）----------------

    async def issue_nonce(self, session_id: str, challenge_id: str) -> str:
        nonce = secrets.token_urlsafe(12)
        await self._c.execute(
            "INSERT INTO xss_nonces(nonce, session_id, challenge_id, created_at, used)"
            " VALUES (?,?,?,?,0)",
            (nonce, session_id, challenge_id, time.time()),
        )
        # 順手清掉過期的（TTL 由呼叫端保證，這裡固定清 1 小時前的）
        await self._c.execute(
            "DELETE FROM xss_nonces WHERE created_at < ?", (time.time() - 3600,)
        )
        await self._c.commit()
        return nonce

    async def consume_nonce(
        self, nonce: str, session_id: str, challenge_id: str, ttl: int
    ) -> bool:
        """一次性、綁 session、綁題目、有 TTL —— 四個條件都要過。"""
        async with self._c.execute(
            "SELECT session_id, challenge_id, created_at, used FROM xss_nonces WHERE nonce = ?",
            (nonce,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        if row["used"]:
            return False
        if row["session_id"] != session_id or row["challenge_id"] != challenge_id:
            return False
        if time.time() - float(row["created_at"]) > ttl:
            return False
        cur = await self._c.execute(
            "UPDATE xss_nonces SET used = 1 WHERE nonce = ? AND used = 0", (nonce,)
        )
        await self._c.commit()
        return cur.rowcount > 0

    # ---------------- meta / 預算 ----------------

    async def get_meta(self, key: str, default: str = "") -> str:
        async with self._c.execute("SELECT v FROM meta WHERE k = ?", (key,)) as cur:
            row = await cur.fetchone()
        return row["v"] if row else default

    async def set_meta(self, key: str, value: str) -> None:
        await self._c.execute(
            "INSERT INTO meta(k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
            (key, value),
        )
        await self._c.commit()

    async def add_tokens(self, n: int) -> int:
        await self._c.execute(
            "INSERT INTO meta(k, v) VALUES ('tokens_used', ?)"
            " ON CONFLICT(k) DO UPDATE SET v = CAST(CAST(meta.v AS INTEGER) + ? AS TEXT)",
            (str(n), n),
        )
        await self._c.commit()
        return int(await self.get_meta("tokens_used", "0") or 0)

    async def tokens_used(self) -> int:
        try:
            return int(await self.get_meta("tokens_used", "0") or 0)
        except ValueError:  # pragma: no cover
            return 0

    async def stats(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, sql in (
            ("users", "SELECT COUNT(*) n FROM users"),
            ("sessions", "SELECT COUNT(*) n FROM sessions"),
            ("attempts", "SELECT COUNT(*) n FROM attempts"),
            ("solves", "SELECT COUNT(*) n FROM solves"),
            ("defense_submissions", "SELECT COUNT(*) n FROM defense_submissions"),
        ):
            async with self._c.execute(sql) as cur:
                row = await cur.fetchone()
            out[name] = int(row["n"]) if row else 0
        async with self._c.execute(
            "SELECT challenge_id, COUNT(*) n FROM solves GROUP BY challenge_id"
        ) as cur:
            out["solves_by_challenge"] = {
                r["challenge_id"]: int(r["n"]) for r in await cur.fetchall()
            }
        out["tokens_used"] = await self.tokens_used()
        return out


async def seed_users(db: Database, count: int, prefix: str = "u") -> list[dict]:
    """產生活動當天要發給學員的 token。已有使用者時不重複產生。"""
    created: list[dict] = []
    existing = await db.count_users()
    for i in range(existing + 1, existing + count + 1):
        uid = f"{prefix}{i:03d}"
        token = make_user_token()
        await db.create_user(uid, f"選手{i:03d}", token)
        created.append({"user_id": uid, "display_name": f"選手{i:03d}", "token": token})
    return created


def write_user_csv(path: Path, users: Iterable[dict]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["user_id", "display_name", "token"])
        if not exists:
            w.writeheader()
        for u in users:
            w.writerow({k: u[k] for k in ("user_id", "display_name", "token")})
