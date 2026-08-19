"""載入並驗證 challenges.json（spec §8：單一事實來源）。

前端拿到的只有「安全欄位」——system_prompt / defense / win 永遠不下發。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .filters import KNOWN_FILTERS

log = logging.getLogger("ctf.challenges")

VALID_TYPES = {
    "chat_leak",
    "chat_direct",
    "indirect_summarize",
    "indirect_agent",
    "xss_output",
    "defense",
    # Web 實戰題（前端驗證繞過 / IDOR）：破關判定在 app/weblabs.py，不經 LLM。
    "weblab",
}
VALID_INPUT_MODES = {"free_chat", "locked_doc", "xss_render", "defense", "weblab"}
VALID_WIN_KINDS = {
    "leak", "indirect_leak", "tool_exfil", "tool_call", "xss", "defense", "weblab",
}

# input_mode 與 win.kind 必須相容，避免設定寫錯導致判定走錯分支
_MODE_TO_KINDS = {
    "free_chat": {"leak", "tool_call"},
    "locked_doc": {"indirect_leak", "tool_exfil", "tool_call"},
    "xss_render": {"xss"},
    "defense": {"defense"},
    "weblab": {"weblab"},
}


class ConfigError(ValueError):
    pass


class Challenge:
    __slots__ = (
        "challenge_id", "group", "order", "points", "release_stage", "enabled",
        "type", "input_mode", "title", "description_md", "hints", "model",
        "system_prompt", "defense", "input_filter", "data_channel", "tools", "win",
        "lab_url",
    )

    def __init__(self, raw: dict[str, Any], defaults: dict[str, Any]):
        self.challenge_id: str = raw["challenge_id"]
        self.group: str = raw["group"]
        self.order: int = int(raw.get("order", 0))
        self.points: int = int(raw.get("points", 100))
        self.release_stage: str = raw.get("release_stage", "main")
        self.enabled: bool = bool(raw.get("enabled", True))
        self.type: str = raw["type"]
        self.input_mode: str = raw["input_mode"]
        self.title: str = raw.get("title", self.challenge_id)
        self.description_md: str = raw.get("description_md", "")
        self.hints: list[str] = list(raw.get("hints") or [])
        self.model: dict[str, Any] = {**defaults, **(raw.get("model") or {})}
        self.system_prompt: str | None = raw.get("system_prompt")
        self.defense: list[dict] = list(raw.get("defense") or [])
        # 輸入端過濾：在呼叫模型「之前」檢查使用者輸入。
        # 教學點是「擋關鍵字擋不住攻擊」，順便也省了被擋下那次的模型費用。
        self.input_filter: list[dict] = list(raw.get("input_filter") or [])
        self.data_channel: dict | None = raw.get("data_channel")
        self.tools: list[dict] | None = raw.get("tools")
        self.win: dict = raw.get("win") or {}
        # weblab 題型：靶場頁的相對網址（例如 /static/labs/lab.html?id=a1）
        self.lab_url: str | None = raw.get("lab_url")

    # ---- 前端可見欄位（絕不含 system_prompt / defense / win）----
    def public(self, *, solved: bool = False, points_earned: int = 0) -> dict[str, Any]:
        dc = None
        if self.data_channel:
            wrap = self.data_channel.get("wrap", "{doc}")
            dc = {
                "field": self.data_channel.get("field", "document"),
                "max_len": int(self.data_channel.get("max_len", 4000)),
                "placeholder": self.data_channel.get("placeholder", ""),
                # 讓學員看到「後端固定送出的那句使用者指令」長什麼樣（唯讀）
                "locked_instruction": wrap.replace("{doc}", "〈你在下面編輯的文件內容〉"),
            }
        return {
            "challenge_id": self.challenge_id,
            "group": self.group,
            "order": self.order,
            "points": self.points,
            "release_stage": self.release_stage,
            "type": self.type,
            "input_mode": self.input_mode,
            "title": self.title,
            "description_md": self.description_md,
            "hint_count": len(self.hints),
            "data_channel": dc,
            # 只告訴前端「有沒有輸入過濾」，不下發過濾規則本身
            "has_input_filter": bool(self.input_filter),
            "lab_url": self.lab_url,
            "solved": solved,
            "points_earned": points_earned,
        }


class ChallengeSet:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw
        self.defaults: dict[str, Any] = raw.get("defaults") or {}
        self.groups: list[dict] = sorted(
            raw.get("groups") or [], key=lambda g: int(g.get("order", 0))
        )
        items = [Challenge(c, self.defaults) for c in raw.get("challenges") or []]
        self.all: list[Challenge] = sorted(items, key=lambda c: (c.group, c.order))
        self.by_id: dict[str, Challenge] = {c.challenge_id: c for c in self.all}

    def get(self, challenge_id: str) -> Challenge | None:
        c = self.by_id.get(challenge_id)
        return c if c and c.enabled else None

    def visible(self, *, final_open: bool) -> list[Challenge]:
        return [
            c for c in self.all
            if c.enabled and (final_open or c.release_stage != "final")
        ]

    def total_points(self, *, final_open: bool) -> int:
        return sum(c.points for c in self.visible(final_open=final_open))


def _validate(raw: dict[str, Any]) -> None:
    challenges = raw.get("challenges")
    if not isinstance(challenges, list) or not challenges:
        raise ConfigError("challenges.json 必須有非空的 'challenges' 陣列")

    seen: set[str] = set()
    for c in challenges:
        cid = c.get("challenge_id")
        if not cid or not isinstance(cid, str):
            raise ConfigError(f"缺少 challenge_id：{c!r}")
        if cid in seen:
            raise ConfigError(f"challenge_id 重複：{cid}")
        seen.add(cid)
        if "_" in cid:
            # flag 格式是 FLAG{<challenge_id>_<token>}，challenge_id 含底線會讓解析歧義
            raise ConfigError(f"challenge_id 不可含底線：{cid}")

        if c.get("type") not in VALID_TYPES:
            raise ConfigError(f"[{cid}] type 無效：{c.get('type')}")
        mode = c.get("input_mode")
        if mode not in VALID_INPUT_MODES:
            raise ConfigError(f"[{cid}] input_mode 無效：{mode}")

        win = c.get("win") or {}
        kind = win.get("kind")
        if kind not in VALID_WIN_KINDS:
            raise ConfigError(f"[{cid}] win.kind 無效：{kind}")
        if kind not in _MODE_TO_KINDS[mode]:
            raise ConfigError(
                f"[{cid}] input_mode={mode} 與 win.kind={kind} 不相容"
                f"（允許：{sorted(_MODE_TO_KINDS[mode])}）"
            )

        if mode == "weblab" and not c.get("lab_url"):
            raise ConfigError(f"[{cid}] weblab 題型需要 lab_url")

        sp = c.get("system_prompt")
        # defense 與 weblab 都不跟 LLM 對話，因此不需要 system_prompt / {{FLAG}}。
        if mode not in ("defense", "weblab"):
            if not sp or not isinstance(sp, str):
                raise ConfigError(f"[{cid}] 缺少 system_prompt")
            # 需要 canary 的題型必須有 {{FLAG}} 佔位（spec §6）
            needs_flag = kind in {"leak", "indirect_leak", "tool_exfil"}
            if needs_flag and "{{FLAG}}" not in sp:
                raise ConfigError(f"[{cid}] system_prompt 缺少 {{{{FLAG}}}} 佔位符")
            if not needs_flag and "{{FLAG}}" in sp:
                raise ConfigError(f"[{cid}] win.kind={kind} 不應使用 {{{{FLAG}}}}")

        if mode == "locked_doc":
            dc = c.get("data_channel")
            if not isinstance(dc, dict) or "{doc}" not in str(dc.get("wrap", "")):
                raise ConfigError(f"[{cid}] locked_doc 需要 data_channel.wrap 且含 {{doc}}")
        if kind == "tool_exfil":
            if not c.get("tools"):
                raise ConfigError(f"[{cid}] win.kind=tool_exfil 需要 tools 定義")
            if not win.get("attacker_email"):
                raise ConfigError(f"[{cid}] win.kind=tool_exfil 需要 attacker_email")
        if kind == "tool_call":
            if not c.get("tools"):
                raise ConfigError(f"[{cid}] win.kind=tool_call 需要 tools 定義")
            if not win.get("tool_name"):
                raise ConfigError(f"[{cid}] win.kind=tool_call 需要 tool_name")
            names = {
                (t.get("function") or {}).get("name")
                for t in c.get("tools") or []
                if isinstance(t, dict)
            }
            if win["tool_name"] not in names:
                raise ConfigError(
                    f"[{cid}] win.tool_name={win['tool_name']!r} 不在 tools 定義中（{sorted(n for n in names if n)}）"
                )

        import re as _re

        for field in ("defense", "input_filter"):
            for rule in c.get(field) or []:
                if not isinstance(rule, dict) or rule.get("filter") not in KNOWN_FILTERS:
                    raise ConfigError(f"[{cid}] 未知的 {field} filter：{rule!r}")
                if rule["filter"] in {"block_regex", "strip_regex"}:
                    try:
                        _re.compile(str(rule.get("value", "")))
                    except _re.error as exc:
                        raise ConfigError(
                            f"[{cid}] {field} regex 無效：{rule.get('value')!r} ({exc})"
                        )
        # 輸入端只有「擋下」有意義；改寫類過濾器放這裡會讓行為難以理解
        for rule in c.get("input_filter") or []:
            if rule.get("filter") not in {"block_substring", "block_regex"}:
                raise ConfigError(
                    f"[{cid}] input_filter 只支援 block_substring / block_regex，"
                    f"收到 {rule.get('filter')!r}"
                )


def load_challenges(path: Path) -> ChallengeSet:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate(raw)
    cs = ChallengeSet(raw)
    log.info(
        "已載入 %d 道題目（main=%d, final=%d）",
        len(cs.all),
        sum(1 for c in cs.all if c.release_stage != "final"),
        sum(1 for c in cs.all if c.release_stage == "final"),
    )
    return cs
