#!/usr/bin/env python3
"""清掉比賽進度，但**保留使用者與他們的參賽代碼**。

用途：活動前把測試期間累積的解題紀錄、排行榜、嘗試紀錄清乾淨，
而已經印好發出去的參賽代碼不受影響（flag 也不變，因為 flag 是從
SERVER_SECRET + user_id 算出來的）。

    docker compose exec app python scripts/reset_progress.py --yes

只想砍某幾個測試帳號：

    docker compose exec app python scripts/reset_progress.py --yes --drop-users u091 u092

想連使用者一起砍掉重來（**會讓已發出的參賽代碼全部失效**）：

    docker compose exec app python scripts/reset_progress.py --yes --drop-all-users
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import Database          # noqa: E402

PROGRESS_TABLES = [
    "solves", "scores", "attempts", "defense_submissions",
    "flag_submissions", "hints_taken", "xss_nonces", "prompt_logs",
]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="確認執行（不加就只做預覽）")
    ap.add_argument("--drop-users", nargs="*", default=[],
                    help="順便刪掉這些 user_id（例如測試帳號）")
    ap.add_argument("--drop-all-users", action="store_true",
                    help="連所有使用者一起刪掉——已發出的參賽代碼會全部失效")
    ap.add_argument("--keep-tokens", action="store_true",
                    help="也把 token 用量計數歸零（預設會歸零，加這個表示保留）")
    args = ap.parse_args()

    s = get_settings()
    db = Database(s.db_path)
    await db.connect()
    try:
        before = await db.stats()
        print("目前狀態：")
        for k in ("users", "sessions", "attempts", "solves", "defense_submissions"):
            print(f"  {k:<22}{before[k]}")
        print(f"  {'tokens_used':<22}{before['tokens_used']}")
        print(f"  解題分布：{before['solves_by_challenge']}")

        if not args.yes:
            print("\n（預覽模式，沒有實際刪除。確定要清就加 --yes）")
            return 0

        conn = db.conn
        assert conn is not None

        for t in PROGRESS_TABLES:
            await conn.execute(f"DELETE FROM {t}")
        await conn.execute("DELETE FROM sessions")

        if args.drop_all_users:
            await conn.execute("DELETE FROM users")
            print("\n⚠️  已刪除所有使用者——請重新產生參賽代碼並重印。")
        elif args.drop_users:
            for uid in args.drop_users:
                await conn.execute("DELETE FROM users WHERE user_id = ?", (uid,))
            print(f"\n已刪除 {len(args.drop_users)} 個指定帳號。")

        if not args.keep_tokens:
            await conn.execute("DELETE FROM meta WHERE k = 'tokens_used'")

        await conn.commit()
        await conn.execute("VACUUM")
        await conn.commit()

        after = await db.stats()
        print("\n清理後：")
        for k in ("users", "sessions", "attempts", "solves", "defense_submissions"):
            print(f"  {k:<22}{after[k]}")
        print(f"  {'tokens_used':<22}{after['tokens_used']}")
        print("\n✅ 進度已清空。參賽代碼與每個人的 flag 都沒有改變。")
    finally:
        await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
