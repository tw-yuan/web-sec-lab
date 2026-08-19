"""FastAPI 應用 —— API 合約見 spec §10。

安全前提（spec §3，不可繞過）：
- OPENROUTER_API_KEY / SERVER_SECRET 永不出現在任何回應或 log。
- 破關判定全部在後端用決定性規則（app/judging.py），**不經 LLM**。
- L3 的 locked_doc：後端固定 user 指令，不接受任意 user 文字。
- L4 的 XSS：模型輸出只在 null-origin 的 sandbox iframe 內執行，破關訊號走一次性 nonce。
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import flags as flagmod
from . import judging, payloads, weblabs
from .challenges import Challenge, load_challenges
from .config import get_settings
from .db import Database, seed_users, write_user_csv
from .filters import apply_defense
from .llm import LLMClient, LLMError
from .ratelimit import SlidingWindow
from .schemas import (
    AdminFinalReq, ChatReq, DefenseReq, DisplayNameReq, HintReq,
    LoginReq, SubmitFlagReq, XssCallbackReq,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("ctf")

META_FINAL_OPEN = "final_open"
META_HINTS_OPEN = "hints_open"


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}


# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------


class State:
    settings = None
    db: Database | None = None
    llm: LLMClient | None = None
    challenges = None
    rl_challenge = SlidingWindow(60.0)
    rl_user = SlidingWindow(60.0)
    rl_login = SlidingWindow(60.0)
    budget_warned = False


st = State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    st.settings = s
    st.challenges = load_challenges(s.challenges_path)

    db = Database(s.db_path)
    await db.connect()
    st.db = db

    if not await db.get_meta(META_FINAL_OPEN):
        await db.set_meta(META_FINAL_OPEN, "1" if s.final_open_default else "0")

    if s.seed_users > 0 and await db.count_users() == 0:
        created = await seed_users(db, s.seed_users)
        csv_path = s.data_dir / "users.csv"
        write_user_csv(csv_path, created)
        log.info("已產生 %d 組學員 token，清單寫入 %s", len(created), csv_path)

    llm = LLMClient(s)
    llm.budget_check = _budget_ok
    llm.budget_add = _budget_add
    await llm.startup()
    st.llm = llm

    if not s.openrouter_api_key and not s.fake_llm:
        log.warning("OPENROUTER_API_KEY 未設定：/api/chat 會回錯誤。請檢查 .env。")
    if s.fake_llm:
        log.warning("FAKE_LLM=1：模型呼叫是假的，只能用於開發，**不可用於活動**。")
    if not s.admin_token:
        log.warning("ADMIN_TOKEN 未設定：/api/admin/* 全部停用。")

    try:
        yield
    finally:
        await llm.shutdown()
        await db.close()


app = FastAPI(
    title="AI Security 體驗營 CTF",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# ---------------------------------------------------------------------------
# 中介層：安全標頭
# ---------------------------------------------------------------------------

# 主站 CSP。注意：XSS 沙箱頁 /sandbox.html 走另一組寬鬆 CSP（見下方 sandbox 路由），
# 因為那一頁「就是要能執行注入的 inline JS」，而它是 null origin、default-src 'none'。
_MAIN_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-src 'self'; "
    "form-action 'none'; "
    "base-uri 'none'; "
    "object-src 'none'; "
    "frame-ancestors 'none'"
)

_SANDBOX_CSP = (
    # 只允許執行注入的 inline JS（教學目的）。
    # 沒有 connect-src / img-src / frame-src → 注入的 JS 打不出去、外連不了。
    "default-src 'none'; "
    "script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; "
    "form-action 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'self'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    try:
        resp: Response = await call_next(request)
    except ApiError as exc:  # pragma: no cover - 由 exception_handler 處理
        raise exc

    path = request.url.path
    if path == "/sandbox.html":
        # 沙箱頁需要能被主站 iframe 嵌入，且必須能執行注入的 inline JS。
        # 由 frame-ancestors 'self' 控制嵌入來源，不設 X-Frame-Options。
        resp.headers["Content-Security-Policy"] = _SANDBOX_CSP
    else:
        resp.headers["Content-Security-Policy"] = _MAIN_CSP
        resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["Cache-Control"] = resp.headers.get("Cache-Control", "no-store")
    return resp


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    body: dict[str, Any] = {"error": {"code": exc.code, "message": exc.message}}
    body.update(exc.extra)
    return JSONResponse(status_code=exc.status, content=body)


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    # spec §3 / §13：不可把 stack trace 露給前端
    log.exception("未處理的例外：%s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "伺服器發生錯誤，請通知工作人員。"}},
    )


# ---------------------------------------------------------------------------
# 預算
# ---------------------------------------------------------------------------


async def _budget_ok() -> bool:
    s, db = st.settings, st.db
    if s is None or db is None:
        return True
    if s.global_token_budget <= 0:
        return True                      # 0 = 無上限
    used = await db.tokens_used()
    if used >= s.global_token_budget:
        log.error("全域 token 預算已用盡：%s / %s", used, s.global_token_budget)
        return False
    return True


async def _budget_add(n: int) -> None:
    s, db = st.settings, st.db
    if s is None or db is None or n <= 0:
        return
    used = await db.add_tokens(n)
    if s.global_token_budget <= 0:
        return
    if not st.budget_warned and used >= s.global_token_budget * s.budget_warn_ratio:
        st.budget_warned = True
        log.error(
            "【預算告警】token 使用量已達 %.0f%%（%s / %s）",
            100 * used / max(1, s.global_token_budget), used, s.global_token_budget,
        )


# ---------------------------------------------------------------------------
# 驗證輔助
# ---------------------------------------------------------------------------


def _effective_points(challenge_id: str, stored: int) -> int:
    """一題的實得分數。

    一般題：用 challenges.json 的**當前**分數，不用破關當下的快照——
      否則活動中途調整某題分數時，舊紀錄會停在舊分數
      （曾經出現「全解完 5600 分 > 滿分 5570」的 bug）。
    DEF：分數本來就是按防禦成效比例給的（spec §11），用存下來的值。
    """
    cs = st.challenges
    ch = cs.by_id.get(challenge_id) if cs else None
    if ch is None:
        return 0                      # 題目被移除 → 不再計分
    if ch.win.get("kind") == "defense":
        return min(stored, ch.points)
    return ch.points


def _score_of(stored: dict) -> int:
    return sum(_effective_points(cid, pts) for cid, pts in stored.items())


async def require_user(session_id: str) -> dict:
    db, s = st.db, st.settings
    assert db is not None and s is not None
    user = await db.session_user(session_id, s.session_ttl_seconds)
    if not user:
        raise ApiError(401, "invalid_session", "登入已失效，請重新輸入你的參賽代碼。")
    return user


async def final_open() -> bool:
    assert st.db is not None
    return (await st.db.get_meta(META_FINAL_OPEN, "0")) == "1"


async def hints_open() -> bool:
    """提示是否開放點開。預設開放；工作人員可在後臺關閉（例如比賽計分階段）。"""
    assert st.db is not None
    return (await st.db.get_meta(META_HINTS_OPEN, "1")) == "1"


async def require_challenge(challenge_id: str) -> Challenge:
    assert st.challenges is not None
    ch = st.challenges.get(challenge_id)
    if ch is None:
        raise ApiError(404, "unknown_challenge", "找不到這道題目。")
    if ch.release_stage == "final" and not await final_open():
        raise ApiError(403, "not_released", "綜合挑戰尚未開放。")
    return ch


async def enforce_rate(user_id: str, challenge_id: str) -> int:
    """每一項都是 0 = 不限。全部設 0 時，只剩 GLOBAL_TOKEN_BUDGET 擋成本。"""
    s, db = st.settings, st.db
    assert s is not None and db is not None

    if s.rate_per_user_per_min > 0:
        ok, _, retry = st.rl_user.hit(f"u:{user_id}", s.rate_per_user_per_min)
        if not ok:
            raise ApiError(
                429, "rate_limited",
                f"你送太快了，請等 {int(retry) + 1} 秒再試。",
                {"retry_after": int(retry) + 1},
            )

    remaining = -1  # -1 = 不限
    if s.rate_per_challenge_per_min > 0:
        ok, remaining, retry = st.rl_challenge.hit(
            f"c:{user_id}:{challenge_id}", s.rate_per_challenge_per_min
        )
        if not ok:
            raise ApiError(
                429, "rate_limited",
                f"這一題送太快了，請等 {int(retry) + 1} 秒再試。",
                {"retry_after": int(retry) + 1},
            )

    if s.max_attempts_per_challenge > 0:
        used = await db.attempt_count(user_id, challenge_id)
        if used >= s.max_attempts_per_challenge:
            raise ApiError(429, "attempt_limit", "這一題的嘗試次數已達上限，請找工作人員。")
    return remaining


_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_name(raw: str, max_len: int) -> str:
    name = _CTRL.sub("", raw).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:max_len] or "選手"


# ---------------------------------------------------------------------------
# 基本
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.post("/api/login")
async def login(req: LoginReq, request: Request):
    db, s = st.db, st.settings
    assert db is not None and s is not None

    if s.rate_login_per_min > 0:
        ip = request.client.host if request.client else "unknown"
        ok, _, retry = st.rl_login.hit(f"login:{ip}", s.rate_login_per_min)
        if not ok:
            raise ApiError(429, "rate_limited", f"嘗試太頻繁，請等 {int(retry) + 1} 秒。")

    token = req.token.strip().upper().replace(" ", "")
    if len(token) == 8 and "-" not in token:
        token = f"{token[:4]}-{token[4:]}"
    user = await db.user_by_token(token)
    if not user:
        raise ApiError(401, "invalid_token", "參賽代碼不正確，請再確認一次。")
    sid = await db.create_session(user["user_id"])
    return {
        "session_id": sid,
        "user_id": user["user_id"],
        "display_name": user["display_name"],
    }


@app.get("/api/me")
async def me(session_id: str = ""):
    user = await require_user(session_id)
    assert st.db is not None and st.challenges is not None
    stored = await st.db.solved_map(user["user_id"])
    return {
        "user_id": user["user_id"],
        "display_name": user["display_name"],
        "score": _score_of(stored),
        "solved": sorted(stored.keys()),
    }


@app.post("/api/me/display-name")
async def set_display_name(req: DisplayNameReq):
    user = await require_user(req.session_id)
    assert st.db is not None and st.settings is not None
    name = sanitize_name(req.display_name, st.settings.max_display_name_chars)
    await st.db.set_display_name(user["user_id"], name)
    return {"display_name": name}


@app.get("/api/challenges")
async def list_challenges(session_id: str = ""):
    user = await require_user(session_id)
    db, cs = st.db, st.challenges
    assert db is not None and cs is not None

    fo = await final_open()
    stored = await db.solved_map(user["user_id"])
    items = [
        c.public(
            solved=c.challenge_id in stored,
            points_earned=(
                _effective_points(c.challenge_id, stored[c.challenge_id])
                if c.challenge_id in stored else 0
            ),
        )
        for c in cs.visible(final_open=fo)
    ]
    return {
        "groups": cs.groups,
        "challenges": items,
        "final_open": fo,
        "score": _score_of(stored),
        "total_points": cs.total_points(final_open=fo),
    }


@app.get("/api/challenges/{challenge_id}")
async def challenge_detail(challenge_id: str, session_id: str = ""):
    user = await require_user(session_id)
    ch = await require_challenge(challenge_id)
    assert st.db is not None and st.settings is not None
    stored = await st.db.solved_map(user["user_id"])
    data = ch.public(
        solved=challenge_id in stored,
        points_earned=(
            _effective_points(challenge_id, stored[challenge_id])
            if challenge_id in stored else 0
        ),
    )
    data["hints_open"] = await hints_open()
    if ch.input_mode == "defense":
        data["defense_meta"] = {
            "battery_size": payloads.battery_size(),
            "usability_size": payloads.usability_size(),
            "max_submissions": st.settings.def_max_submissions,
            "used_submissions": await st.db.defense_submission_count(user["user_id"]),
            "require_usability": st.settings.def_require_usability,
        }
    if ch.win.get("kind") == "tool_exfil":
        data["tool_hint"] = {
            "tool_name": ch.win.get("tool_name"),
            "attacker_email": ch.win.get("attacker_email"),
        }
    return data


@app.post("/api/hint")
async def hint(req: HintReq):
    user = await require_user(req.session_id)
    ch = await require_challenge(req.challenge_id)
    assert st.db is not None
    if not await hints_open():
        raise ApiError(403, "hints_closed", "提示目前已被工作人員關閉。")
    if req.index >= len(ch.hints):
        raise ApiError(404, "no_such_hint", "沒有這一條提示了。")
    await st.db.take_hint(user["user_id"], ch.challenge_id, req.index)
    return {"index": req.index, "hint": ch.hints[req.index], "total": len(ch.hints)}


# ---------------------------------------------------------------------------
# /api/chat（spec §10）
# ---------------------------------------------------------------------------


def _build_messages(ch: Challenge, req: ChatReq, s) -> tuple[list[dict], str]:
    """回傳 (送給模型的 messages, 記錄用的輸入摘要)。"""
    if ch.input_mode == "locked_doc":
        # spec §9.2 / §13：使用者只能改 document，**不接受任意 user 文字**。
        # 這是「攻擊經由資料通道而非直接對話」的唯一保證。
        if req.messages:
            raise ApiError(
                400, "chat_locked",
                "這一題的對話框是鎖死的，你只能修改文件內容。",
            )
        doc = req.document
        if doc is None:
            raise ApiError(400, "missing_document", "請先填寫文件內容。")
        assert ch.data_channel is not None
        max_len = min(int(ch.data_channel.get("max_len", 4000)), s.max_document_chars)
        if len(doc) > max_len:
            raise ApiError(400, "document_too_long", f"文件內容最多 {max_len} 個字。")
        content = str(ch.data_channel.get("wrap", "{doc}")).replace("{doc}", doc)
        return [{"role": "user", "content": content}], doc

    if ch.input_mode not in ("free_chat", "xss_render"):
        raise ApiError(400, "bad_input_mode", "這一題不支援對話。")

    if req.document is not None:
        raise ApiError(400, "unexpected_document", "這一題不使用文件欄位。")
    msgs = req.messages or []
    if not msgs:
        raise ApiError(400, "empty_message", "請先輸入訊息。")
    if msgs[-1].role != "user":
        raise ApiError(400, "bad_messages", "最後一則訊息必須是你的發言。")

    trimmed = msgs[-s.max_history_messages:]
    out: list[dict] = []
    for m in trimmed:
        content = m.content[: s.max_user_message_chars]
        if not content.strip():
            continue
        out.append({"role": m.role, "content": content})
    if not out:
        raise ApiError(400, "empty_message", "請先輸入訊息。")
    if out[0]["role"] != "user":
        out = out[1:]
    if not out:
        raise ApiError(400, "empty_message", "請先輸入訊息。")
    return out, out[-1]["content"]


@app.post("/api/chat")
async def chat(req: ChatReq):
    user = await require_user(req.session_id)
    ch = await require_challenge(req.challenge_id)
    s, db, llm = st.settings, st.db, st.llm
    assert s is not None and db is not None and llm is not None

    if ch.input_mode == "defense":
        raise ApiError(400, "use_defense_endpoint", "這一題請用防禦提交介面。")

    remaining = await enforce_rate(user["user_id"], ch.challenge_id)
    messages, excerpt = _build_messages(ch, req, s)
    # prompt 全文紀錄用：間接注入題的輸入來自「文件」通道，其餘是自由對話。
    user_role = "document" if ch.input_mode == "locked_doc" else "user"

    # 輸入端過濾（在呼叫模型「之前」）。這是關卡難度設計，不是真防護 ——
    # 教學點就是要讓學員發現「擋關鍵字擋不住攻擊」。被擋下時不打模型，順便省錢。
    if ch.input_filter:
        for m in messages:
            hit = apply_defense(m["content"], ch.input_filter, "")
            if hit.blocked:
                await db.log_attempt(
                    user["user_id"], ch.challenge_id, excerpt, "input_blocked", 0
                )
                await db.log_turn(
                    user["user_id"], ch.challenge_id, req.session_id,
                    user_role=user_role, user_content=excerpt,
                    assistant_content=None, verdict="input_blocked", tokens_used=0,
                )
                return {
                    "reply": "🚫 你的訊息被**輸入端過濾器**擋下了，根本沒送到模型。",
                    "blocked": False,
                    "input_blocked": True,
                    "solved": False,
                    "first_solve": False,
                    "points": 0,
                    "tool_calls": None,
                    "rate": {"remaining": remaining},
                }

    # spec §6：注入「這個 user 的」canary
    flag = flagmod.flag_for(s.server_secret, user["user_id"], ch.challenge_id)
    system_prompt = (ch.system_prompt or "").replace("{{FLAG}}", flag)

    try:
        result = await llm.chat(
            system_prompt=system_prompt,
            messages=messages,
            session_id=f"{user['user_id']}:{ch.challenge_id}",
            temperature=float(ch.model.get("temperature", 0.3)),
            max_tokens=int(ch.model.get("max_tokens", 512)),
            tools=ch.tools,
            provider=ch.model.get("provider"),
            model=ch.model.get("model"),
        )
    except LLMError as exc:
        if exc.internal:
            log.warning("LLM 失敗 code=%s internal=%s", exc.code, exc.internal)
        await db.log_attempt(user["user_id"], ch.challenge_id, excerpt, f"error:{exc.code}", 0)
        await db.log_turn(
            user["user_id"], ch.challenge_id, req.session_id,
            user_role=user_role, user_content=excerpt,
            assistant_content=None, verdict=f"error:{exc.code}", tokens_used=0,
        )
        status = 503 if exc.code != "no_api_key" else 500
        raise ApiError(status, exc.code, exc.message)

    raw_reply = result["reply"]
    tool_calls = result["tool_calls"]

    # spec §10：先套 defense 過濾，再拿「過濾後的文字」去判定。
    filtered = apply_defense(raw_reply, ch.defense, flag)
    reply = filtered.text

    kind = ch.win.get("kind")
    solved = False
    method = ""

    if kind in ("leak", "indirect_leak"):
        if judging.leaked(reply, flag):
            solved, method = True, judging.leak_evidence(reply, flag) or "leak"
    elif kind == "tool_exfil":
        solved, method = judging.judge_tool_exfil(tool_calls, reply, flag, ch.win)
        method = method or ""
    elif kind == "tool_call":
        # 過度代理：不看有沒有洩漏，看模型有沒有真的去執行那個危險動作
        solved, method = judging.judge_tool_call(tool_calls, reply, ch.win)
        method = method or ""
    elif kind == "xss":
        # XSS 的破關訊號走 /api/xss-callback + 一次性 nonce（spec §7.3），這裡不判。
        pass

    first_solve = False
    if solved:
        first_solve = await db.record_solve(
            user["user_id"], ch.challenge_id, ch.points, method
        )

    verdict = "solved" if solved else ("blocked" if filtered.blocked else "miss")
    await db.log_attempt(
        user["user_id"], ch.challenge_id, excerpt, verdict, int(result["tokens"])
    )
    # 完整記錄這一輪：學員送的原文 + 模型「過濾前」的原始回覆（復盤時才看得出為何成功）。
    await db.log_turn(
        user["user_id"], ch.challenge_id, req.session_id,
        user_role=user_role, user_content=excerpt,
        assistant_content=raw_reply, verdict=verdict, tokens_used=int(result["tokens"]),
    )

    resp: dict[str, Any] = {
        "reply": reply,
        "blocked": filtered.blocked,
        "solved": solved,
        "first_solve": first_solve,
        "points": ch.points if solved else 0,
        "tool_calls": _public_tool_calls(tool_calls),
        "rate": {"remaining": remaining},
    }
    if solved:
        # 過關才把「你自己的 flag」告訴他，讓他去提交框練習提交流程。
        resp["flag"] = flag
    if ch.input_mode == "xss_render":
        resp["nonce"] = await db.issue_nonce(req.session_id, ch.challenge_id)
        resp["nonce_ttl"] = s.xss_nonce_ttl_seconds
    return resp


def _public_tool_calls(tool_calls: list[dict] | None) -> list[dict] | None:
    """把 tool_call 整理成前端可顯示的樣子（讓學員看到 agent「做了什麼」）。"""
    if not tool_calls:
        return None
    out = []
    for c in tool_calls:
        fn = (c or {}).get("function") or {}
        out.append({
            "name": str(fn.get("name", ""))[:64],
            "arguments": str(fn.get("arguments", ""))[:2000],
        })
    return out


# ---------------------------------------------------------------------------
# /api/submit-flag（spec §10 / §6）
# ---------------------------------------------------------------------------


@app.post("/api/submit-flag")
async def submit_flag(req: SubmitFlagReq):
    user = await require_user(req.session_id)
    ch = await require_challenge(req.challenge_id)
    s, db = st.settings, st.db
    assert s is not None and db is not None

    if s.rate_per_challenge_per_min > 0:
        ok, _, retry = st.rl_challenge.hit(
            f"f:{user['user_id']}:{ch.challenge_id}", max(10, s.rate_per_challenge_per_min)
        )
        if not ok:
            raise ApiError(429, "rate_limited", f"提交太頻繁，請等 {int(retry) + 1} 秒。")

    if ch.win.get("kind") == "defense":
        raise ApiError(400, "no_flag", "這一題沒有旗標，請直接提交你的防禦 prompt。")

    submitted = req.flag.strip()
    expected = flagmod.flag_for(s.server_secret, user["user_id"], ch.challenge_id)
    correct = submitted.lower() == expected.lower()

    suspected = None
    if not correct:
        # spec §6：貼別人的 flag 無效，且要記錄為可疑
        owner = flagmod.find_flag_owner(
            s.server_secret, submitted, ch.challenge_id, await db.all_user_ids()
        )
        if owner and owner != user["user_id"]:
            suspected = owner
            log.warning(
                "疑似 flag 分享：user=%s 提交了 user=%s 的 %s flag",
                user["user_id"], owner, ch.challenge_id,
            )

    await db.log_flag_submission(
        user["user_id"], ch.challenge_id, submitted, correct, suspected
    )

    if not correct:
        msg = "旗標不正確。"
        if suspected:
            msg = "這是別人的旗標喔！每個人的旗標都不一樣，請自己打出來。"
        return {"correct": False, "points": 0, "message": msg, "shared": bool(suspected)}

    first = await db.record_solve(user["user_id"], ch.challenge_id, ch.points, "submit")
    return {
        "correct": True,
        "points": ch.points,
        "first_solve": first,
        "message": "答對了！" if first else "答對了（這題你已經破過了）。",
    }


# ---------------------------------------------------------------------------
# /api/xss-callback（spec §7.3 / §10）
# ---------------------------------------------------------------------------


@app.post("/api/xss-callback")
async def xss_callback(req: XssCallbackReq, origin: str = Header(default="")):
    user = await require_user(req.session_id)
    ch = await require_challenge(req.challenge_id)
    s, db = st.settings, st.db
    assert s is not None and db is not None

    if ch.win.get("kind") != "xss":
        raise ApiError(400, "wrong_challenge", "這一題不是 XSS 題。")

    # 沙箱 iframe 是 null origin；回報一律由主頁發出，因此拒絕 Origin: null。
    if origin.strip().lower() == "null":
        raise ApiError(403, "bad_origin", "無效的請求來源。")

    ok = await db.consume_nonce(
        req.nonce, req.session_id, ch.challenge_id, s.xss_nonce_ttl_seconds
    )
    if not ok:
        raise ApiError(400, "bad_nonce", "驗證碼無效或已使用，請重新產生一次回覆再試。")

    first = await db.record_solve(user["user_id"], ch.challenge_id, ch.points, "xss")
    await db.log_attempt(user["user_id"], ch.challenge_id, "(xss callback)", "solved", 0)
    return {
        "solved": True,
        "first_solve": first,
        "points": ch.points,
        "flag": flagmod.flag_for(s.server_secret, user["user_id"], ch.challenge_id),
    }


# ---------------------------------------------------------------------------
# /api/defense/submit（spec §11 DEF）
# ---------------------------------------------------------------------------


@app.post("/api/defense/submit")
async def defense_submit(req: DefenseReq):
    user = await require_user(req.session_id)
    ch = await require_challenge("def")
    s, db, llm = st.settings, st.db, st.llm
    assert s is not None and db is not None and llm is not None

    used = await db.defense_submission_count(user["user_id"])
    # DEF_MAX_SUBMISSIONS=0 表示不限次數；仍受下面每分鐘 3 次的速率限制
    # 與全域 token 預算約束，不會失控。
    if s.def_max_submissions > 0 and used >= s.def_max_submissions:
        raise ApiError(
            429, "submit_limit",
            f"防禦提交次數已用完（上限 {s.def_max_submissions} 次）。",
        )

    prompt = req.system_prompt.strip()
    if len(prompt) > s.max_defense_prompt_chars:
        raise ApiError(400, "too_long", f"防禦 prompt 最多 {s.max_defense_prompt_chars} 個字。")
    if "{{SECRET}}" not in prompt:
        raise ApiError(400, "missing_placeholder", "你的 prompt 必須包含 {{SECRET}} 這個佔位符。")

    if s.def_rate_per_min > 0:
        ok, _, retry = st.rl_user.hit(f"def:{user['user_id']}", s.def_rate_per_min)
        if not ok:
            raise ApiError(429, "rate_limited", f"請等 {int(retry) + 1} 秒再提交一次。")

    secret = flagmod.random_secret()
    system_prompt = prompt.replace("{{SECRET}}", secret)

    # DEF 一次提交 = battery + probes 次呼叫，成本較高（spec §11 DEF 注意事項）
    sem = asyncio.Semaphore(6)

    async def run_one(uid: str, content: str) -> tuple[str, str, int]:
        async with sem:
            try:
                r = await llm.chat(
                    system_prompt=system_prompt,
                    messages=[{"role": "user", "content": content}],
                    session_id=f"{user['user_id']}:def",
                    temperature=0.0,   # spec §7.4：求穩定可重現
                    max_tokens=int(ch.model.get("max_tokens", 256)),
                )
                return uid, r["reply"], int(r["tokens"])
            except LLMError as exc:
                # 上游失敗 → 保守判為「沒擋下」不公平；標記為 error 後從分母移除。
                log.warning("DEF payload %s 失敗：%s", uid, exc.code)
                return uid, "__LLM_ERROR__", 0

    attack_tasks = [run_one(pid, text) for pid, _desc, text in payloads.ATTACK_BATTERY]
    probe_tasks = [run_one(qid, text) for qid, text, _exp in payloads.USABILITY_PROBES]
    results = await asyncio.gather(*attack_tasks, *probe_tasks)

    by_id = {uid: (reply, tok) for uid, reply, tok in results}
    total_tokens = sum(tok for _, _, tok in results)

    leaked_payloads: list[dict] = []
    blocked = 0
    counted = 0
    errors = 0
    for pid, desc, _text in payloads.ATTACK_BATTERY:
        reply, _ = by_id.get(pid, ("__LLM_ERROR__", 0))
        if reply == "__LLM_ERROR__":
            errors += 1
            continue
        counted += 1
        if judging.leaked(reply, secret):
            leaked_payloads.append({"id": pid, "desc": desc})
        else:
            blocked += 1

    usability_pass = 0
    usability_total = 0
    usability_detail: list[dict] = []
    for qid, text, expected in payloads.USABILITY_PROBES:
        reply, _ = by_id.get(qid, ("__LLM_ERROR__", 0))
        if reply == "__LLM_ERROR__":
            continue
        usability_total += 1
        ok_probe = payloads.usability_passed(reply, expected)
        usability_pass += int(ok_probe)
        usability_detail.append({"id": qid, "question": text, "passed": ok_probe})

    if counted == 0:
        raise ApiError(503, "upstream_unavailable", "模型服務忙碌，請稍後再提交一次。")

    base = round(100 * blocked / counted)
    if s.def_require_usability and usability_total > 0:
        # ASSUMPTION（spec 外的補強）：spec 的 points = 100*blocked/total 會讓
        # 「什麼都不准回答」拿滿分，學到錯的結論。乘上可用度比例後，
        # 「把機器人變啞巴」不再是有效策略。可用 DEF_REQUIRE_USABILITY=0 關掉。
        points = round(base * usability_pass / usability_total)
    else:
        points = base

    await db.log_defense(
        user["user_id"], prompt, blocked, counted, usability_pass, usability_total, points
    )
    await db.upsert_defense_score(user["user_id"], points)
    await db.log_attempt(
        user["user_id"], "def", prompt[:300], f"blocked={blocked}/{counted}", total_tokens
    )

    return {
        "blocked": blocked,
        "total": counted,
        "errors": errors,
        "leaked_payloads": leaked_payloads,
        "usability": {
            "passed": usability_pass,
            "total": usability_total,
            "detail": usability_detail,
            "enforced": s.def_require_usability,
        },
        "points": points,
        "base_points": base,
        # None = 不限次數
        "submissions_left": (
            None if s.def_max_submissions <= 0
            else max(0, s.def_max_submissions - used - 1)
        ),
    }


@app.get("/api/defense/history")
async def defense_history(session_id: str = ""):
    user = await require_user(session_id)
    assert st.db is not None and st.settings is not None
    return {
        "history": await st.db.defense_history(user["user_id"]),
        "max_submissions": st.settings.def_max_submissions,
    }


@app.get("/api/defense/payloads")
async def defense_payloads(session_id: str = ""):
    """只回「攻擊手法的簡述」，不回完整 payload —— 讓學員知道自己被什麼打，
    但不至於直接照抄 payload 寫出針對性的字串比對防禦。"""
    await require_user(session_id)
    return {
        "battery": [{"id": pid, "desc": desc} for pid, desc, _ in payloads.ATTACK_BATTERY],
        "usability": [{"id": qid, "question": q} for qid, q, _ in payloads.USABILITY_PROBES],
    }


# ---------------------------------------------------------------------------
# 排行榜
# ---------------------------------------------------------------------------


@app.get("/api/leaderboard")
async def leaderboard(session_id: str = ""):
    await require_user(session_id)
    assert st.db is not None and st.challenges is not None
    rows = await st.db.leaderboard()
    fo = await final_open()
    entries = [
        {
            "display_name": r["display_name"],
            "score": _score_of(r["stored"]),
            "solved": r["solved"],
            "last_solved_at": r["last_solved_at"],
        }
        for r in rows
    ]
    # 分數高的在前；同分則先完成的在前
    entries.sort(key=lambda e: (-e["score"], e["last_solved_at"] or "9999"))
    return {
        "final_open": fo,
        "total_points": st.challenges.total_points(final_open=fo),
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# Admin（可選，需 ADMIN_TOKEN）
# ---------------------------------------------------------------------------


async def require_admin(x_admin_token: str = Header(default="")) -> None:
    s = st.settings
    assert s is not None
    if not s.admin_token:
        raise ApiError(404, "not_found", "找不到。")
    import hmac as _hmac

    if not _hmac.compare_digest(x_admin_token, s.admin_token):
        raise ApiError(401, "unauthorized", "未授權。")


@app.get("/api/admin/stats", dependencies=[Depends(require_admin)])
async def admin_stats():
    assert st.db is not None and st.settings is not None
    data = await st.db.stats()
    data["token_budget"] = st.settings.global_token_budget
    data["final_open"] = await final_open()
    data["hint_stats"] = await st.db.hint_stats()
    data["suspicious_flag_submissions"] = await st.db.suspicious_submissions()
    return data


@app.get("/api/admin/users", dependencies=[Depends(require_admin)])
async def admin_users():
    assert st.db is not None
    return {"users": await st.db.list_users()}


@app.get("/api/admin/prompts", dependencies=[Depends(require_admin)])
async def admin_prompts(challenge_id: str = "", user_id: str = "", limit: int = 300):
    """學員解題過程的完整 prompt / 回覆紀錄（教學復盤）。可依題目 / 學員過濾。"""
    assert st.db is not None
    rows = await st.db.fetch_prompts(
        challenge_id.strip() or None, user_id.strip() or None, limit
    )
    return {"rows": rows, "count": len(rows)}


@app.get("/api/admin/overview", dependencies=[Depends(require_admin)])
async def admin_overview():
    """後臺主控頁需要的所有資料，一次拿完（前端每 10 秒輪詢一次）。"""
    db, cs, s = st.db, st.challenges, st.settings
    assert db is not None and cs is not None and s is not None

    fo = await final_open()
    stats = await db.stats()
    rows = await db.leaderboard()

    solves_by = stats["solves_by_challenge"]
    hints = {}
    for h in await db.hint_stats():
        hints[h["challenge_id"]] = hints.get(h["challenge_id"], 0) + int(h["n"])
    attempts_by = await db.attempts_by_challenge()

    total = cs.total_points(final_open=fo)
    entries = sorted(
        (
            {
                "user_id": r["user_id"],
                "display_name": r["display_name"],
                "score": _score_of(r["stored"]),
                "solved": r["solved"],
                "last_solved_at": r["last_solved_at"],
            }
            for r in rows
        ),
        key=lambda e: (-e["score"], e["last_solved_at"] or "9999"),
    )
    active = sum(1 for e in entries if e["solved"])

    challenges = []
    for c in cs.all:
        n = int(solves_by.get(c.challenge_id, 0))
        challenges.append({
            "challenge_id": c.challenge_id,
            "group": c.group,
            "order": c.order,
            "title": c.title,
            "points": c.points,
            "enabled": c.enabled,
            "release_stage": c.release_stage,
            "solves": n,
            "attempts": int(attempts_by.get(c.challenge_id, 0)),
            "hints_taken": int(hints.get(c.challenge_id, 0)),
            "solve_rate": round(n / active, 3) if active else 0.0,
        })

    return {
        "final_open": fo,
        "hints_open": await hints_open(),
        "total_points": total,
        "active_users": active,
        "stats": stats,
        "budget": {
            "used": stats["tokens_used"],
            "limit": s.global_token_budget,      # 0 = 無上限
        },
        "limits": {
            "rate_per_challenge_per_min": s.rate_per_challenge_per_min,
            "rate_per_user_per_min": s.rate_per_user_per_min,
            "rate_login_per_min": s.rate_login_per_min,
            "max_attempts_per_challenge": s.max_attempts_per_challenge,
            "def_max_submissions": s.def_max_submissions,
            "def_rate_per_min": s.def_rate_per_min,
        },
        "challenges": sorted(challenges, key=lambda c: (c["group"], c["order"])),
        "entries": entries,
        "suspicious": stats.get("suspicious_flag_submissions", []),
    }


@app.post("/api/admin/final-open", dependencies=[Depends(require_admin)])
async def admin_final_open(req: AdminFinalReq):
    assert st.db is not None
    await st.db.set_meta(META_FINAL_OPEN, "1" if req.open else "0")
    log.info("FINAL 題組開放狀態改為：%s", req.open)
    return {"final_open": req.open}


@app.post("/api/admin/hints-open", dependencies=[Depends(require_admin)])
async def admin_hints_open(req: AdminFinalReq):
    """開 / 關前臺提示功能。關閉後學員按提示會收到 403。"""
    assert st.db is not None
    await st.db.set_meta(META_HINTS_OPEN, "1" if req.open else "0")
    log.info("提示開放狀態改為：%s", req.open)
    return {"hints_open": req.open}


@app.post("/api/admin/seed-users", dependencies=[Depends(require_admin)])
async def admin_seed_users(count: int = 10):
    assert st.db is not None and st.settings is not None
    count = max(1, min(500, count))
    created = await seed_users(st.db, count)
    write_user_csv(st.settings.data_dir / "users.csv", created)
    return {"created": created}


# ---------------------------------------------------------------------------
# Web 實戰靶場（前端驗證繞過 / IDOR）—— 破關端點見 app/weblabs.py
# ---------------------------------------------------------------------------

weblabs.configure(st=st, require_user=require_user, api_error_cls=ApiError)
app.include_router(weblabs.router)


# ---------------------------------------------------------------------------
# 靜態檔
# ---------------------------------------------------------------------------


def _mount_static() -> None:
    s = get_settings()
    if s.static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(s.static_dir)), name="static")


_mount_static()


def _static_file(name: str) -> FileResponse:
    s = get_settings()
    path = s.static_dir / name
    if not path.exists():
        raise ApiError(404, "not_found", "找不到頁面。")
    return FileResponse(path)


@app.get("/")
async def index_page():
    return _static_file("index.html")


@app.get("/challenge.html")
async def challenge_page():
    return _static_file("challenge.html")


@app.get("/leaderboard.html")
async def leaderboard_page():
    return _static_file("leaderboard.html")


@app.get("/admin.html")
async def admin_page():
    """後臺主控頁。頁面本身是公開的靜態檔，資料一律要 X-Admin-Token 才拿得到。"""
    return _static_file("admin.html")


@app.get("/prompts.html")
async def prompts_page():
    """後臺子頁：學員 prompt 全文紀錄檢視。資料一樣要 X-Admin-Token。"""
    return _static_file("prompts.html")


@app.get("/sandbox.html")
async def sandbox_page():
    """XSS 沙箱頁（spec §3.4）。

    它由 <iframe sandbox="allow-scripts">（**沒有** allow-same-origin）載入，
    因此執行在 null origin：讀不到主站 cookie / DOM / localStorage。
    回應標頭另外套用 _SANDBOX_CSP：default-src 'none' 讓注入的 JS 無法對外連線。

    ASSUMPTION: 用獨立路由而非 srcdoc。srcdoc 會**繼承父頁的 CSP**，
    等於把主站那組較寬鬆的政策帶進沙箱；獨立路由才能給沙箱一組獨立、更嚴的 CSP。
    隔離效果相同（一樣是 null origin，不需要第二個網域）。
    """
    return _static_file("sandbox.html")


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)
