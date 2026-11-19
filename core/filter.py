# -*- coding: utf-8 -*-
"""数据筛选模块 - 交通/景点/美食/住宿 按用户偏好智能筛选"""
import sys
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE = os.path.dirname(_THIS_DIR)
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from utils.helpers import dedup


def filter_transport(trains, flights, user_data):
    """筛选交通方案"""
    pref = user_data.get("transport_pref", "both")
    budget = float(user_data.get("budget", 3000))
    people = int(user_data.get("people", 2))
    per_person_budget = budget / people

    filtered_trains = []
    for t in trains:
        try:
            price = t.get("seats", {}).get("二等座", 0)
            if price <= per_person_budget * 0.4:
                filtered_trains.append(t)
        except Exception:
            continue

    filtered_flights = []
    for f in flights:
        try:
            price = f.get("cabin", {}).get("经济舱", 0)
            if price <= per_person_budget * 0.5:
                filtered_flights.append(f)
        except Exception:
            continue

    if pref == "train":
        return {"trains": filtered_trains[:5], "flights": []}
    elif pref == "flight":
        return {"trains": [], "flights": filtered_flights[:5]}
    else:
        return {
            "trains": filtered_trains[:3],
            "flights": filtered_flights[:3],
        }


def filter_attractions(attractions, user_data):
    """筛选景点 - 根据年龄/偏好/预算/时间"""
    prefs = user_data.get("attraction_prefs", [])
    age = user_data.get("age_group", "youth")
    days = int(user_data.get("days", 3))
    budget = float(user_data.get("budget", 3000))
    people = int(user_data.get("people", 2))

    scored = []
    for a in attractions:
        score = 0
        tags = a.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        if "culture" in prefs and "人文古迹" in tags:
            score += 30
        if "nature" in prefs and "自然风光" in tags:
            score += 30
        if "internet" in prefs and "网红打卡" in tags:
            score += 30
        if "theme" in prefs and "主题乐园" in tags:
            score += 30
        if "food_tour" in prefs and "美食文化" in tags:
            score += 30
        if "shopping" in prefs and "购物" in tags:
            score += 20

        ticket = float(a.get("ticket_price", 0))
        if ticket == 0:
            score += 10
        elif ticket > budget * 0.05 * people:
            score -= 5

        likes = float(a.get("likes", 10000))
        score += min(likes / 5000, 20)

        if age == "senior" and not a.get("indoor", False):
            score -= 5
        if age == "family" and a.get("indoor", True):
            score += 5

        scored.append((score, a))

    scored.sort(key=lambda x: x[0], reverse=True)
    max_attrs = days * 2 + 2
    result = [item[1] for item in scored[:max_attrs]]
    return dedup(result)


def filter_food(foods, user_data):
    """筛选美食 - 根据口味/场景/预算"""
    tastes = user_data.get("tastes", [])
    budget = float(user_data.get("budget", 3000))
    people = int(user_data.get("people", 2))
    avg_budget = budget / people / 3

    scored = []
    for f in foods:
        score = 0
        tags = f.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        if "light" in tastes and "不辣" in tags:
            score += 25
        if "mild" in tastes and "微辣" in tags:
            score += 20
        if "spicy" in tastes and "重辣" in tags:
            score += 25
        if "seafood" in tastes and ("海鲜" in f.get("cuisine", "") or "日料" in f.get("cuisine", "")):
            score += 15
        if "local" in tastes and ("小吃" in tags or "湘菜" in f.get("cuisine", "") or "京菜" in f.get("cuisine", "")):
            score += 20

        price = float(f.get("avg_price", 80))
        if price <= avg_budget:
            score += 15
        elif price > avg_budget * 1.5:
            score -= 10

        likes = float(f.get("likes", 5000))
        score += min(likes / 3000, 15)

        scored.append((score, f))

    scored.sort(key=lambda x: x[0], reverse=True)
    result = [item[1] for item in scored[:8]]
    return dedup(result)


def filter_hotels(hotels, user_data):
    """筛选住宿 - 按预算/位置偏好/年龄"""
    budget = float(user_data.get("budget", 3000))
    people = int(user_data.get("people", 2))
    days = int(user_data.get("days", 3))
    hotel_level = user_data.get("hotel_level", "mid")
    location = user_data.get("hotel_location", "subway")
    age = user_data.get("age_group", "youth")

    per_night_budget = budget * 0.25 / max(1, days - 1) if days > 1 else budget * 0.1

    level_ranges = {
        "budget": (0, 350), "mid": (250, 650),
        "high": (500, 99999), "bnb": (200, 700),
    }
    min_p, max_p = level_ranges.get(hotel_level, (200, 600))
    if hotel_level == "budget":
        max_p = min(max_p, per_night_budget + 100)

    scored = []
    for h in hotels:
        score = 0
        price = float(h.get("price", 300))

        if min_p <= price <= max_p:
            score += 30
        elif price < min_p:
            score += 10
        else:
            continue

        if h.get("location") == location:
            score += 20
        elif location == "subway" and h.get("location") in ["center", "subway"]:
            score += 10

        dist = str(h.get("distance", ""))
        if "步行" in dist or "米" in dist:
            score += 10

        if age in ["family", "senior"]:
            if "免费" in h.get("facilities", ""):
                score += 10

        reviews = str(h.get("reviews", ""))
        if "4.7" in reviews or "4.8" in reviews:
            score += 10
        elif "4.6" in reviews:
            score += 5

        scored.append((score, h))

    scored.sort(key=lambda x: x[0], reverse=True)
    result = [item[1] for item in scored[:6]]
    return dedup(result)


_PLACE_FILTERS = {
    "attraction": filter_attractions,
    "food": filter_food,
    "restaurant": filter_food,
    "hotel": filter_hotels,
}


def _as_mapping(item):
    """把地点条目转为筛选逻辑可读的 dict 副本，原始对象由调用方保留"""
    if isinstance(item, dict):
        mapping = dict(item)
    else:
        dump = getattr(item, "model_dump", None)
        if not callable(dump):
            return item
        mapping = dump()

    if not mapping.get("tags"):
        tags = mapping.get("features") or (
            [mapping["type"]] if mapping.get("type") else None
        )
        if tags:
            mapping["tags"] = tags
    if "ticket_price" not in mapping and mapping.get("avg_price") is not None:
        mapping["ticket_price"] = mapping["avg_price"]
    if "indoor" not in mapping and "is_indoor" in mapping:
        mapping["indoor"] = mapping["is_indoor"]
    return mapping


def filter_places(items, user_data, kind="attraction"):
    """按品类筛选地点结果，兼容 dict 与 PlaceItem；返回与入参同样的对象类型"""
    items = list(items or [])
    scorer = _PLACE_FILTERS.get(kind)
    if scorer is None or not items:
        return items

    mappings = []
    origin = {}
    for item in items:
        mapping = _as_mapping(item)
        mappings.append(mapping)
        if mapping is not item:
            origin[id(mapping)] = item

    picked = scorer(mappings, user_data or {})
    return [origin.get(id(p), p) for p in picked]


def filter_all(trains, flights, attractions, foods, hotels, user_data):
    """统一筛选入口"""
    transport = filter_transport(trains, flights, user_data)
    return {
        "trains": transport["trains"],
        "flights": transport["flights"],
        "attractions": filter_attractions(attractions, user_data),
        "foods": filter_food(foods, user_data),
        "hotels": filter_hotels(hotels, user_data),
    }