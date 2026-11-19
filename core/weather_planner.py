"""天气联动重排：恶劣天气（降雨或高温）时把户外行程项替换为室内备选。"""

BAD_WEATHER_KEYWORDS = ("雨", "雷", "雪")
HEAT_THRESHOLD = 35.0
INDOOR_TAG_KEYWORDS = ("室内", "博物馆", "展览", "美术馆")


def _field(obj, key, default=None):
    """兼容 pydantic 模型与裸 dict 两种地点/行程项表示。"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def is_bad_weather(weather: dict) -> bool:
    if not weather:
        return False
    if isinstance(weather, str):
        return any(k in weather for k in BAD_WEATHER_KEYWORDS)
    text = str(_field(weather, "weather") or _field(weather, "text") or "")
    if any(k in text for k in BAD_WEATHER_KEYWORDS):
        return True
    high = _field(weather, "temp_high")
    if high is None:
        high = _field(weather, "temperature")
    try:
        return float(high) >= HEAT_THRESHOLD
    except (TypeError, ValueError):
        return False


def _weather_reason(weather) -> str:
    text = weather if isinstance(weather, str) else str(
        _field(weather, "weather") or _field(weather, "text") or ""
    )
    if any(k in text for k in BAD_WEATHER_KEYWORDS):
        return "有降雨"
    return "高温"


def _weather_of(day: dict, weather_by_day) -> dict | str | None:
    """按天号或日期查天气，weather_by_day 的键可为 day 整数或 "YYYY-MM-DD"。"""
    if not weather_by_day:
        return None
    day_no = day.get("day")
    for key in (day_no, day.get("date"), None if day_no is None else str(day_no)):
        if key is not None and key in weather_by_day:
            return weather_by_day[key]
    return None


def _is_indoor(place) -> bool:
    indoor = _field(place, "indoor")
    if isinstance(indoor, bool):
        return indoor
    if indoor is not None:
        return bool(indoor)
    tags = _field(place, "tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return any(k in str(tag) for tag in tags for k in INDOOR_TAG_KEYWORDS)


def _next_indoor(places: list, used_names: set[str]):
    for place in places:
        name = str(_field(place, "name", "") or "")
        if not name or name in used_names:
            continue
        if _is_indoor(place):
            return place
    return None


def _copy_item(item) -> dict:
    if isinstance(item, dict):
        return dict(item)
    return {key: _field(item, key) for key in ("name", "start", "end", "lng", "lat", "indoor")}


def replan_for_weather(itinerary, places, weather_by_day) -> tuple[list[dict], list[str]]:
    days = list(itinerary or [])
    indoor_pool = list(places or [])
    used_names = {
        str(_field(item, "name", "") or "")
        for day in days
        for item in (day.get("items") or [])
    }
    replanned: list[dict] = []
    notes: list[str] = []

    for day in days:
        items = list(day.get("items") or [])
        weather = _weather_of(day, weather_by_day)
        if not items or not is_bad_weather(weather):
            replanned.append({**day, "items": [_copy_item(item) for item in items]})
            continue

        reason = _weather_reason(weather)
        new_items: list[dict] = []
        for item in items:
            if _field(item, "indoor"):
                new_items.append(_copy_item(item))
                continue

            name = _field(item, "name", "") or ""
            alt = _next_indoor(indoor_pool, used_names)
            if alt is None:
                notes.append(f"第{day.get('day')}天 {name} 为户外项目，{reason}，暂无可用室内备选")
                new_items.append(_copy_item(item))
                continue

            alt_name = str(_field(alt, "name", "") or "")
            used_names.add(alt_name)
            new_items.append({
                "name": alt_name,
                "start": _field(item, "start"),
                "end": _field(item, "end"),
                "lng": _field(alt, "lng"),
                "lat": _field(alt, "lat"),
                "indoor": True,
            })
            notes.append(f"第{day.get('day')}天 {name} → {alt_name}：{reason}，已替换为室内项目")

        replanned.append({**day, "items": new_items})

    return replanned, notes