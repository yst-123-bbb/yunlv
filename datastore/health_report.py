"""数据体检报表：按城市与品类统计缺失率、过期率与冲突率。"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from infra.cache import TTL_DYNAMIC, TTL_STATIC

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "attraction": ("address", "open_time"),
    "restaurant": ("address", "avg_price"),
    "hotel": ("price", "address"),
    "train_route": ("routes",),
    "flight_route": ("routes",),
}

DEFAULT_TTL_S: dict[str, int] = {
    "attraction": TTL_STATIC,
    "restaurant": TTL_STATIC,
    "hotel": TTL_STATIC,
    "train_route": TTL_DYNAMIC,
    "flight_route": TTL_DYNAMIC,
}

CSV_COLUMNS = ("city", "category", "total", "missing_rate", "stale_rate", "conflict_rate")

_CST = timezone(timedelta(hours=8))


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # 数据规范要求带 +08:00，缺失时按东八区解释，避免与本地时区漂移混淆
        parsed = parsed.replace(tzinfo=_CST)
    return parsed


def _ttl_seconds(category: str, stale_after_days: dict[str, int] | None) -> int:
    if stale_after_days and category in stale_after_days:
        return int(stale_after_days[category]) * 86400
    return DEFAULT_TTL_S.get(category, TTL_STATIC)


def build_report(
    conn: Any, *, stale_after_days: dict[str, int] | None = None
) -> list[dict]:
    """按 city+category 汇总体检指标；库内无实体时返回空列表。"""
    now = datetime.now(timezone.utc)

    entities = conn.execute(
        "SELECT id, city, type FROM entity WHERE status = 'active'"
    ).fetchall()
    if not entities:
        return []

    fields_by_entity: dict[int, list[tuple[str, Any]]] = {}
    for row in conn.execute(
        "SELECT entity_id, field_name, fetched_at FROM field_value WHERE is_current = 1"
    ).fetchall():
        fields_by_entity.setdefault(int(row["entity_id"]), []).append(
            (row["field_name"], row["fetched_at"])
        )

    conflict_ids = {
        int(row["entity_id"])
        for row in conn.execute(
            "SELECT DISTINCT entity_id FROM review_queue "
            "WHERE status = 'pending' AND entity_id IS NOT NULL"
        ).fetchall()
    }

    groups: dict[tuple[str, str], list[int]] = {}
    for row in entities:
        groups.setdefault((row["city"], row["type"]), []).append(int(row["id"]))

    report: list[dict] = []
    for (city, category), entity_ids in sorted(groups.items()):
        total = len(entity_ids)
        required = REQUIRED_FIELDS.get(category, ())
        ttl_s = _ttl_seconds(category, stale_after_days)
        missing = stale = conflict = 0

        for entity_id in entity_ids:
            fields = fields_by_entity.get(entity_id, [])
            present = {name for name, _ in fields}
            if any(name not in present for name in required):
                missing += 1
            if any(
                (ts := _parse_ts(fetched_at)) is not None
                and (now - ts).total_seconds() > ttl_s
                for _, fetched_at in fields
            ):
                stale += 1
            if entity_id in conflict_ids:
                conflict += 1

        report.append(
            {
                "city": city,
                "category": category,
                "total": total,
                "missing_rate": round(missing / total, 4),
                "stale_rate": round(stale / total, 4),
                "conflict_rate": round(conflict / total, 4),
            }
        )
    return report


def export_csv(rows: list[dict], path: str) -> None:
    """把体检报表写成 CSV（UTF-8，自动创建父目录）。"""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(CSV_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in CSV_COLUMNS})