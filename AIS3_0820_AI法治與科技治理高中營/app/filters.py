"""輸出後處理過濾器（spec §8 `defense`）。

**這些過濾器是題目難度設計，不是真正的防護。**
L1c / final1 這些關卡就是要讓學員繞過它們（拆字、編碼、反寫），這正是教學點。

套用時機（spec §10）：模型回覆 -> 這裡 -> §7 判定 -> 回前端。
過濾後的文字同時是「回給學員看的」與「拿去判定的」，所以擋掉就等於沒過關。
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger("ctf.filters")

BLOCKED_PLACEHOLDER = "[已封鎖：輸出過濾器攔截了這段回覆]"

_MAX_REGEX_INPUT = 20_000


class FilterResult:
    __slots__ = ("text", "blocked", "triggered")

    def __init__(self, text: str, blocked: bool, triggered: list[str]):
        self.text = text
        self.blocked = blocked
        self.triggered = triggered


def _compile(pattern: str) -> re.Pattern[str] | None:
    try:
        return re.compile(pattern, re.DOTALL)
    except re.error as exc:
        log.error("challenges.json 中的正規表示式無效：%r (%s)", pattern, exc)
        return None


def apply_defense(reply: str, defense: list[dict] | None, flag: str) -> FilterResult:
    """依序套用 defense 清單。

    支援的 filter：
      block_substring  命中就整段換成 [已封鎖]（預設不分大小寫）
      block_regex      命中就整段換成 [已封鎖]
      strip_flag       只挖掉「這個 user 的 flag」與泛用 FLAG{...} 片段
      strip_regex      只把 regex 命中處換成 replacement（不整段封鎖）
    """
    text = reply or ""
    triggered: list[str] = []
    if not defense:
        return FilterResult(text, False, triggered)

    scan = text[:_MAX_REGEX_INPUT]

    for rule in defense:
        if not isinstance(rule, dict):
            continue
        kind = rule.get("filter")

        if kind == "block_substring":
            needle = str(rule.get("value", ""))
            if not needle:
                continue
            # ASSUMPTION: 預設不分大小寫。spec §11 L1c 同時列了 "FLAG{" 與 "flag"，
            # 若區分大小寫，"flag" 這條幾乎沒作用；不分大小寫才符合題目意圖。
            # 需要區分時在 challenges.json 加 "case_sensitive": true。
            if rule.get("case_sensitive"):
                hit = needle in text
            else:
                hit = needle.lower() in text.lower()
            if hit:
                triggered.append(f"block_substring:{needle}")
                return FilterResult(BLOCKED_PLACEHOLDER, True, triggered)

        elif kind == "block_regex":
            rx = _compile(str(rule.get("value", "")))
            if rx is None:
                continue
            if rx.search(scan):
                triggered.append(f"block_regex:{rule.get('value')}")
                return FilterResult(BLOCKED_PLACEHOLDER, True, triggered)

        elif kind == "strip_flag":
            replacement = str(rule.get("replacement", "[REDACTED]"))
            before = text
            if flag:
                text = text.replace(flag, replacement)
                # 也擋掉大小寫變形的整串 flag
                text = re.sub(re.escape(flag), replacement, text, flags=re.IGNORECASE)
            text = re.sub(r"FLAG\{[^}]{0,128}\}", replacement, text, flags=re.IGNORECASE)
            if text != before:
                triggered.append("strip_flag")
            scan = text[:_MAX_REGEX_INPUT]

        elif kind == "strip_regex":
            rx = _compile(str(rule.get("value", "")))
            if rx is None:
                continue
            replacement = str(rule.get("replacement", "[REDACTED]"))
            new_text, n = rx.subn(replacement, text)
            if n:
                triggered.append(f"strip_regex:{rule.get('value')}")
                text = new_text
                scan = text[:_MAX_REGEX_INPUT]

        else:
            log.warning("未知的 defense filter 類型：%r（已忽略）", kind)

    return FilterResult(text, False, triggered)


KNOWN_FILTERS = {"block_substring", "block_regex", "strip_flag", "strip_regex"}
