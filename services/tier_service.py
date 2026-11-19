# -*- coding: utf-8 -*-
"""预算分档服务：三档区间适配度与削减模拟建议。"""
from __future__ import annotations

import copy
from typing import Any

from core import budget_tiers
from services import budget_service, plan_service

TIERS: tuple[tuple[str, str], ...] = (
    ("economy", "经济"),
    ("comfort", "舒适"),
    ("quality", "品质"),
)

MAX_CUTS = 4


def _build_plan(session: plan_service.PlanSession) -> dict[str, Any]:
    chosen = session.chosen_plan or {}
    attractions = list(chosen.get("attractions") or [])
    hotel = chosen.get("hotel") or (chosen.get("hotels") or [None])[0]
    return {
        "user_data": dict(session.user_data),
        "transport": session.transport,
        "attractions": copy.deepcopy(attractions),
        "hotel": copy.deepcopy(hotel) if isinstance(hotel, dict) else None,
        "city_mode": session.user_data.get("city_mode"),
    }


def _cut_attempts(session: plan_service.PlanSession, plan: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = sorted(
        (item for item in plan["attractions"] if isinstance(item, dict)),
        key=lambda item: float(item.get("ticket_price") or 0),
        reverse=True,
    )
    attempts: list[dict[str, Any]] = [
        {"kind": "remove_place", "name": item.get("name")}
        for item in ranked[:3]
        if item.get("name")
    ]

    hotel = plan["hotel"]
    if isinstance(hotel, dict) and hotel.get("price"):
        attempts.append({"kind": "swap_hotel", "price": round(float(hotel["price"]) * 0.6, 2)})

    transport = session.transport
    if isinstance(transport, dict) and transport.get("price_per_person"):
        attempts.append(
            {
                "kind": "swap_transport",
                "price": round(float(transport["price_per_person"]) * 0.6, 2),
            }
        )
    return attempts


def _cuts(session: plan_service.PlanSession, plan: dict[str, Any]) -> list[dict[str, Any]]:
    cuts: list[dict[str, Any]] = []
    for attempt in _cut_attempts(session, plan):
        if len(cuts) >= MAX_CUTS:
            break
        try:
            result = budget_tiers.simulate_cut(plan, attempt)
        except (KeyError, ValueError):
            # 单个削减方案在当前行程下不可行时直接跳过，不阻断整体建议
            continue
        if float(result.get("save") or 0) <= 0:
            continue
        cuts.append(
            {
                "kind": attempt["kind"],
                "label": result["explain"],
                "save": result["save"],
                "explain": result["explain"],
            }
        )
    return cuts


def summary(session_id: str) -> dict[str, Any]:
    session = plan_service.get(session_id)
    user_data = session.user_data
    days = max(int(user_data.get("days") or len(session.itinerary) or 1), 1)
    people = max(int(user_data.get("people") or 1), 1)
    children = int(user_data.get("children") or 0)
    seniors = int(user_data.get("seniors") or 0)
    current_total = round(float(budget_service.compute(session).grand_total), 2)

    plan = _build_plan(session)
    cuts = _cuts(session, plan)

    tiers: list[dict[str, Any]] = []
    highs: dict[str, float] = {}
    for tier, label in TIERS:
        low, high = budget_tiers.tier_range(tier, days, people, children, seniors)
        if current_total < low:
            fit = "under"
        elif current_total > high:
            fit = "over"
        else:
            fit = "within"
        highs[tier] = high
        tiers.append(
            {
                "tier": tier,
                "label": label,
                "low": low,
                "high": high,
                "fit": fit,
                "cuts": [dict(cut) for cut in cuts],
            }
        )

    return {
        "session_id": str(session.session_id),
        "days": days,
        "people": people,
        "current_total": current_total,
        "tiers": tiers,
        "gap": {
            "to_economy": round(max(current_total - highs["economy"], 0), 2),
            "to_comfort": round(max(current_total - highs["comfort"], 0), 2),
        },
    }