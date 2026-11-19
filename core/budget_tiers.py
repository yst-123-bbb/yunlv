# -*- coding: utf-8 -*-
"""预算分档区间与削减模拟。"""
from __future__ import annotations

from typing import Literal

from core.budget import (
    CHILD_TICKET_RATE,
    SENIOR_TICKET_RATE,
    assert_balanced,
    calculate_budget,
)
from infra.logging_setup import get_logger, log_event

logger = get_logger(__name__)

Tier = Literal["economy", "comfort", "quality"]

# 人均每天的预算区间（含住宿、餐饮、交通与门票）
TIER_DAILY_RANGE: dict[str, tuple[float, float]] = {
    "economy": (300.0, 600.0),
    "comfort": (600.0, 1200.0),
    "quality": (1200.0, 2500.0),
}


def tier_range(
    tier: Tier,
    days: int,
    people: int,
    children: int = 0,
    seniors: int = 0,
) -> tuple[float, float]:
    if tier not in TIER_DAILY_RANGE:
        raise KeyError("unknown_tier")
    low, high = TIER_DAILY_RANGE[tier]

    people = max(int(people), 1)
    days = max(int(days), 0)
    children = min(max(int(children), 0), people)
    seniors = min(max(int(seniors), 0), people - children)
    adults = people - children - seniors
    adult_equivalent = adults + children * CHILD_TICKET_RATE + seniors * SENIOR_TICKET_RATE

    factor = days * adult_equivalent
    return round(low * factor, 2), round(high * factor, 2)


def _plan_total(plan: dict) -> float:
    user_data = plan.get("user_data") or {}
    breakdown = calculate_budget(
        user_data,
        plan.get("transport"),
        plan.get("attractions") or [],
        plan.get("hotel"),
        plan.get("city_mode") or user_data.get("city_mode") or "bus",
    )
    assert_balanced(breakdown)
    return breakdown.grand_total


def _match_place(attractions: list[dict], name: str, day: int | None) -> int:
    for index, attraction in enumerate(attractions):
        if attraction.get("name") != name:
            continue
        if day is not None and attraction.get("day") is not None and attraction["day"] != day:
            continue
        return index
    raise KeyError(f"place_not_found:{name}")


def simulate_cut(plan: dict, cut: dict) -> dict:
    kind = cut.get("kind")
    next_plan = {
        "user_data": dict(plan.get("user_data") or {}),
        "transport": dict(plan["transport"]) if plan.get("transport") else None,
        "attractions": [dict(a) for a in (plan.get("attractions") or [])],
        "hotel": dict(plan["hotel"]) if plan.get("hotel") else None,
        "city_mode": plan.get("city_mode"),
    }

    if kind == "remove_place":
        name = cut["name"]
        index = _match_place(next_plan["attractions"], name, cut.get("day"))
        next_plan["attractions"].pop(index)
        explain = f"去掉景点 {name}，减少门票支出"
    elif kind == "swap_hotel":
        if not next_plan["hotel"]:
            raise KeyError("hotel_not_found")
        next_plan["hotel"]["price"] = float(cut["price"])
        next_plan["hotel"].pop("price_per_night", None)
        explain = f"更换酒店，每晚由 {plan['hotel'].get('price', 0)} 元改为 {cut['price']} 元"
    elif kind == "swap_transport":
        if not next_plan["transport"]:
            raise KeyError("transport_not_found")
        next_plan["transport"]["price_per_person"] = float(cut["price"])
        explain = f"更换交通，单程人均由 {plan['transport'].get('price_per_person', 0)} 元改为 {cut['price']} 元"
    else:
        raise ValueError(f"unknown_cut_kind:{kind}")

    before = _plan_total(plan)
    after = _plan_total(next_plan)
    save = round(before - after, 2)
    result = {
        "before": before,
        "after": after,
        "save": save,
        "explain": f"{explain}，总预算 {before} 元 → {after} 元，{'省下' if save >= 0 else '增加'} {abs(save)} 元",
    }
    log_event(
        logger,
        "budget_cut_simulated",
        outcome="ok",
        provider="core.budget_tiers",
        kind=kind,
        save=save,
    )
    return result