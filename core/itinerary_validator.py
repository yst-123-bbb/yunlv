# -*- coding: utf-8 -*-
"""行程校验器：检查时间冲突、距离超阈值、闭馆日、预约缺失、超营业时间与人群强度。"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

try:
    from providers.models import PlaceItem
except Exception:  # 数据模型尚未装配时仍保证模块可导入
    PlaceItem = Any

DISTANCE_THRESHOLD_KM = 2.0

_EARTH_RADIUS_KM = 6371.0
_DAY_MINUTES = 24 * 60
_MINUTES_RE = re.compile(r"(\d{1,2}):(\d{2})")
_OPEN_RANGE_RE = re.compile(r"(\d{1,2}):(\d{2})\s*[-~—至到]\s*(\d{1,2}):(\d{2})")
_CLOSED_MONDAY = "周一闭馆"

IssueCode = Literal[
    "time_overlap",
    "distance",
    "closed_day",
    "booking_required",
    "out_of_hours",
    "crowd_intensity",
]


class Issue(BaseModel):
    day: int
    start_time: str | None = None
    code: IssueCode
    level: Literal["error", "warn"]
    message: str
    refs: list[str] = Field(default_factory=list)


def validate_itinerary(
    itinerary: list[dict],
    places: list[PlaceItem],
    *,
    start_date: str,
    crowd_mode: str = "normal",
) -> list[Issue]:
    """校验行程并返回可定位到天与时刻的问题列表；任何缺失信息只跳过校验，不抛异常。"""
    index = _place_index(places)
    issues: list[Issue] = []

    for entry in itinerary or []:
        day = _to_int(_field(entry, "day"))
        if day <= 0:
            continue
        day_date = _resolve_date(entry, start_date, day)
        items = sorted(_day_items(entry), key=lambda it: _to_minutes(_field(it, "start")) or 0)

        issues.extend(_check_time_overlap(day, items))
        issues.extend(_check_distance(day, items))
        for item in items:
            issues.extend(_check_place(day, day_date, item, index))
        issues.extend(_check_crowd(day, items, crowd_mode))

    issues.sort(key=lambda issue: (issue.day, _to_minutes(issue.start_time) or -1))
    return issues


def _check_time_overlap(day: int, items: list[Any]) -> list[Issue]:
    issues: list[Issue] = []
    spans = [
        (name_of(item), _to_minutes(_field(item, "start")), _span_end(item))
        for item in items
    ]
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            name_a, start_a, end_a = spans[i]
            name_b, start_b, end_b = spans[j]
            if None in (start_a, end_a, start_b, end_b):
                continue
            if start_b < end_a and start_a < end_b:
                issues.append(
                    Issue(
                        day=day,
                        start_time=_fmt(max(start_a, start_b)),
                        code="time_overlap",
                        level="error",
                        message=(
                            f"{name_a}（{_fmt(start_a)}-{_fmt(end_a)}）与 "
                            f"{name_b}（{_fmt(start_b)}-{_fmt(end_b)}）时间重叠"
                        ),
                        refs=[name_a, name_b],
                    )
                )
    return issues


def _check_distance(day: int, items: list[Any]) -> list[Issue]:
    issues: list[Issue] = []
    for prev, cur in zip(items, items[1:]):
        prev_lng, prev_lat = _field(prev, "lng"), _field(prev, "lat")
        cur_lng, cur_lat = _field(cur, "lng"), _field(cur, "lat")
        if None in (prev_lng, prev_lat, cur_lng, cur_lat):
            continue
        km = _haversine(prev_lng, prev_lat, cur_lng, cur_lat)
        if km > DISTANCE_THRESHOLD_KM:
            issues.append(
                Issue(
                    day=day,
                    start_time=_fmt(_to_minutes(_field(cur, "start"))),
                    code="distance",
                    level="warn",
                    message=(
                        f"{name_of(prev)} → {name_of(cur)} 直线距离 {km:.1f} km，"
                        f"超过 {DISTANCE_THRESHOLD_KM} km，建议调整顺序或更换交通方式"
                    ),
                    refs=[name_of(prev), name_of(cur)],
                )
            )
    return issues


def _check_place(day: int, day_date: date | None, item: Any, index: dict[str, Any]) -> list[Issue]:
    name = name_of(item)
    place = _lookup(index, name)
    if place is None:
        return []

    issues: list[Issue] = []
    start = _to_minutes(_field(item, "start"))
    end = _span_end(item)
    open_time = str(_field(place, "open_time", "") or "")

    booking_required = bool(
        _field(item, "booking_required", False) or _field(place, "booking_required", False)
    )
    booked = bool(_field(item, "booked", False) or _field(place, "booked", False))
    if booking_required and not booked:
        issues.append(
            Issue(
                day=day,
                start_time=_fmt(start),
                code="booking_required",
                level="warn",
                message=f"{name} 需提前预约，当前行程尚未标记已预约",
                refs=[name],
            )
        )

    if not open_time:
        return issues

    if _CLOSED_MONDAY in open_time and day_date is not None and day_date.weekday() == 0:
        issues.append(
            Issue(
                day=day,
                start_time=_fmt(start),
                code="closed_day",
                level="error",
                message=f"{name} 周一闭馆，{day_date.isoformat()} 无法参观",
                refs=[name],
            )
        )
        return issues

    span = _parse_open_range(open_time)
    if span is not None and start is not None:
        open_min, close_min = span
        if start < open_min or (end is not None and end > close_min):
            issues.append(
                Issue(
                    day=day,
                    start_time=_fmt(start),
                    code="out_of_hours",
                    level="warn",
                    message=(
                        f"{name} 开放时间 {open_time}，行程 "
                        f"{_fmt(start)}-{_fmt(end) or _field(item, 'end', '')} 超出营业时间"
                    ),
                    refs=[name],
                )
            )
    return issues


def _check_crowd(day: int, items: list[Any], crowd_mode: str) -> list[Issue]:
    if (crowd_mode or "normal") == "normal" or len(items) < 3:
        return []
    return [
        Issue(
            day=day,
            start_time="10:00",
            code="crowd_intensity",
            level="warn",
            message=(
                f"第 {day} 天安排 {len(items)} 个景点，{crowd_mode} 模式下人流密集，"
                "建议错峰出行并预留休息时间"
            ),
            refs=[name_of(item) for item in items],
        )
    ]


def _place_index(places: list[PlaceItem]) -> dict[str, Any]:
    index: dict[str, Any] = {}
    for place in places or []:
        name = str(_field(place, "name", "") or "").strip()
        if name:
            index.setdefault(name, place)
    return index


def _lookup(index: dict[str, Any], name: str) -> Any | None:
    if not name:
        return None
    if name in index:
        return index[name]
    for key, place in index.items():
        if name in key or key in name:
            return place
    return None


def _day_items(entry: Any) -> list[Any]:
    items = _field(entry, "items", []) or []
    return [item for item in items if item is not None]


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def name_of(item: Any) -> str:
    return str(_field(item, "name", "") or "")


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_minutes(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    match = _MINUTES_RE.search(value)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def _span_end(item: Any) -> int | None:
    start = _to_minutes(_field(item, "start"))
    end = _to_minutes(_field(item, "end"))
    if start is None or end is None:
        return None
    return end + _DAY_MINUTES if end < start else end


def _parse_open_range(open_time: str) -> tuple[int, int] | None:
    match = _OPEN_RANGE_RE.search(open_time)
    if not match:
        return None
    open_min = int(match.group(1)) * 60 + int(match.group(2))
    close_min = int(match.group(3)) * 60 + int(match.group(4))
    if close_min < open_min:
        close_min += _DAY_MINUTES
    return open_min, close_min


def _fmt(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    normalized = minutes % _DAY_MINUTES
    return f"{normalized // 60:02d}:{normalized % 60:02d}"


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _resolve_date(entry: Any, start_date: str, day: int) -> date | None:
    parsed = _parse_date(_field(entry, "date"))
    if parsed is not None:
        return parsed
    base = _parse_date(start_date)
    if base is None:
        return None
    return base + timedelta(days=day - 1)


def _haversine(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    lon1, lat_1, lon2, lat_2 = map(math.radians, (float(lng1), float(lat1), float(lng2), float(lat2)))
    dlon, dlat = lon2 - lon1, lat_2 - lat_1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat_1) * math.cos(lat_2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))