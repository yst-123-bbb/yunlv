"""Provider 降级链测试：主源成功、主源异常降级、全失败返回空、熔断跳过。"""

from __future__ import annotations

import pytest

import providers.registry as registry_module
from providers.registry import ProviderRegistry


class _FakeBreaker:
    def __init__(self, open_names: tuple[str, ...] = ()) -> None:
        self._open = set(open_names)
        self.successes: list[str] = []
        self.failures: list[str] = []

    def allow(self, provider: str) -> bool:
        return provider not in self._open

    def record_success(self, provider: str) -> None:
        self.successes.append(provider)

    def record_failure(self, provider: str) -> None:
        self.failures.append(provider)


class _FakePlaceProvider:
    def __init__(
        self,
        name: str,
        results: list[object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self._results = list(results or [])
        self._error = error
        self.calls = 0

    def search(self, city: str, keyword: str, limit: int = 15) -> list[object]:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return list(self._results)


@pytest.fixture
def fake_breaker(monkeypatch: pytest.MonkeyPatch) -> _FakeBreaker:
    stub = _FakeBreaker()
    monkeypatch.setattr(registry_module, "breaker", stub)
    return stub


def test_primary_source_hit_stops_chain(fake_breaker: _FakeBreaker) -> None:
    primary = _FakePlaceProvider("amap", results=[{"name": "故宫"}])
    backup = _FakePlaceProvider("store", results=[{"name": "备选"}])
    reg = ProviderRegistry()
    reg.register("place", primary)
    reg.register("place", backup)

    results, attempted = reg.search("place", city="北京", keyword="故宫")

    assert results == [{"name": "故宫"}]
    assert attempted == ["amap"]
    assert backup.calls == 0
    assert fake_breaker.successes == ["amap"]
    assert fake_breaker.failures == []


def test_primary_failure_falls_back_to_backup(fake_breaker: _FakeBreaker) -> None:
    primary = _FakePlaceProvider("amap", error=RuntimeError("boom"))
    backup = _FakePlaceProvider("store", results=[{"name": "本地兜底"}])
    reg = ProviderRegistry()
    reg.register("place", primary)
    reg.register("place", backup)

    results, attempted = reg.search("place", city="北京", keyword="故宫")

    assert results == [{"name": "本地兜底"}]
    assert attempted == ["amap", "store"]
    assert primary.calls == 1
    assert backup.calls == 1
    assert fake_breaker.failures == ["amap"]
    assert fake_breaker.successes == ["store"]


def test_all_sources_fail_returns_empty(fake_breaker: _FakeBreaker) -> None:
    primary = _FakePlaceProvider("amap", error=RuntimeError("boom"))
    backup = _FakePlaceProvider("store", results=[])
    reg = ProviderRegistry()
    reg.register("place", primary)
    reg.register("place", backup)

    results, attempted = reg.search("place", city="北京", keyword="故宫")

    assert results == []
    assert attempted == ["amap", "store"]
    assert fake_breaker.failures == ["amap"]


def test_open_breaker_provider_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry_module, "breaker", _FakeBreaker(open_names=("amap",)))
    primary = _FakePlaceProvider("amap", results=[{"name": "不应命中"}])
    backup = _FakePlaceProvider("store", results=[{"name": "本地兜底"}])
    reg = ProviderRegistry()
    reg.register("place", primary)
    reg.register("place", backup)

    results, attempted = reg.search("place", city="北京", keyword="故宫")

    assert results == [{"name": "本地兜底"}]
    assert attempted == ["store"]
    assert primary.calls == 0