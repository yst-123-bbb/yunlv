"""C-GUARD@1 令牌桶 / 并发合并 / 熔断。"""

from __future__ import annotations

import threading
import time

import pytest

from infra.ratelimit import CircuitBreaker, RateLimiter, breaker, limiter, singleflight


def test_rate_limiter_enforces_min_interval():
    guard = RateLimiter(min_interval_s=0.05)

    start = time.monotonic()
    guard.acquire("example.com")
    guard.acquire("example.com")
    elapsed = time.monotonic() - start

    assert elapsed >= 0.05


def test_singleflight_merges_concurrent_calls():
    calls = 0
    entered = threading.Event()
    gate = threading.Event()

    def fn():
        nonlocal calls
        calls += 1
        entered.set()
        gate.wait(timeout=5)
        return "shared"

    results: list[str] = []

    def worker():
        results.append(singleflight("merge-key", fn))

    first = threading.Thread(target=worker)
    first.start()
    assert entered.wait(timeout=5)

    second = threading.Thread(target=worker)
    second.start()
    time.sleep(0.2)
    gate.set()

    first.join(timeout=5)
    second.join(timeout=5)

    assert calls == 1
    assert results == ["shared", "shared"]


def test_singleflight_clears_key_after_call():
    calls = 0

    def fn():
        nonlocal calls
        calls += 1
        return calls

    assert singleflight("seq-key", fn) == 1
    assert singleflight("seq-key", fn) == 2


def test_singleflight_propagates_error_and_clears_key():
    def boom():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        singleflight("err-key", boom)

    assert singleflight("err-key", lambda: "ok") == "ok"


def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=2, cooldown_s=60)

    cb.record_failure("amap")
    assert cb.allow("amap") is True

    cb.record_failure("amap")
    assert cb.state("amap") == "open"
    assert cb.allow("amap") is False


def test_circuit_breaker_success_resets_count():
    cb = CircuitBreaker(failure_threshold=2, cooldown_s=60)

    cb.record_failure("amap")
    cb.record_success("amap")
    cb.record_failure("amap")

    assert cb.state("amap") == "closed"
    assert cb.allow("amap") is True


def test_circuit_breaker_isolates_providers():
    cb = CircuitBreaker(failure_threshold=1, cooldown_s=60)

    cb.record_failure("train_12306")

    assert cb.allow("train_12306") is False
    assert cb.allow("ticket_gov") is True


def test_circuit_breaker_half_open_after_cooldown():
    cb = CircuitBreaker(failure_threshold=1, cooldown_s=0.2)

    cb.record_failure("amap")
    assert cb.allow("amap") is False

    time.sleep(0.25)
    assert cb.allow("amap") is True

    cb.record_failure("amap")
    assert cb.allow("amap") is False


def test_module_singletons_exist():
    assert isinstance(limiter, RateLimiter)
    assert isinstance(breaker, CircuitBreaker)