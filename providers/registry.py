"""Provider 降级链注册表：按注册顺序尝试，取首个非空结果，跳过熔断中的 provider。"""

from __future__ import annotations

import time
from typing import Any, Literal

from infra.logging_setup import get_logger, log_event
from infra.ratelimit import breaker

ProviderKind = Literal["place", "transport", "ticket", "note"]
PROVIDER_KINDS: tuple[str, ...] = ("place", "transport", "ticket", "note")

_logger = get_logger("provider_registry")


class ProviderRegistry:
    def __init__(self) -> None:
        self._chains: dict[str, list[Any]] = {kind: [] for kind in PROVIDER_KINDS}

    def register(self, kind: ProviderKind, provider: Any) -> None:
        if kind not in self._chains:
            raise ValueError(f"unknown provider kind: {kind}")
        self._chains[kind].append(provider)

    def search(self, kind: ProviderKind, **kwargs: Any) -> tuple[list[Any], list[str]]:
        attempted: list[str] = []
        for provider in self._chains.get(kind, ()):
            name = getattr(provider, "name", type(provider).__name__)
            if not breaker.allow(name):
                log_event(_logger, "provider_skipped", provider=name, outcome="breaker_open")
                continue
            attempted.append(name)
            started = time.perf_counter()
            try:
                results = self._invoke(kind, provider, kwargs)
            except Exception as exc:
                breaker.record_failure(name)
                log_event(
                    _logger,
                    "provider_failed",
                    provider=name,
                    duration_ms=_elapsed_ms(started),
                    outcome="error",
                    error=f"{type(exc).__name__}: {exc}",
                )
                continue
            breaker.record_success(name)
            if results:
                log_event(
                    _logger,
                    "provider_hit",
                    provider=name,
                    duration_ms=_elapsed_ms(started),
                    outcome="ok",
                )
                return results, attempted
        return [], attempted

    @staticmethod
    def _invoke(kind: str, provider: Any, kwargs: dict[str, Any]) -> list[Any]:
        # note 类返回单个 NoteItem，统一包装成列表以便与其余三类共用降级逻辑
        if kind == "note":
            item = provider.fetch(**kwargs)
            return [item] if item is not None else []
        return list(provider.search(**kwargs) or [])


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def build_default_registry() -> ProviderRegistry:
    from providers.amap import AmapPlaceProvider
    from providers.notes_xhs import XhsNoteProvider
    from providers.store import (
        StorePlaceProvider,
        StoreTicketProvider,
        StoreTransportProvider,
    )
    from providers.ticket_gov import TicketGovProvider
    from providers.train_12306 import Train12306Provider

    reg = ProviderRegistry()
    reg.register("place", AmapPlaceProvider())
    reg.register("place", StorePlaceProvider())
    reg.register("transport", Train12306Provider())
    reg.register("transport", StoreTransportProvider())
    reg.register("ticket", TicketGovProvider())
    reg.register("ticket", StoreTicketProvider())
    reg.register("note", XhsNoteProvider())
    return reg


registry = build_default_registry()