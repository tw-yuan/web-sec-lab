"""per-user canary flag（spec §6）。

flag = FLAG{<challenge_id>_<token>}
token = HMAC_SHA256(SERVER_SECRET, "<user_id>:<challenge_id>")[:8]（hex）

重點：
- 每個 user 每題的 flag 都不同 → 貼到群組給別人送分無效。
- server 可隨時重算，不必入庫。
- token 用純 hex，確保 §7 的正規化比對不會誤中一般英文字。
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

FLAG_RE = re.compile(r"FLAG\{[^}]{1,128}\}", re.IGNORECASE)

_TOKEN_LEN = 8


def flag_token(server_secret: str, user_id: str, challenge_id: str) -> str:
    mac = hmac.new(
        server_secret.encode("utf-8"),
        f"{user_id}:{challenge_id}".encode("utf-8"),
        hashlib.sha256,
    )
    return mac.hexdigest()[:_TOKEN_LEN]


def flag_for(server_secret: str, user_id: str, challenge_id: str) -> str:
    return f"FLAG{{{challenge_id}_{flag_token(server_secret, user_id, challenge_id)}}}"


def random_secret(prefix: str = "def") -> str:
    """DEF 關卡用的一次性測試秘密，格式與 flag 一致以便重用 §7 判定引擎。"""
    return f"FLAG{{{prefix}_{secrets.token_hex(_TOKEN_LEN // 2)}}}"


def parse_flag(text: str) -> tuple[str, str] | None:
    """從 'FLAG{l1a_9f3c1a7b}' 解出 (challenge_id, token)；解不出回 None。"""
    m = FLAG_RE.search(text.strip())
    if not m:
        return None
    inner = m.group(0)[len("FLAG{"):-1]
    if "_" not in inner:
        return None
    cid, _, token = inner.rpartition("_")
    if not cid or not token:
        return None
    return cid, token.lower()


def find_flag_owner(
    server_secret: str, submitted: str, challenge_id: str, user_ids: list[str]
) -> str | None:
    """判斷這個提交的 flag 是不是「別人的」（spec §6：疑似分享要記錄）。

    活動規模只有幾十~一百人，線性掃描成本可忽略。
    """
    parsed = parse_flag(submitted)
    if not parsed:
        return None
    cid, token = parsed
    if cid != challenge_id:
        return None
    for uid in user_ids:
        if hmac.compare_digest(flag_token(server_secret, uid, challenge_id), token):
            return uid
    return None
