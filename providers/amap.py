"""高德地图 Provider：POI 搜索、地理编码、路径规划与天气查询。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from config import AMAP_CITY_CODES
from datastore import db
from datastore.repository import upsert_entity, upsert_field
from infra.cache import TTL_DYNAMIC, TTL_STATIC, get_cache, namespaced
from infra.http import get_json
from infra.logging_setup import get_logger, log_event
from providers.models import ExtractionInvalid, PlaceItem, ProviderUnavailable
from settings import settings

PROVIDER_NAME = "amap"
POI_TEXT_URL = "https://restapi.amap.com/v5/place/text"
GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
DIRECTION_URL = "https://restapi.amap.com/v5/direction/{path}"

CONFIDENCE_FULL = 0.8
CONFIDENCE_PARTIAL = 0.6
INDOOR_HINTS = ("博物馆", "纪念馆", "展览", "美术馆", "馆", "剧院", "商场")
TYPE_BY_PREFIX = (("11", "attraction"), ("05", "restaurant"), ("10", "hotel"))
DIRECTION_PATHS = {
    "driving": "driving",
    "walking": "walking",
    "bicycling": "bicycling",
    "riding": "bicycling",
    "transit": "transit/integrated",
    "integrated": "transit/integrated",
}

_CST = timezone(timedelta(hours=8))
_logger = get_logger("amap")


def _now() -> str:
    return datetime.now(_CST).isoformat(timespec="seconds")


def _city_code(city: str) -> str:
    name = str(city or "").strip()
    stripped = name.removesuffix("市")
    return AMAP_CITY_CODES.get(stripped, name)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _split_location(location: Any) -> tuple[float | None, float | None]:
    if not isinstance(location, str) or "," not in location:
        return None, None
    lng_text, _, lat_text = location.partition(",")
    return _to_float(lng_text), _to_float(lat_text)


def _entity_type(typecode: str) -> str:
    for prefix, name in TYPE_BY_PREFIX:
        if typecode.startswith(prefix):
            return name
    return "place"


def _is_indoor(poi: dict) -> bool:
    text = f"{poi.get('name') or ''}{poi.get('type') or ''}"
    return any(hint in text for hint in INDOOR_HINTS)


def _check_status(data: dict) -> None:
    if str(data.get("status")) != "1":
        info = data.get("info") or "unknown"
        raise ProviderUnavailable(f"amap_status:{info}")


def _persist(entity_type: str, city: str, name: str, fields: dict, source_url: str, confidence: float) -> None:
    conn = db.connect()
    try:
        with db.transaction(conn):
            entity_id = upsert_entity(conn, type=entity_type, city=city, name=name)
            for field_name, value in fields.items():
                if value is None or value == "":
                    continue
                upsert_field(
                    conn,
                    entity_id=entity_id,
                    field_name=field_name,
                    value=value,
                    source=PROVIDER_NAME,
                    source_url=source_url,
                    confidence=confidence,
                )
    except Exception as exc:  # 落库失败不影响本次查询结果
        log_event(_logger, "persist_failed", provider=PROVIDER_NAME, outcome="warn", error=str(exc))
    finally:
        conn.close()


def _collect_polyline(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "polyline" and isinstance(value, str) and value:
                out.append(value)
            else:
                _collect_polyline(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_polyline(value, out)


class AmapPlaceProvider:
    """高德 Web 服务 API 调用封装，查询结果同时落库到 field_value。"""

    name = PROVIDER_NAME

    def __init__(self) -> None:
        self._cache = get_cache()

    def _ensure_ready(self) -> None:
        if not settings.use_real_amap or not settings.amap_key.strip():
            raise ProviderUnavailable("amap_key_missing")

    def search(self, city: str, keyword: str, limit: int = 15) -> list[PlaceItem]:
        self._ensure_ready()
        cache_key = namespaced(PROVIDER_NAME, f"poi:{city}:{keyword}:{limit}")
        cached = self._cache.get(cache_key)
        if isinstance(cached, list):
            return [PlaceItem.model_validate(item) for item in cached]

        data = get_json(
            POI_TEXT_URL,
            params={
                "key": settings.amap_key,
                "keywords": keyword,
                "region": _city_code(city),
                "city_limit": "true",
                "page_size": str(limit),
                "page_num": "1",
                "show_fields": "business,photos",
            },
            provider=PROVIDER_NAME,
        )
        _check_status(data)

        items: list[PlaceItem] = []
        for poi in data.get("pois") or []:
            if not isinstance(poi, dict) or not str(poi.get("name") or "").strip():
                continue
            item = self._to_place(city, poi)
            items.append(item)
            _persist(
                item.type,
                item.city,
                item.name,
                {
                    "address": item.address,
                    "lng": item.lng,
                    "lat": item.lat,
                    "open_time": item.open_time,
                    "avg_price": item.avg_price,
                    "phone": item.phone,
                    "indoor": item.indoor,
                },
                item.source_url,
                item.confidence,
            )

        self._cache.set(cache_key, [item.model_dump() for item in items], TTL_DYNAMIC)
        return items[:limit]

    def geocode(self, address: str, city: str) -> PlaceItem:
        self._ensure_ready()
        cache_key = namespaced(PROVIDER_NAME, f"geo:{city}:{address}")
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict):
            return PlaceItem.model_validate(cached)

        data = get_json(
            GEOCODE_URL,
            params={"key": settings.amap_key, "address": address, "city": _city_code(city)},
            provider=PROVIDER_NAME,
        )
        _check_status(data)

        geocodes = data.get("geocodes") or []
        if not geocodes:
            raise ProviderUnavailable("geocode_empty")
        geo = geocodes[0]
        lng, lat = _split_location(geo.get("location"))
        if lng is None or lat is None:
            raise ExtractionInvalid("geocode_location_invalid", raw_excerpt=str(geo.get("location")))

        item = PlaceItem(
            name=address,
            type="address",
            city=city or str(geo.get("city") or ""),
            address=str(geo.get("formatted_address") or address),
            lng=lng,
            lat=lat,
            source=PROVIDER_NAME,
            source_url=f"https://www.amap.com/search?query={quote(str(address))}",
            fetched_at=_now(),
            confidence=CONFIDENCE_FULL,
        )
        self._cache.set(cache_key, item.model_dump(), TTL_STATIC)
        _persist(
            "address",
            item.city,
            item.name,
            {"address": item.address, "lng": item.lng, "lat": item.lat},
            item.source_url,
            item.confidence,
        )
        return item

    def get_weather(self, city: str, date: str) -> dict:
        self._ensure_ready()
        cache_key = namespaced(PROVIDER_NAME, f"weather:{city}:{date}")
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict):
            return cached

        data = get_json(
            WEATHER_URL,
            params={"key": settings.amap_key, "city": _city_code(city), "extensions": "all"},
            provider=PROVIDER_NAME,
        )
        _check_status(data)

        forecasts = data.get("forecasts") or []
        casts = (forecasts[0].get("casts") if forecasts else None) or []
        if not casts:
            raise ExtractionInvalid("weather_empty", raw_excerpt=str(data)[:200])

        target = str(date or "").strip()
        cast = next((c for c in casts if str(c.get("date")) == target), casts[0])
        result = {
            "city": city,
            "date": str(cast.get("date") or ""),
            "weather": str(cast.get("dayweather") or cast.get("nightweather") or ""),
            "temp_low": _to_float(cast.get("nighttemp")),
            "temp_high": _to_float(cast.get("daytemp")),
            "wind": f"{cast.get('daywind') or ''}{cast.get('daypower') or ''}".strip(),
            "source": PROVIDER_NAME,
            "fetched_at": _now(),
        }
        self._cache.set(cache_key, result, TTL_DYNAMIC)
        _persist(
            "weather",
            city,
            city,
            {"forecast": {k: v for k, v in result.items() if k not in ("source", "fetched_at")}},
            "https://www.amap.com/",
            CONFIDENCE_FULL,
        )
        return result

    def route(
        self,
        from_lng: float,
        from_lat: float,
        to_lng: float,
        to_lat: float,
        mode: str = "driving",
    ) -> dict:
        self._ensure_ready()
        mode_key = str(mode or "driving").strip().lower()
        path = DIRECTION_PATHS.get(mode_key, "driving")
        cache_key = namespaced(
            PROVIDER_NAME,
            f"route:{path}:{from_lng},{from_lat}->{to_lng},{to_lat}",
        )
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict):
            return cached

        data = get_json(
            DIRECTION_URL.format(path=path),
            params={
                "key": settings.amap_key,
                "origin": f"{from_lng},{from_lat}",
                "destination": f"{to_lng},{to_lat}",
                "show_fields": "cost,polyline",
            },
            provider=PROVIDER_NAME,
        )
        _check_status(data)

        route = data.get("route") or {}
        entries = route.get("transits") if "transit" in path else route.get("paths")
        if not entries:
            raise ProviderUnavailable("route_empty")
        first = entries[0]
        cost = first.get("cost") if isinstance(first.get("cost"), dict) else {}
        polyline_parts: list[str] = []
        _collect_polyline(first.get("steps") or first.get("segments"), polyline_parts)
        result = {
            "distance_m": _to_int(first.get("distance")),
            "duration_s": _to_int(cost.get("duration") or first.get("duration")),
            "polyline": ";".join(polyline_parts),
        }
        self._cache.set(cache_key, result, TTL_DYNAMIC)
        return result


def get_weather(city: str, date: str) -> dict:
    return AmapPlaceProvider().get_weather(city, date)


def geocode(address: str, city: str) -> PlaceItem:
    return AmapPlaceProvider().geocode(address, city)


def route(
    from_lng: float,
    from_lat: float,
    to_lng: float,
    to_lat: float,
    mode: str = "driving",
) -> dict:
    return AmapPlaceProvider().route(from_lng, from_lat, to_lng, to_lat, mode)