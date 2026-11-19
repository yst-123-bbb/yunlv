# -*- coding: utf-8 -*-
"""预算服务：从会话状态装配七项预算。"""
from __future__ import annotations

from core.budget import BudgetBreakdown, assert_balanced, calculate_budget
from infra.logging_setup import get_logger, log_event

logger = get_logger(__name__)


def _pick(source: object, key: str, default=None):
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _resolve_hotel(session: object) -> dict | None:
    chosen_plan = _pick(session, "chosen_plan") or {}
    if isinstance(chosen_plan, dict):
        hotel = chosen_plan.get("hotel") or chosen_plan.get("chosen_hotel")
        if isinstance(hotel, dict):
            return hotel
        hotels = chosen_plan.get("hotels") or []
        if hotels and isinstance(hotels[0], dict):
            return hotels[0]
    itinerary = _pick(session, "itinerary")
    if isinstance(itinerary, dict):
        hotel = itinerary.get("chosen_hotel")
        if isinstance(hotel, dict):
            return hotel
    hotel = _pick(session, "hotel")
    return hotel if isinstance(hotel, dict) else None


def compute(session: object) -> BudgetBreakdown:
    user_data = _pick(session, "user_data") or {}
    chosen_plan = _pick(session, "chosen_plan") or {}
    attractions = chosen_plan.get("attractions") if isinstance(chosen_plan, dict) else None
    if attractions is None:
        attractions = _pick(session, "attractions") or []

    breakdown = calculate_budget(
        user_data,
        _pick(session, "transport"),
        attractions,
        _resolve_hotel(session),
        user_data.get("city_mode")
        or _pick(session, "city_mode")
        or user_data.get("hotel_location")
        or "subway",
    )
    assert_balanced(breakdown)
    log_event(
        logger,
        "budget_computed",
        outcome="ok",
        provider="services.budget_service",
        grand_total=breakdown.grand_total,
        session_id=_pick(session, "session_id"),
    )
    return breakdown