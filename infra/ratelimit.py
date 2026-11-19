"""跨 provider 的限速、同键请求合并与熔断保护（C-GUARD@1）。"""

from __future__ import annotations

import threading
import time
from typing import Callable, Literal, TypeVar, cast

from infra.logging_setup import get_logger, log_event

T = TypeVar("T")

__all__ = ["RateLimiter", "singleflight", "CircuitBreaker", "limiter", "breaker"]

logger = get_logger(__name__)


class RateLimiter:
    """按 domain 独立限速：同域相邻两次 acquire 的返回时间差 >= min_interval_s。"""

    def __init__(self, min_interval_s: float = 2.0) -> None:
        self.min_interval_s = max(0.0, float(min_interval_s))
        self._lock = threading.Lock()
        self._domain_locks: dict[str, threading.Lock] = {}
        self._last_seen: dict[str, float] = {}

    def _lock_for(self, domain: str) -> threading.Lock:
        with self._lock:
            lock = self._domain_locks.get(domain)
            if lock is None:
                lock = threading.Lock()
                self._domain_locks[domain] = lock
            return lock

    def acquire(self, domain: str) -> None:
        # 每域独立加锁，慢域（sleep）不阻塞其他域
        with self._lock_for(domain):
            last = self._last_seen.get(domain, float("-inf"))
            wait = last + self.min_interval_s - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_seen[domain] = time.monotonic()


class _Flight:
    __slots__ = ("done", "result", "error")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: object = None
        self.error: BaseException | None = None


_flight_lock = threading.Lock()
_flights: dict[str, _Flight] = {}


def singleflight(key: str, fn: Callable[[], T]) -> T:
    """同 key 并发调用只执行一次 fn，其余调用者共享其结果或同一个异常实例。"""
    with _flight_lock:
        flight = _flights.get(key)
        leader = flight is None
        if leader:
            flight = _Flight()
            _flights[key] = flight

    assert flight is not None
    if not leader:
        flight.done.wait()
        if flight.error is not None:
            raise flight.error
        return cast(T, flight.result)

    try:
        flight.result = fn()
        return cast(T, flight.result)
    except BaseException as exc:
        flight.error = exc
        raise
    finally:
        with _flight_lock:
            _flights.pop(key, None)
        flight.done.set()


class _ProviderState:
    __slots__ = ("failures", "opened_at", "probing")

    def __init__(self) -> None:
        self.failures = 0
        self.opened_at: float | None = None
        self.probing = False


class CircuitBreaker:
    """按 provider 独立计数：连续失败达阈值后冷却 cooldown_s，冷却期满放行一次试探。"""

    def __init__(self, failure_threshold: int = 5, cooldown_s: float = 1800.0) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_s = max(0.0, float(cooldown_s))
        self._lock = threading.Lock()
        self._states: dict[str, _ProviderState] = {}

    def _state_of(self, provider: str) -> _ProviderState:
        state = self._states.get(provider)
        if state is None:
            state = _ProviderState()
            self._states[provider] = state
        return state

    def allow(self, provider: str) -> bool:
        half_opened = False
        with self._lock:
            state = self._state_of(provider)
            if state.opened_at is None:
                # 半开试探结果回写前不再放行，保证冷却期满只放行一次
                return not state.probing
            if time.monotonic() - state.opened_at < self.cooldown_s:
                return False
            state.opened_at = None
            state.failures = 0
            state.probing = True
            half_opened = True
        if half_opened:
            log_event(logger, "circuit_half_open", provider=provider, outcome="allow")
        return True

    def record_success(self, provider: str) -> None:
        was_open = False
        with self._lock:
            state = self._state_of(provider)
            was_open = state.opened_at is not None or state.probing
            state.failures = 0
            state.opened_at = None
            state.probing = False
        if was_open:
            log_event(logger, "circuit_closed", provider=provider, outcome="success")

    def record_failure(self, provider: str) -> None:
        opened = False
        failures = 0
        with self._lock:
            state = self._state_of(provider)
            state.failures += 1
            state.probing = False
            failures = state.failures
            if state.opened_at is None and state.failures >= self.failure_threshold:
                state.opened_at = time.monotonic()
                opened = True
        if opened:
            log_event(
                logger,
                "circuit_open",
                provider=provider,
                outcome="failure",
                failures=failures,
            )

    def state(self, provider: str) -> Literal["closed", "open"]:
        with self._lock:
            state = self._states.get(provider)
            if state is None or state.opened_at is None:
                return "closed"
            if time.monotonic() - state.opened_at >= self.cooldown_s:
                return "closed"
            return "open"


limiter = RateLimiter()
breaker = CircuitBreaker()