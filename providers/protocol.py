"""Provider 协议：四类数据源对外统一的调用接口。"""

from __future__ import annotations

from typing import Protocol

from providers.models import NoteItem, PlaceItem, TicketOffer, TransportOffer


class PlaceProvider(Protocol):
    name: str

    def search(self, city: str, keyword: str, limit: int = 15) -> list[PlaceItem]: ...


class TransportProvider(Protocol):
    name: str

    def search(self, origin: str, dest: str, date: str) -> list[TransportOffer]: ...


class TicketProvider(Protocol):
    name: str

    def search(self, place_name: str, city: str) -> list[TicketOffer]: ...


class NoteProvider(Protocol):
    name: str

    def fetch(self, url: str) -> NoteItem: ...