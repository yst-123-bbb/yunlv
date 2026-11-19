"""实体治理：名称归一、重复发现、实体合并与坐标边界校验。

约定：所有写操作在调用方事务内执行，本模块不 commit。
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone

from datastore.repository import enqueue_review

_TZ = timezone(timedelta(hours=8))

# 括号注释：半角/全角圆括号与方括号、中文方头括号
_BRACKET_RE = re.compile(r"[（(【\[][^（）()【\[\]]*[）)】\]]")
_WS_RE = re.compile(r"\s+")

_COORD_RADIUS_KM = 100.0

# 近似城市中心坐标（与 config.AMAP_CITY_CODES 的城市集合一致）
_CITY_CENTERS: dict[str, tuple[float, float]] = {
    "北京": (116.407, 39.904),
    "上海": (121.473, 31.230),
    "广州": (113.264, 23.129),
    "深圳": (114.057, 22.543),
    "长沙": (112.939, 28.228),
    "成都": (104.066, 30.572),
    "杭州": (120.155, 30.274),
    "武汉": (114.305, 30.593),
    "西安": (108.939, 34.341),
    "南京": (118.797, 32.060),
    "苏州": (120.585, 31.299),
    "天津": (117.190, 39.125),
    "重庆": (106.551, 29.563),
    "三亚": (109.512, 18.252),
    "厦门": (118.090, 24.480),
    "青岛": (120.383, 36.067),
    "大连": (121.615, 38.914),
    "昆明": (102.833, 24.880),
    "丽江": (100.230, 26.872),
    "大理": (100.267, 25.606),
    "哈尔滨": (126.535, 45.803),
}


def normalize_name(name: str) -> str:
    """全角转半角、去括号注释、去空白、小写化。"""
    text = unicodedata.normalize("NFKC", name or "")
    text = _BRACKET_RE.sub("", text)
    text = _WS_RE.sub("", text)
    return text.lower()


def find_duplicates(conn: sqlite3.Connection) -> list[list[int]]:
    """返回同 city+type 下的疑似重复实体分组（组内 ≥2 个实体 id）。"""
    rows = conn.execute(
        "SELECT id, city, type, name, alias FROM entity WHERE status = 'active' ORDER BY id"
    ).fetchall()

    by_scope: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        by_scope.setdefault((row["city"], row["type"]), []).append(row)

    groups: list[list[int]] = []
    for items in by_scope.values():
        ids = [row["id"] for row in items]
        parent = {entity_id: entity_id for entity_id in ids}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        norms = {row["id"]: normalize_name(row["name"]) for row in items}
        aliases = {
            row["id"]: {normalize_name(a) for a in _parse_alias(row["alias"]) if a}
            for row in items
        }

        for i, left in enumerate(items):
            for right in items[i + 1:]:
                a, b = left["id"], right["id"]
                na, nb = norms[a], norms[b]
                if not na or not nb:
                    continue
                if na == nb or na in aliases[b] or nb in aliases[a]:
                    union(a, b)

        buckets: dict[int, list[int]] = {}
        for entity_id in ids:
            buckets.setdefault(find(entity_id), []).append(entity_id)
        groups.extend(sorted(members) for members in buckets.values() if len(members) >= 2)

    groups.sort()
    return groups


def merge_entities(conn: sqlite3.Connection, keep_id: int, drop_id: int) -> dict[str, int]:
    """把 drop_id 的有效字段并入 keep_id，drop_id 置 status='merged'（保留行）。"""
    if keep_id == drop_id:
        raise ValueError("same_entity")

    keep = conn.execute("SELECT * FROM entity WHERE id = ?", (keep_id,)).fetchone()
    drop = conn.execute("SELECT * FROM entity WHERE id = ?", (drop_id,)).fetchone()
    if keep is None or drop is None:
        raise ValueError("entity_not_found")

    now = _now()
    keep_current = {
        row["field_name"]: row
        for row in conn.execute(
            "SELECT * FROM field_value WHERE entity_id = ? AND is_current = 1", (keep_id,)
        ).fetchall()
    }
    drop_current = conn.execute(
        "SELECT * FROM field_value WHERE entity_id = ? AND is_current = 1 ORDER BY id", (drop_id,)
    ).fetchall()

    moved_fields = 0
    for row in drop_current:
        existing = keep_current.get(row["field_name"])
        if existing is None:
            conn.execute(
                "UPDATE field_value SET entity_id = ? WHERE id = ?", (keep_id, row["id"])
            )
            _log_change(conn, keep_id, row["field_name"], None, row["value_json"], row["source"], now)
            moved_fields += 1
            continue

        if row["confidence"] > existing["confidence"]:
            conn.execute("UPDATE field_value SET is_current = 0 WHERE id = ?", (existing["id"],))
            conn.execute(
                "UPDATE field_value SET entity_id = ?, version = ? WHERE id = ?",
                (keep_id, existing["version"] + 1, row["id"]),
            )
            _log_change(
                conn, keep_id, row["field_name"], existing["value_json"], row["value_json"],
                row["source"], now,
            )
            moved_fields += 1
        else:
            conn.execute("UPDATE field_value SET is_current = 0 WHERE id = ?", (row["id"],))
            enqueue_review(
                conn,
                entity_id=keep_id,
                field_name=row["field_name"],
                proposed=_loads(row["value_json"]),
                current=_loads(existing["value_json"]),
                reason="merge_conflict",
                raw_excerpt=f"merged_from:{drop_id}",
            )

    merged_alias = _merge_alias(keep["alias"], drop["name"], _parse_alias(drop["alias"]))
    conn.execute(
        "UPDATE entity SET alias = ?, updated_at = ? WHERE id = ?", (merged_alias, now, keep_id)
    )
    conn.execute(
        "UPDATE entity SET status = 'merged', updated_at = ? WHERE id = ?", (now, drop_id)
    )
    _log_change(
        conn, drop_id, "status",
        json.dumps(drop["status"], ensure_ascii=False),
        json.dumps("merged", ensure_ascii=False),
        "governance", now,
    )

    return {"moved_fields": moved_fields, "dropped": 1}


def validate_coord(city: str, lng: float, lat: float) -> bool:
    """坐标是否落在城市中心 100km 内；城市未知时返回 True。"""
    if lng is None or lat is None:
        return False
    try:
        lng_f, lat_f = float(lng), float(lat)
    except (TypeError, ValueError):
        return False
    if not (math.isfinite(lng_f) and math.isfinite(lat_f)):
        return False

    center = _city_center(city)
    if center is None:
        return True
    return _distance_km(center[0], center[1], lng_f, lat_f) <= _COORD_RADIUS_KM


def _known_cities() -> dict:
    try:
        from config import AMAP_CITY_CODES
    except ImportError:
        return _CITY_CENTERS
    return AMAP_CITY_CODES


def _city_center(city: str) -> tuple[float, float] | None:
    key = (city or "").strip()
    if not key:
        return None
    known = _known_cities()
    candidates = [key]
    for suffix in ("市", "省"):
        if key.endswith(suffix) and len(key) > len(suffix):
            candidates.append(key[: -len(suffix)])
    for candidate in candidates:
        if candidate in known:
            return _CITY_CENTERS.get(candidate)
    return None


def _distance_km(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def _parse_alias(alias: str | None) -> list[str]:
    if not alias:
        return []
    try:
        data = json.loads(alias)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if item]


def _loads(value_json: str):
    try:
        return json.loads(value_json)
    except (json.JSONDecodeError, TypeError):
        return value_json


def _merge_alias(keep_alias: str | None, drop_name: str, drop_alias: list[str]) -> str | None:
    merged: list[str] = []
    for name in _parse_alias(keep_alias) + [drop_name] + drop_alias:
        if name and name not in merged:
            merged.append(name)
    return json.dumps(merged, ensure_ascii=False) if merged else None


def _log_change(
    conn: sqlite3.Connection,
    entity_id: int,
    field_name: str,
    old_value_json: str | None,
    new_value_json: str | None,
    source: str,
    changed_at: str,
    operator: str = "merge",
) -> None:
    conn.execute(
        "INSERT INTO change_log"
        " (entity_id, field_name, old_value_json, new_value_json, source, operator, changed_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (entity_id, field_name, old_value_json, new_value_json, source, operator, changed_at),
    )


def _now() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")