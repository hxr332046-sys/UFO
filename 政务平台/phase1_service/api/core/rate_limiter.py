"""令牌桶 + D0029 熔断。进程内单例，保证对上游政务服务端的串行化/限速。"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class RateLimiterConfig:
    # 每分钟最多多少次 phase1_protocol_driver 完整执行
    max_drives_per_minute: int = 6
    # D0029 冷却
    d0029_cooldown_sec: int = 600
    d0029_threshold: int = 2


class AsyncTokenBucket:
    """按"每分钟 N 次"为上游限速。进程内全局单例。"""

    def __init__(self, cfg: RateLimiterConfig):
        self.cfg = cfg
        self._window_start = time.time()
        self._calls_in_window = 0
        self._cooldown_until: float = 0.0
        self._d0029_count = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            # 冷却期
            now = time.time()
            if now < self._cooldown_until:
                wait = self._cooldown_until - now
                await asyncio.sleep(wait)

            # 窗口滑动
            now = time.time()
            if now - self._window_start >= 60.0:
                self._window_start = now
                self._calls_in_window = 0

            if self._calls_in_window >= self.cfg.max_drives_per_minute:
                # 等到窗口结束
                wait = 60.0 - (now - self._window_start)
                if wait > 0:
                    await asyncio.sleep(wait)
                self._window_start = time.time()
                self._calls_in_window = 0
            self._calls_in_window += 1

    def report_success(self) -> None:
        self._d0029_count = 0

    def report_d0029(self) -> None:
        self._d0029_count += 1
        if self._d0029_count >= self.cfg.d0029_threshold:
            self._cooldown_until = time.time() + self.cfg.d0029_cooldown_sec
            self._d0029_count = 0


_singleton: AsyncTokenBucket | None = None


def get_limiter() -> AsyncTokenBucket:
    global _singleton
    if _singleton is None:
        _singleton = AsyncTokenBucket(RateLimiterConfig())
    return _singleton
