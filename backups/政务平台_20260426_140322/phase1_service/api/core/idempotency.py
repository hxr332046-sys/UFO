"""幂等性缓存：相同 case_id 短时间内多次调用返回同一个 busiId，避免在服务端产生垃圾草稿。

简单内存 TTL 缓存，适合单进程。生产环境可替换为 Redis。
"""
from __future__ import annotations

import time
import threading
from typing import Any, Dict, Optional

# 默认 TTL：30 分钟
DEFAULT_TTL_SEC = 30 * 60


class IdempotencyCache:
    def __init__(self, ttl: int = DEFAULT_TTL_SEC):
        self._ttl = ttl
        self._store: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def get(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._store.get(case_id)
            if entry is None:
                return None
            ts, result = entry
            if time.time() - ts > self._ttl:
                del self._store[case_id]
                return None
            return result

    def put(self, case_id: str, result: Dict[str, Any]) -> None:
        with self._lock:
            self._store[case_id] = (time.time(), result)

    def invalidate(self, case_id: str) -> bool:
        with self._lock:
            return self._store.pop(case_id, None) is not None

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            valid = sum(1 for ts, _ in self._store.values() if now - ts <= self._ttl)
            return {"total": len(self._store), "valid": valid, "ttl_sec": self._ttl}


# 单例
_cache = IdempotencyCache()

def get_cache() -> IdempotencyCache:
    return _cache
