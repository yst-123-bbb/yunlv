"""中转比价：以目的省及邻省的旅游城市为换乘点，与直达方案比价。"""

from __future__ import annotations

import re

from data import flight_data, train_data
from data.city_geo import CITY_COORDS, PROVINCE_NEIGHBORS, distance_km, province_of
from data.flight_data import get_flight_backup
from data.place_catalog import ATTRACTIONS, CITIES
from data.train_data import get_train_backup

NOTE = "价格为内置参考数据或按距离估算，非实时报价"
NOTE_NO_OPTION = "未找到更便宜的中转组合；价格为内置参考数据或按距离估算，非实时报价"

_MODE_LABELS = {"train": "高铁", "flight": "飞机"}
_COMBOS = (("train", "train"), ("train", "flight"), ("flight", "train"))
_DURATION_RE = re.compile(r"^(\d+)h(\d+)m$")
_MAX_CANDIDATES = 8


def _safe_distance(a: str, b: str) -> float:
    d = distance_km(a, b)
    return d if d >= 0 else 1000.0


def _duration_min(text: object, d: float, mode: str) -> int:
    match = _DURATION_RE.match(str(text or ""))
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    if mode == "train":
        return round(d / 250 * 60)
    return round(d / 700 * 60) + 60


def _cheapest(items: list[dict], extract) -> tuple[float, dict] | None:
    best: tuple[float, dict] | None = None
    for item in items:
        try:
            price = extract(item)
        except (KeyError, TypeError):
            continue
        if price is None:
            continue
        if best is None or price < best[0]:
            best = (price, item)
    return best


def _has_train_route(a: str, b: str) -> bool:
    """仅已收录线路的备份数据可信；未知线路会合成假报价。"""
    return f"{a}-{b}" in train_data._PAIRS or f"{b}-{a}" in train_data._PAIRS


def _has_flight_route(a: str, b: str) -> bool:
    return any(
        (row[0] == a and row[1] == b) or (row[0] == b and row[1] == a)
        for row in flight_data._TIMES
    )


def _train_quote(a: str, b: str) -> tuple[int, int]:
    """单程人均高铁价与时长；无真实线路时按距离估算。"""
    d = _safe_distance(a, b)
    best = None
    if _has_train_route(a, b):
        try:
            best = _cheapest(list(get_train_backup(a, b) or []), lambda t: t["seats"]["二等座"])
        except Exception:
            best = None
    if best is None:
        return max(60, round(0.45 * d)), _duration_min(None, d, "train")
    price, item = best
    return int(price), _duration_min(item.get("duration"), d, "train")


def _flight_quote(a: str, b: str) -> tuple[int, int]:
    """单程人均机票价与时长；无真实航线时按距离估算。"""
    d = _safe_distance(a, b)
    best = None
    if _has_flight_route(a, b):
        try:
            best = _cheapest(list(get_flight_backup(a, b) or []), lambda f: f["cabin"]["经济舱"])
        except Exception:
            best = None
    if best is None:
        return max(320, round(0.85 * d)), _duration_min(None, d, "flight")
    price, item = best
    return int(price), _duration_min(item.get("duration"), d, "flight")


def _candidates(origin: str, dest: str) -> list[str]:
    dest_province = province_of(dest)
    allowed = {dest_province} | set(PROVINCE_NEIGHBORS.get(dest_province, ()))

    names = [
        city["name"]
        for city in CITIES
        if city["name"] not in (origin, dest)
        and province_of(city["name"]) in allowed
        and ATTRACTIONS.get(city["name"])
    ]
    names.sort(key=lambda name: distance_km(name, dest))
    return names[:_MAX_CANDIDATES]


def find_transfers(origin: str, dest: str, people: int = 1, limit: int = 5) -> dict:
    """返回直达最低价、最多 ``limit`` 条更便宜的中转方案与最便候选方案。"""
    if origin == dest:
        raise ValueError("same_city")
    if origin not in CITY_COORDS or dest not in CITY_COORDS:
        raise ValueError("unknown_city")

    quote_cache: dict[tuple[str, str, str], tuple[int, int]] = {}

    def quote(mode: str, a: str, b: str) -> tuple[int, int]:
        key = (mode, a, b)
        if key not in quote_cache:
            quote_cache[key] = _train_quote(a, b) if mode == "train" else _flight_quote(a, b)
        return quote_cache[key]

    direct_train_price, direct_train_min = quote("train", origin, dest)
    direct_flight_price, direct_flight_min = quote("flight", origin, dest)
    if direct_train_price <= direct_flight_price:
        direct_total, direct_duration = direct_train_price, direct_train_min
    else:
        direct_total, direct_duration = direct_flight_price, direct_flight_min

    threshold = direct_total * people * 0.95
    all_options: list[dict] = []
    for via in _candidates(origin, dest):
        for first_mode, second_mode in _COMBOS:
            price1, duration1 = quote(first_mode, origin, via)
            price2, duration2 = quote(second_mode, via, dest)
            total = round((price1 + price2) * people)
            all_options.append(
                {
                    "via": via,
                    "via_province": province_of(via),
                    "total": total,
                    "save": round(direct_total * people) - total,
                    "duration_min": duration1 + duration2,
                    "summary": f"{via}中转：{_MODE_LABELS[first_mode]}→{_MODE_LABELS[second_mode]}",
                    "legs": [
                        {
                            "mode": first_mode,
                            "from": origin,
                            "to": via,
                            "price": price1,
                            "duration_min": duration1,
                        },
                        {
                            "mode": second_mode,
                            "from": via,
                            "to": dest,
                            "price": price2,
                            "duration_min": duration2,
                        },
                    ],
                }
            )

    options = [option for option in all_options if option["total"] < threshold]
    options.sort(key=lambda option: (-option["save"], option["duration_min"]))
    options = options[:limit]

    best = min(all_options, key=lambda option: (option["total"], option["duration_min"]), default=None)

    return {
        "origin": origin,
        "dest": dest,
        "people": people,
        "direct": {"total": direct_total, "duration_min": direct_duration},
        "options": options,
        "best": best,
        "note": NOTE if options else NOTE_NO_OPTION,
    }