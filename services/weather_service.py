# -*- coding: utf-8 -*-
"""天气联动重排：把户外行程项替换为室内备选，并把结果落库。"""

from __future__ import annotations

from typing import Any

from core.weather_planner import replan_for_weather
from data.place_catalog import ATTRACTIONS
from services import plan_service, profile_service


def replan(session_id: str, weather_by_day: dict) -> dict:
    session = plan_service.get(session_id)
    if not isinstance(weather_by_day, dict) or not weather_by_day:
        raise ValueError("invalid_weather")

    pool = _attraction_pool(session)
    if not pool:
        raise ValueError("no_places")

    new_itinerary, notes = replan_for_weather(session.itinerary, pool, weather_by_day)
    session = plan_service.replace_itinerary(session_id, new_itinerary)
    return {
        "itinerary": session.itinerary,
        "notes": notes,
        "state": profile_service.enrich_state(session),
    }


def _attraction_pool(session: Any) -> list[dict]:
    """按会话城市拼出候选景点池，每条补上 city 以便前端展示与校验。"""
    user_data = session.user_data or {}
    cities = [
        str(entry.get("city") or "")
        for entry in (user_data.get("cities") or [])
        if isinstance(entry, dict)
    ]
    cities = [city for city in cities if city]
    if not cities:
        cities = [str(user_data.get("destination") or "")]

    pool: list[dict] = []
    for city in cities:
        for place in ATTRACTIONS.get(city) or []:
            if not isinstance(place, dict):
                continue
            pool.append({**place, "city": city})
    return pool