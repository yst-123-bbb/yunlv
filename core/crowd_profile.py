# -*- coding: utf-8 -*-
"""人群模式强度提示：按亲子/老人/无障碍模式给出每日步行、爬升与可达性评估。"""

from __future__ import annotations

import math
from typing import Any, Literal

CROWD_MODES = ("normal", "family", "senior", "accessible")

# 各模式的单日舒适阈值：(步行 km, 爬升 m)
_THRESHOLDS: dict[str, tuple[float, float]] = {
    "normal": (8.0, 500.0),
    "family": (5.0, 200.0),
    "senior": (4.0, 150.0),
    "accessible": (3.0, 30.0),
}

_EARTH_RADIUS_KM = 6371.0
_ITEM_BASE_WALK_KM = 0.5  # 每个景点园区内的基础步行量

_CLIMB_KEYWORDS = ("山", "峰", "岭", "长城", "塔", "寺", "宫", "洞", "坡", "登")
_ELEVATOR_KEYWORDS = ("电梯", "无障碍", "缆车", "索道", "扶梯", "坡道")

_MODE_TIPS: dict[str, list[str]] = {
    "normal": ["按常规节奏游览，注意补充水分。"],
    "family": [
        "亲子模式：安排午休时段，避免连续排队超过 40 分钟。",
        "优先选择有儿童设施、可随时中断的景点。",
    ],
    "senior": [
        "老人模式：景区间预留休息时间，避免连续爬坡。",
        "提前确认景区医务点与就近医院位置。",
    ],
    "accessible": [
        "无障碍模式：出发前确认景点无障碍通道与电梯开放情况。",
        "优先安排室内或有平缓无障碍路线的景点。",
    ],
}


def profile_day(itinerary_day: dict, mode: str) -> dict:
    """评估单日行程强度；缺坐标或缺字段时降级估算，不抛异常。"""
    mode = _normalize_mode(mode)
    items = _items(itinerary_day)
    walk_km = round(_estimate_walk_km(items), 2)
    climb_m = round(_estimate_climb_m(items), 1)
    elevator_ok = _elevator_ok(items, mode)
    walk_limit, climb_limit = _THRESHOLDS[mode]

    tips = list(_MODE_TIPS[mode])
    if walk_km > walk_limit:
        tips.append(f"今日步行约 {walk_km} km，超出{mode}模式建议 {walk_limit} km，建议减少景点或改乘摆渡车。")
    if climb_m > climb_limit:
        tips.append(f"今日爬升约 {climb_m} m，超出{mode}模式建议 {climb_limit} m，建议改乘缆车或替换为平缓景点。")
    if not elevator_ok:
        tips.append("部分景点未确认电梯/无障碍通道，请提前联系景区确认。")

    return {
        "walk_km": walk_km,
        "climb_m": climb_m,
        "elevator_ok": elevator_ok,
        "tips": tips,
        "intensity": _intensity(walk_km, climb_m, walk_limit, climb_limit),
    }


def _normalize_mode(mode: str | None) -> str:
    if not mode:
        return "normal"
    if mode not in CROWD_MODES:
        raise ValueError(f"unknown_crowd_mode: {mode}")
    return mode


def _items(itinerary_day: Any) -> list[Any]:
    items = itinerary_day.get("items") if isinstance(itinerary_day, dict) else None
    return [item for item in items or [] if item is not None]


def _field(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _text(item: Any) -> str:
    parts: list[str] = []
    for key in ("name", "tags", "features", "tips"):
        value = _field(item, key)
        if isinstance(value, (list, tuple)):
            parts.extend(str(v) for v in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def _estimate_walk_km(items: list[Any]) -> float:
    total = _ITEM_BASE_WALK_KM * len(items)
    for prev, cur in zip(items, items[1:]):
        distance = _haversine_km(_field(prev, "lng"), _field(prev, "lat"), _field(cur, "lng"), _field(cur, "lat"))
        if distance is not None:
            total += distance
    return total


def _estimate_climb_m(items: list[Any]) -> float:
    total = 0.0
    for item in items:
        explicit = _to_float(_field(item, "climb_m"))
        if explicit is not None:
            total += max(explicit, 0.0)
        elif any(keyword in _text(item) for keyword in _CLIMB_KEYWORDS):
            total += 80.0
    return total


def _elevator_ok(items: list[Any], mode: str) -> bool:
    if not items:
        return True
    if mode != "accessible":
        return True
    return all(_has_elevator(item) for item in items)


def _has_elevator(item: Any) -> bool:
    explicit = _field(item, "elevator")
    if explicit is None:
        explicit = _field(item, "accessible")
    if explicit is not None:
        return bool(explicit)
    return any(keyword in _text(item) for keyword in _ELEVATOR_KEYWORDS)


def _intensity(walk_km: float, climb_m: float, walk_limit: float, climb_limit: float) -> Literal["low", "mid", "high"]:
    ratio = max(walk_km / walk_limit, climb_m / climb_limit if climb_limit else 0.0)
    if ratio <= 0.6:
        return "low"
    if ratio <= 1.0:
        return "mid"
    return "high"


def _haversine_km(lng1: Any, lat1: Any, lng2: Any, lat2: Any) -> float | None:
    x1, y1, x2, y2 = _to_float(lng1), _to_float(lat1), _to_float(lng2), _to_float(lat2)
    if None in (x1, y1, x2, y2):
        return None
    phi1, phi2 = math.radians(y1), math.radians(y2)
    d_phi = math.radians(y2 - y1)
    d_lambda = math.radians(x2 - x1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None