"""OpenRouter 介接（spec §5 / 附錄 A）。

硬性原則：
- OPENROUTER_API_KEY 只在這裡使用，永不進 log、永不進回應。
- 逾時 20s、最多重試 2 次（指數退避）。
- provider 5xx / 逾時 → 丟 LLMError，由上層轉成友善訊息，不外露 stack trace。
- 全域 token 預算由 budget_check / budget_add callback 交給 db 層記帳。
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Awaitable, Callable

import httpx

from .config import Settings

log = logging.getLogger("ctf.llm")


class LLMError(RuntimeError):
    """對外一律轉成友善訊息，不帶上游細節。"""

    def __init__(self, code: str, message: str, *, internal: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.internal = internal


class BudgetExceeded(LLMError):
    def __init__(self) -> None:
        super().__init__(
            "budget_exceeded",
            "平臺今日的模型用量已達上限，請通知工作人員。",
        )


class LLMClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self._sem = asyncio.Semaphore(max(1, settings.llm_max_concurrency))
        self._client: httpx.AsyncClient | None = None
        # 由 main.py 於啟動時注入（避免 llm 直接相依 db）
        self.budget_check: Callable[[], Awaitable[bool]] | None = None
        self.budget_add: Callable[[int], Awaitable[None]] | None = None

    async def startup(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.s.llm_timeout),
                # spec §3.3：後端對外只允許 openrouter.ai。
                # 這裡再加一道 app 層保險：不跟隨 redirect，避免被導去別的主機。
                follow_redirects=False,
                limits=httpx.Limits(
                    max_connections=self.s.llm_max_concurrency + 8,
                    max_keepalive_connections=self.s.llm_max_concurrency,
                ),
            )

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.s.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.s.http_referer,
            "X-Title": self.s.x_title,
        }

    async def chat(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        session_id: str,
        temperature: float = 0.3,
        max_tokens: int = 512,
        tools: list[dict] | None = None,
        provider: dict | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """回傳 {"reply": str, "tool_calls": list|None, "usage": dict, "tokens": int}。"""
        if self.s.fake_llm:
            return _fake_reply(system_prompt, messages, tools)

        if not self.s.openrouter_api_key:
            raise LLMError("no_api_key", "後端尚未設定模型金鑰，請通知工作人員。")

        if self.budget_check is not None and not await self.budget_check():
            raise BudgetExceeded()

        body: dict[str, Any] = {
            "model": model or self.s.model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            # sticky routing + prompt cache（spec §5）：system prompt 重複度高
            "session_id": session_id,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if provider:
            body["provider"] = provider

        await self.startup()
        assert self._client is not None

        last_exc: Exception | None = None
        for attempt in range(self.s.llm_max_retries + 1):
            try:
                async with self._sem:
                    resp = await self._client.post(
                        self.s.openrouter_url, headers=self._headers(), json=body
                    )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                log.warning("OpenRouter 連線失敗（第 %d 次）：%s", attempt + 1, type(exc).__name__)
            else:
                if resp.status_code == 200:
                    return await self._parse(resp)
                if resp.status_code in (408, 429, 500, 502, 503, 504):
                    last_exc = RuntimeError(f"upstream {resp.status_code}")
                    log.warning(
                        "OpenRouter 回 %s（第 %d 次），準備重試", resp.status_code, attempt + 1
                    )
                else:
                    # 4xx（設定錯誤、金鑰無效…）重試沒意義。
                    # 注意：body 可能含金鑰相關訊息，只記 status code。
                    log.error("OpenRouter 回不可重試的狀態碼 %s", resp.status_code)
                    raise LLMError(
                        "upstream_error",
                        "模型服務暫時無法使用，請稍後再試或通知工作人員。",
                        internal=f"status={resp.status_code}",
                    )

            if attempt < self.s.llm_max_retries:
                backoff = (2 ** attempt) * 0.5 + random.random() * 0.3
                await asyncio.sleep(backoff)

        raise LLMError(
            "upstream_unavailable",
            "模型服務忙碌或逾時，請稍後再試一次。",
            internal=type(last_exc).__name__ if last_exc else "unknown",
        )

    async def _parse(self, resp: httpx.Response) -> dict[str, Any]:
        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMError("bad_response", "模型回應格式異常，請再試一次。", internal=str(exc))

        choices = data.get("choices") or []
        if not choices:
            err = data.get("error") or {}
            log.error("OpenRouter 回應無 choices：code=%s", err.get("code"))
            raise LLMError("bad_response", "模型沒有回應內容，請再試一次。")

        msg = choices[0].get("message") or {}
        usage = data.get("usage") or {}
        tokens = int(usage.get("total_tokens") or 0)
        if not tokens:
            tokens = int(usage.get("prompt_tokens") or 0) + int(
                usage.get("completion_tokens") or 0
            )
        if self.budget_add is not None and tokens:
            await self.budget_add(tokens)

        return {
            "reply": msg.get("content") or "",
            "tool_calls": msg.get("tool_calls"),
            "usage": usage,
            "tokens": tokens,
        }


def _fake_reply(system_prompt: str, messages: list[dict], tools: list[dict] | None) -> dict:
    """FAKE_LLM=1 時的離線回覆：把 system prompt 原樣吐回。

    用途：前端開發、沒有金鑰時的煙霧測試。**絕不可在活動中啟用**（會直接送分）。
    """
    last = messages[-1]["content"] if messages else ""
    return {
        "reply": f"[FAKE_LLM] 我收到的系統設定是：{system_prompt}\n你說：{last[:200]}",
        "tool_calls": None,
        "usage": {"total_tokens": 0},
        "tokens": 0,
    }
