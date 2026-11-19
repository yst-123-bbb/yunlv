"""C-CACHE@1 分层缓存：TTL 三档常量、读写、过期与命名空间清理。"""

from __future__ import annotations

import time

from infra.cache import TTL_DYNAMIC, TTL_SEMI_STATIC, TTL_STATIC, TTL_TRANSPORT, namespaced


def test_ttl_constants():
    assert TTL_STATIC == 90 * 86400
    assert TTL_SEMI_STATIC == 30 * 86400
    assert TTL_DYNAMIC == 600
    assert TTL_TRANSPORT == 600


def test_namespaced():
    assert namespaced("amap", "poi:北京") == "amap:poi:北京"


def test_set_get_roundtrip(file_cache):
    value = {"a": 1, "b": ["x", "y"]}
    file_cache.set("ns:key", value, ttl_s=TTL_DYNAMIC)
    assert file_cache.get("ns:key") == value


def test_missing_key_returns_none(file_cache):
    assert file_cache.get("ns:absent") is None


def test_overwrite_returns_latest_value(file_cache):
    file_cache.set("ns:key", "old", ttl_s=TTL_DYNAMIC)
    file_cache.set("ns:key", "new", ttl_s=TTL_DYNAMIC)
    assert file_cache.get("ns:key") == "new"


def test_ttl_expired_returns_none(file_cache):
    file_cache.set("ns:short", "v", ttl_s=0)
    time.sleep(0.01)
    assert file_cache.get("ns:short") is None


def test_delete_removes_key(file_cache):
    file_cache.set("ns:del", 1, ttl_s=TTL_DYNAMIC)
    file_cache.delete("ns:del")
    assert file_cache.get("ns:del") is None


def test_clear_namespace_only_clears_target(file_cache):
    file_cache.set("ns1:a", 1, ttl_s=TTL_DYNAMIC)
    file_cache.set("ns1:b", 2, ttl_s=TTL_DYNAMIC)
    file_cache.set("ns2:a", 3, ttl_s=TTL_DYNAMIC)

    file_cache.clear_namespace("ns1")

    assert file_cache.get("ns1:a") is None
    assert file_cache.get("ns1:b") is None
    assert file_cache.get("ns2:a") == 3