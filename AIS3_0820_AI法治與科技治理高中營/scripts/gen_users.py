#!/usr/bin/env python3
"""產生活動當天要發給學員的參賽代碼。

用法（容器內）：
    docker compose exec app python scripts/gen_users.py --count 90
用法（本機）：
    python scripts/gen_users.py --count 90

輸出：寫入資料庫 + 附加到 ${DATA_DIR}/users.csv（可直接列印裁切發放）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings          # noqa: E402
from app.db import Database, seed_users, write_user_csv  # noqa: E402
from app.flags import flag_for               # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=90, help="要產生幾組")
    ap.add_argument("--prefix", default="u", help="user_id 前綴")
    ap.add_argument("--show-flags", action="store_true",
                    help="順便印出每個人每題的 flag（僅供工作人員對答案，勿外流）")
    args = ap.parse_args()

    s = get_settings()
    db = Database(s.db_path)
    await db.connect()
    try:
        created = await seed_users(db, args.count, args.prefix)
        csv_path = s.data_dir / "users.csv"
        write_user_csv(csv_path, created)
        print(f"已建立 {len(created)} 組使用者，清單附加到 {csv_path}")
        for u in created[:5]:
            print(f"  {u['user_id']}  {u['display_name']}  {u['token']}")
        if len(created) > 5:
            print(f"  …（其餘 {len(created) - 5} 組見 CSV）")

        if args.show_flags:
            from app.challenges import load_challenges

            cs = load_challenges(s.challenges_path)
            print("\n=== 對答案用（機密）===")
            for u in created:
                line = [u["user_id"]]
                for c in cs.all:
                    if c.win.get("kind") in {"leak", "indirect_leak", "tool_exfil", "xss"}:
                        line.append(f"{c.challenge_id}={flag_for(s.server_secret, u['user_id'], c.challenge_id)}")
                print("  " + "  ".join(line))
    finally:
        await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
