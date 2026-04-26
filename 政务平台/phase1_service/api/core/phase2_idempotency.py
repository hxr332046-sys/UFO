"""Phase 2 专用幂等缓存。

Phase 2 和 Phase 1 的幂等语义不同：
- Phase 1 "拿 busiId" 是纯读（或一次性写入），重复调用返回同一 busiId 没副作用
- Phase 2 "推进状态机" 是写操作，重复调用会在服务端产生二次写入（saveShareholder/submit）

所以 Phase 2 的幂等 key 不只是 case，而是 (busi_id, stop_after, start_from, step 签名)。
短 TTL（5 分钟）用于防止客户端重试风暴，但不妨碍真正需要重跑的场景。
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Dict, Optional

DEFAULT_TTL_SEC = 5 * 60  # 5 分钟


class Phase2IdempotencyCache:
    def __init__(self, ttl: int = DEFAULT_TTL_SEC):
        self._ttl = ttl
        self._store: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def make_key(case_dict: Dict[str, Any], busi_id: str, *,
                  start_from: int, stop_after: int, name_id: Optional[str]) -> str:
        """根据 (case 指纹 + busi_id + 步骤窗口 + name_id) 生成幂等 key。"""
        payload = {
            "name_mark": case_dict.get("name_mark", ""),
            "entType": case_dict.get("entType_default", ""),
            "dist_codes": case_dict.get("phase1_dist_codes", []),
            "busi_id": busi_id,
            "start_from": start_from,
            "stop_after": stop_after,
            "name_id": name_id or "",
        }
        s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, result = entry
            if time.time() - ts > self._ttl:
                del self._store[key]
                return None
            return result

    def put(self, key: str, result: Dict[str, Any]) -> None:
        with self._lock:
            self._store[key] = (time.time(), result)

    def invalidate(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            valid = sum(1 for ts, _ in self._store.values() if now - ts <= self._ttl)
            return {"total": len(self._store), "valid": valid, "ttl_sec": self._ttl}


# 单例
_cache = Phase2IdempotencyCache()


def get_phase2_cache() -> Phase2IdempotencyCache:
    return _cache
