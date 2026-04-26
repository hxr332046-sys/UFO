"""单元测试：Phase 2 幂等缓存。"""
from __future__ import annotations

import time

import pytest


@pytest.fixture
def cache():
    """清新的幂等缓存实例（避免全局单例污染）。"""
    from phase1_service.api.core.phase2_idempotency import Phase2IdempotencyCache
    return Phase2IdempotencyCache(ttl=2)


class TestIdempotencyCache:
    def test_key_stable_same_input(self, cache):
        c1 = {"name": "X", "entType_default": "4540"}
        k1 = cache.make_key(c1, "BUSI_1", start_from=1, stop_after=25, name_id="N1")
        k2 = cache.make_key(c1, "BUSI_1", start_from=1, stop_after=25, name_id="N1")
        assert k1 == k2

    def test_key_differs_by_busi_id(self, cache):
        c = {"name": "X"}
        k1 = cache.make_key(c, "BUSI_1", start_from=1, stop_after=25, name_id=None)
        k2 = cache.make_key(c, "BUSI_2", start_from=1, stop_after=25, name_id=None)
        assert k1 != k2

    def test_key_differs_by_stop_after(self, cache):
        c = {"name": "X"}
        k1 = cache.make_key(c, "BUSI_1", start_from=1, stop_after=14, name_id=None)
        k2 = cache.make_key(c, "BUSI_1", start_from=1, stop_after=25, name_id=None)
        assert k1 != k2

    def test_put_get_roundtrip(self, cache):
        k = "my_key"
        v = {"success": True, "data": 42}
        cache.put(k, v)
        assert cache.get(k) == v

    def test_missing_returns_none(self, cache):
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self, cache):
        cache.put("k", {"v": 1})
        assert cache.get("k") is not None
        time.sleep(2.2)  # TTL=2s
        assert cache.get("k") is None

    def test_stats_tracks_entries(self, cache):
        cache.put("a", {"v": 1})
        cache.put("b", {"v": 2})
        stats = cache.stats()
        assert stats["total"] == 2
        assert stats["ttl_sec"] == 2
