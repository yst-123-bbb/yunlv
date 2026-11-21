"""城市与景点目录服务：只读，全部基于 ``data.place_catalog`` 的内存常量。"""

from __future__ import annotations

from data.attraction_images import image_meta, image_remote_url, image_url
from data.place_catalog import ATTRACTIONS, CITIES

_SEARCH_LIMIT = 20
_HOT_CITY_LIMIT = 8
_HOT_ATTRACTION_LIMIT = 10


def _attraction_out(city_name: str, item: dict, with_meta: bool = False) -> dict:
    out = {
        **item,
        "tags": list(item["tags"]),
        "city": city_name,
        "image": image_url(item["name"]),
        "image_fallback": image_remote_url(item["name"]),
    }
    if with_meta:
        out["image_meta"] = image_meta().get(item["name"]) or {}
    return out


def _city_brief(city: dict) -> dict:
    name = city["name"]
    return {
        "name": name,
        "province": city["province"],
        "tag": city["tag"],
        "spots": list(city["spots"]),
        "attraction_count": len(ATTRACTIONS.get(name, [])),
    }


def _sorted_cities() -> list[dict]:
    cities = [_city_brief(city) for city in CITIES]
    cities.sort(key=lambda c: (-c["attraction_count"], c["name"]))
    return cities


def _find_city(name: str) -> dict | None:
    key = (name or "").strip().casefold()
    if not key:
        return None
    for city in CITIES:
        if city["name"].casefold() == key:
            return city
    return None


def list_cities() -> list[dict]:
    return _sorted_cities()


def get_city(name: str) -> dict:
    city = _find_city(name)
    if city is None:
        raise KeyError("city_not_found")
    city_name = city["name"]
    return {
        "city": {
            "name": city_name,
            "province": city["province"],
            "tag": city["tag"],
            "spots": list(city["spots"]),
        },
        "attractions": [_attraction_out(city_name, item) for item in ATTRACTIONS.get(city_name, [])],
    }


def list_attractions(city: str | None = None, limit: int = 12) -> list[dict]:
    if not 1 <= limit <= 50:
        raise ValueError("invalid_limit")
    if city is None:
        items = [
            _attraction_out(city_name, item)
            for city_name, attractions in ATTRACTIONS.items()
            for item in attractions
        ]
    else:
        matched = _find_city(city)
        items = [] if matched is None else [
            _attraction_out(matched["name"], item) for item in ATTRACTIONS[matched["name"]]
        ]
    items.sort(key=lambda a: -a["likes"])
    return items[:limit]


def get_attraction(name: str) -> dict:
    key = (name or "").strip().casefold()
    if key:
        for city_name, attractions in ATTRACTIONS.items():
            for item in attractions:
                if item["name"].casefold() == key:
                    return _attraction_out(city_name, item, with_meta=True)
    raise KeyError("attraction_not_found")


def search(q: str) -> dict:
    needle = (q or "").strip().casefold()
    if not needle:
        raise ValueError("invalid_query")

    cities = [
        city
        for city in _sorted_cities()
        if needle in city["name"].casefold()
        or needle in city["province"].casefold()
        or needle in city["tag"].casefold()
    ][:_SEARCH_LIMIT]

    attractions: list[dict] = []
    for city_name, items in ATTRACTIONS.items():
        for item in items:
            haystack = " ".join([item["name"], *item["tags"], item["features"]]).casefold()
            if needle in haystack:
                attractions.append(_attraction_out(city_name, item))
    attractions.sort(key=lambda a: -a["likes"])
    return {"cities": cities, "attractions": attractions[:_SEARCH_LIMIT]}


def hot() -> dict:
    cities = [
        {
            "name": city["name"],
            "province": city["province"],
            "tag": city["tag"],
            "attraction_count": city["attraction_count"],
        }
        for city in _sorted_cities()[:_HOT_CITY_LIMIT]
    ]
    attractions: list[dict] = [
        _attraction_out(city_name, item)
        for city_name, items in ATTRACTIONS.items()
        for item in items
    ]
    attractions.sort(key=lambda a: -a["likes"])
    return {"cities": cities, "attractions": attractions[:_HOT_ATTRACTION_LIMIT]}