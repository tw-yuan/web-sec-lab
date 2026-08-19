#!/usr/bin/env python3
"""把學員解題過程的完整 prompt / 回覆匯出，供活動後教學復盤。

用法（容器內）：
    docker compose exec app python scripts/export_prompts.py                 # 全部，輸出可讀文字
    docker compose exec app python scripts/export_prompts.py --challenge l2b # 只看某題
    docker compose exec app python scripts/export_prompts.py --format jsonl --out /srv/data/prompts.jsonl

--format:
    text  （預設）依「學員 / 題目 / 對話」分段的可讀逐字稿。
    jsonl 每行一列原始紀錄（給程式分析 / 匯入其他工具）。

沒有 --out 就印到 stdout。
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import Database          # noqa: E402


async def _load(challenge: str | None, user: str | None) -> list[dict]:
    s = get_settings()
    db = Database(s.db_path)
    await db.connect()
    try:
        sql = (
            "SELECT id, user_id, challenge_id, session_id, turn, role, content,"
            " verdict, tokens_used, ts FROM prompt_logs"
            " WHERE (? IS NULL OR challenge_id = ?) AND (? IS NULL OR user_id = ?)"
            " ORDER BY user_id, challenge_id, session_id, turn, id"
        )
        async with db.conn.execute(sql, (challenge, challenge, user, user)) as cur:
            return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


def _write_text(rows: list[dict], out: io.TextIOBase) -> None:
    last_key = None
    for r in rows:
        key = (r["user_id"], r["challenge_id"], r["session_id"])
        if key != last_key:
            out.write(
                f"\n{'=' * 70}\n"
                f"學員 {r['user_id']} · 題目 {r['challenge_id']} · session {(r['session_id'] or '')[:12]}\n"
                f"{'=' * 70}\n"
            )
            last_key = key
        who = {"user": "👤 學員", "document": "📄 文件", "assistant": "🤖 模型"}.get(
            r["role"], r["role"]
        )
        tag = f"（{r['verdict']}）" if r["role"] != "assistant" else ""
        out.write(f"\n[第 {r['turn']} 輪] {who} {tag}\n{r['content']}\n")


def _write_jsonl(rows: list[dict], out: io.TextIOBase) -> None:
    for r in rows:
        out.write(json.dumps(r, ensure_ascii=False) + "\n")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenge", default=None, help="只匯出某一題（challenge_id）")
    ap.add_argument("--user", default=None, help="只匯出某位學員（user_id）")
    ap.add_argument("--format", choices=["text", "jsonl"], default="text")
    ap.add_argument("--out", default=None, help="輸出檔路徑；省略則印到畫面")
    args = ap.parse_args()

    rows = await _load(args.challenge, args.user)
    if not rows:
        print("（沒有符合條件的 prompt 紀錄）", file=sys.stderr)
        return 0

    writer = _write_jsonl if args.format == "jsonl" else _write_text
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            writer(rows, fh)
        n_conv = len({(r["user_id"], r["challenge_id"], r["session_id"]) for r in rows})
        print(f"已匯出 {len(rows)} 列（{n_conv} 段對話）到 {args.out}")
    else:
        writer(rows, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
