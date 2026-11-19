"""把 data/*.py 中的兜底数据迁移为 SQLite 实体（C-SEED@1）。

只读引用 data/*.py，不修改其中任何文件；写入统一标注 `source="legacy"`、
`confidence=0.3`，供后续真实 Provider 覆盖时作为低可信度基线。
"""

from __future__ import annotations

import importlib.util
import logging
from datetime import date
from pathlib import Path
from typing import Any, Callable

from datastore import repository

logger = logging.getLogger(__name__)

SOURCE = "legacy"
CONFIDENCE = 0.3

_ATTRACTION_DB = "_ATTRACTION_DB"
_ATTRACTION_FIELDS = (
    "name", "address", "ticket_price", "open_time", "tags",
    "features", "tips", "indoor", "likes",
)
_FOOD_DB = "_FOOD_DB"
_FOOD_FIELDS = (
    "name", "address", "cuisine", "avg_price", "signature",
    "tags", "reviews", "tips", "likes",
)
_HOTEL_DB = "_HOTEL_DB"
_HOTEL_FIELDS = (
    "name", "room_type", "price", "address", "facilities",
    "reviews", "tips", "distance", "location",
)


def load_all(conn, data_dir: str = "data") -> dict[str, int]:
    """导入五类旧数据，返回各品类新建实体条数。

    重复执行时实体已存在，计数为 0，但实体总数不变。
    """
    fetched_at = f"{date.today().isoformat()}T00:00:00+08:00"
    counters = {"attraction": 0, "food": 0, "hotel": 0, "train": 0, "flight": 0}
    loaders: tuple[tuple[str, Callable[[Any, str, str], int]], ...] = (
        ("attraction", _load_attraction),
        ("food", _load_food),
        ("hotel", _load_hotel),
        ("train", _load_train),
        ("flight", _load_flight),
    )
    for key, loader in loaders:
        try:
            counters[key] = loader(conn, data_dir, fetched_at)
        except Exception as exc:
            logger.warning("legacy seed %s failed: %s", key, exc)
        conn.commit()
    return counters


def _load_attraction(conn, data_dir: str, fetched_at: str) -> int:
    db = getattr(_load_module(data_dir, "attraction_data"), _ATTRACTION_DB, {}) or {}
    return _load_records(
        conn, db, type_="attraction", field_names=_ATTRACTION_FIELDS, fetched_at=fetched_at
    )


def _load_food(conn, data_dir: str, fetched_at: str) -> int:
    db = getattr(_load_module(data_dir, "food_data"), _FOOD_DB, {}) or {}
    return _load_records(
        conn, db, type_="restaurant", field_names=_FOOD_FIELDS, fetched_at=fetched_at
    )


def _load_hotel(conn, data_dir: str, fetched_at: str) -> int:
    db = getattr(_load_module(data_dir, "hotel_data"), _HOTEL_DB, {}) or {}
    return _load_records(
        conn, db, type_="hotel", field_names=_HOTEL_FIELDS, fetched_at=fetched_at
    )


def _load_train(conn, data_dir: str, fetched_at: str) -> int:
    module = _load_module(data_dir, "train_data")
    pairs = getattr(module, "_PAIRS", {}) or {}
    total = 0
    for route_key, rows in pairs.items():
        dep, sep, dest = str(route_key).partition("-")
        if not sep or not dep or not dest:
            logger.warning("skip malformed train route key: %r", route_key)
            continue
        trains = []
        for row in rows:
            if not isinstance(row, (tuple, list)) or len(row) < 8:
                logger.warning("skip malformed train row in %s: %r", route_key, row)
                continue
            code, from_station, to_station, depart_time, arrive_time, duration, second_class, first_class = row[:8]
            trains.append({
                "code": code,
                "from_station": from_station,
                "to_station": to_station,
                "depart_time": depart_time,
                "arrive_time": arrive_time,
                "duration": duration,
                "second_class": second_class,
                "first_class": first_class,
            })
        total += _write_entity(
            conn, type_="train_route", city=dep, name=f"{dep}-{dest}",
            fields={"trains": trains}, fetched_at=fetched_at,
        )
    return total


def _load_flight(conn, data_dir: str, fetched_at: str) -> int:
    module = _load_module(data_dir, "flight_data")
    rows = getattr(module, "_TIMES", ()) or ()
    build = getattr(module, "get_flight_backup", None)
    total = 0
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 2:
            logger.warning("skip malformed flight route row: %r", row)
            continue
        dep, dest = str(row[0]), str(row[1])
        try:
            routes = build(dep, dest) if callable(build) else []
        except Exception as exc:
            logger.warning("legacy seed flight routes failed %s-%s: %s", dep, dest, exc)
            continue
        total += _write_entity(
            conn, type_="flight_route", city=dep, name=f"{dep}-{dest}",
            fields={"routes": routes}, fetched_at=fetched_at,
        )
    return total


def _load_records(
    conn, db: dict, *, type_: str, field_names: tuple[str, ...], fetched_at: str
) -> int:
    total = 0
    for city, records in db.items():
        for record in records:
            if not isinstance(record, dict):
                logger.warning("skip malformed %s record in %s: %r", type_, city, record)
                continue
            name = str(record.get("name") or "").strip()
            if not name:
                logger.warning("skip nameless %s record in %s", type_, city)
                continue
            fields = {key: record[key] for key in field_names if key in record}
            fields["name"] = name
            total += _write_entity(
                conn, type_=type_, city=str(city), name=name,
                fields=fields, fetched_at=fetched_at,
            )
    return total


def _write_entity(
    conn, *, type_: str, city: str, name: str, fields: dict[str, Any], fetched_at: str
) -> int:
    """写入单个实体，返回 1 表示新建实体，0 表示已存在或写入失败。"""
    try:
        entity_id = repository.get_entity_id(conn, type=type_, city=city, name=name)
        is_new = entity_id is None
        if is_new:
            entity_id = repository.upsert_entity(conn, type=type_, city=city, name=name)
        for field_name, value in fields.items():
            repository.upsert_field(
                conn,
                entity_id=entity_id,
                field_name=field_name,
                value=value,
                source=SOURCE,
                source_url=None,
                confidence=CONFIDENCE,
                fetched_at=fetched_at,
            )
        return 1 if is_new else 0
    except Exception as exc:
        logger.warning(
            "legacy seed write failed type=%s city=%s name=%s: %s", type_, city, name, exc
        )
        return 0


def _load_module(data_dir: str, module_name: str):
    path = Path(data_dir) / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"_cloudtrip_seed_{module_name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载数据模块: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module