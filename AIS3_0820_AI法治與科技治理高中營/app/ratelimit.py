"""行程內滑動視窗限流（spec §3.6）。

ASSUMPTION: 單一 uvicorn worker（見 Dockerfile）。多 worker 會讓每個 worker
各自計數，限流強度變成 N 倍鬆；要多 worker 請改用 Redis。
"""

from __future__ import annotations

import time
from collections import deque


class SlidingWindow:
    def __init__(self, window_seconds: float = 60.0, max_entries: int = 20_000):
        self.window = window_seconds
        self.max_entries = max_entries
        self._hits: dict[str, deque[float]] = {}
        self._last_gc = 0.0

    def _gc(self, now: float) -> None:
        if now - self._last_gc < 60 or len(self._hits) < self.max_entries // 2:
            return
        self._last_gc = now
        stale = [k for k, dq in self._hits.items() if not dq or now - dq[-1] > self.window * 4]
        for k in stale:
            self._hits.pop(k, None)

    def check(self, key: str, limit: int) -> tuple[bool, int, float]:
        """回傳 (是否允許, 這個視窗還剩幾次, 幾秒後可重試)。不消耗額度。"""
        now = time.time()
        dq = self._hits.get(key)
        if dq is None:
            return True, limit, 0.0
        while dq and now - dq[0] > self.window:
            dq.popleft()
        remaining = limit - len(dq)
        if remaining > 0:
            return True, remaining, 0.0
        retry_after = max(0.0, self.window - (now - dq[0]))
        return False, 0, retry_after

    def hit(self, key: str, limit: int) -> tuple[bool, int, float]:
        """檢查並消耗一次額度。"""
        now = time.time()
        self._gc(now)
        dq = self._hits.setdefault(key, deque())
        while dq and now - dq[0] > self.window:
            dq.popleft()
        if len(dq) >= limit:
            return False, 0, max(0.0, self.window - (now - dq[0]))
        dq.append(now)
        return True, limit - len(dq), 0.0

    def reset(self) -> None:
        self._hits.clear()
