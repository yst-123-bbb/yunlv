"""本地兜底 Provider：从 SQLite 的 legacy 数据读取地点、交通与门票。

legacy 数据由 `datastore.seed_loader` 写入，可信度固定 0.3；命中即返回，未命中
返回空列表并由降级链决定后续行为。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from datastore import repository
from datastore.db import connect
from providers.models import PlaceItem, TicketOffer, TransportOffer

SOURCE = "store"
CONFIDENCE = 0.3
TRAIN_SOURCE_URL = "https://www.12306.cn"
PLACE_TYPES = ("attraction", "restaurant", "hotel")

_TZ = timezone(timedelta(hours=8))
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _now_iso() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER.search(str(value))
    return float(match.group()) if match else None


def _duration_minutes(value: Any) -> int:
    text = str(value or "").strip()
    hours = re.search(r"(\d+)\s*h", text)
    minutes = re.search(r"(\d+)\s*m", text)
    total = (int(hours.group(1)) * 60 if hours else 0) + (int(minutes.group(1)) if minutes else 0)
    if total == 0:
        number = _to_float(value)
        total = int(number) if number is not None else 0
    return total


def _economy_price(cabin: Any) -> float | None:
    if isinstance(cabin, dict):
        for key in ("经济舱", "超级经济舱"):
            if key in cabin:
                price = _to_float(cabin[key])
                if price is not None:
                    return price
        for value in cabin.values():
            price = _to_float(value)
            if price is not None:
                return price
        return None
    return _to_float(cabin)


def _entity_fields(conn, entity: dict[str, Any]) -> dict[str, Any]:
    fields = entity.get("fields")
    return fields if isinstance(fields, dict) else repository.read_entity(conn, int(entity["entity_id"]))


class _StoreBase:
    """共享 SQLite 连接策略：每次查询打开/关闭独立连接。"""

    name = "store"

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path


class StorePlaceProvider(_StoreBase):
    def search(self, city: str, keyword: str, limit: int = 15) -> list[PlaceItem]:
        fetched_at = _now_iso()
        results: list[PlaceItem] = []
        conn = connect(self.db_path)
        try:
            for place_type in PLACE_TYPES:
                entities = repository.search_entities(
                    conn,
                    type=place_type,
                    city=city,
                    keyword=(keyword or "").strip() or None,
                    limit=limit,
                )
                for entity in entities:
                    fields = _entity_fields(conn, entity)
                    results.append(
                        PlaceItem(
                            name=str(fields.get("name") or entity["name"]),
                            type=place_type,
                            city=str(entity["city"]),
                            address=str(fields.get("address") or ""),
                            open_time=str(fields.get("open_time") or ""),
                            avg_price=self._avg_price(fields),
                            indoor=bool(fields.get("indoor") or False),
                            source=SOURCE,
                            source_url="",
                            fetched_at=fetched_at,
                            confidence=CONFIDENCE,
                        )
                    )
                    if len(results) >= limit:
                        return results
        finally:
            conn.close()
        return results

    @staticmethod
    def _avg_price(fields: dict[str, Any]) -> float | None:
        return _to_float(fields.get("avg_price", fields.get("price")))


class StoreTransportProvider(_StoreBase):
    def search(self, origin: str, dest: str, date: str) -> list[TransportOffer]:
        fetched_at = _now_iso()
        conn = connect(self.db_path)
        try:
            trains = self._route_rows(conn, "train_route", origin, dest)
            if trains:
                return [self._train_offer(row, fetched_at) for row in trains if isinstance(row, dict)]
            flights = self._route_rows(conn, "flight_route", origin, dest)
            if flights:
                return [self._flight_offer(row, fetched_at) for row in flights if isinstance(row, dict)]
        finally:
            conn.close()
        return []

    @staticmethod
    def _route_rows(conn, route_type: str, origin: str, dest: str) -> list[Any]:
        field_name = "trains" if route_type == "train_route" else "routes"
        for dep, arr in ((origin, dest), (dest, origin)):
            entity_id = repository.get_entity_id(
                conn, type=route_type, city=dep, name=f"{dep}-{arr}"
            )
            if entity_id is None:
                continue
            rows = repository.read_entity(conn, entity_id).get(field_name) or []
            if rows:
                return list(rows)
        return []

    @staticmethod
    def _train_offer(row: dict[str, Any], fetched_at: str) -> TransportOffer:
        return TransportOffer(
            mode="train",
            code=str(row.get("code") or ""),
            from_station=str(row.get("from_station") or ""),
            to_station=str(row.get("to_station") or ""),
            depart_time=str(row.get("depart_time") or ""),
            arrive_time=str(row.get("arrive_time") or ""),
            duration_min=_duration_minutes(row.get("duration")),
            price_cny=_to_float(row.get("second_class")) or 0.0,
            seat_class="二等座",
            source=SOURCE,
            source_url=TRAIN_SOURCE_URL,
            fetched_at=fetched_at,
            confidence=CONFIDENCE,
        )

    @staticmethod
    def _flight_offer(row: dict[str, Any], fetched_at: str) -> TransportOffer:
        return TransportOffer(
            mode="flight",
            code=str(row.get("flight_no") or ""),
            from_station=str(row.get("dep_airport") or ""),
            to_station=str(row.get("arr_airport") or ""),
            depart_time=str(row.get("dep_time") or ""),
            arrive_time=str(row.get("arr_time") or ""),
            duration_min=_duration_minutes(row.get("duration")),
            price_cny=_economy_price(row.get("cabin")) or 0.0,
            seat_class="经济舱",
            source=SOURCE,
            source_url="",
            fetched_at=fetched_at,
            confidence=CONFIDENCE,
        )


class StoreTicketProvider(_StoreBase):
    def search(self, place_name: str, city: str) -> list[TicketOffer]:
        name = str(place_name or "").strip()
        if not name:
            return []
        fetched_at = _now_iso()
        conn = connect(self.db_path)
        try:
            entity_id = repository.get_entity_id(conn, type="attraction", city=city, name=name)
            if entity_id is not None:
                entity = {"entity_id": entity_id, "name": name}
            else:
                hits = repository.search_entities(
                    conn, type="attraction", city=city, keyword=name, limit=1
                )
                if not hits:
                    return []
                entity = hits[0]
            fields = _entity_fields(conn, entity)
            resolved_name = str(fields.get("name") or entity["name"])
        finally:
            conn.close()

        price = _to_float(fields.get("ticket_price"))
        if price is None:
            return []
        return [
            TicketOffer(
                name=resolved_name,
                city=city,
                price_min=price,
                price_max=price,
                open_time=str(fields.get("open_time") or ""),
                source=SOURCE,
                source_url="",
                fetched_at=fetched_at,
                confidence=CONFIDENCE,
            )
        ]