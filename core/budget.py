# -*- coding: utf-8 -*-
"""分项预算核算：交通/住宿/门票/餐饮/市内交通/购物/备用金。"""
from __future__ import annotations

from pydantic import BaseModel

from infra.logging_setup import get_logger, log_event

logger = get_logger(__name__)

CHILD_TICKET_RATE = 0.5
SENIOR_TICKET_RATE = 0.8
RESERVE_RATE = 0.1

CITY_TRANSPORT_RATES = {
    "subway": 30.0,
    "taxi": 120.0,
    "bus": 60.0,
}


class BudgetBreakdown(BaseModel):
    transport: float
    hotel: float
    tickets: float
    food: float
    city_transport: float
    shopping: float
    reserve: float
    grand_total: float
    per_person: float


def _city_transport_cost(city_mode: str, people: int, days: int) -> float:
    if city_mode == "rent":
        return 300.0 * days + 80.0 * days
    return CITY_TRANSPORT_RATES.get(city_mode, CITY_TRANSPORT_RATES["bus"]) * people * days


def _ticket_adult_equivalent(user_data: dict, people: int) -> tuple[float, int, int]:
    """儿童/老人对门票按成人价的固定比例折算，其余人按全价。"""
    children = min(max(int(user_data.get("children", 0) or 0), 0), people)
    seniors = min(max(int(user_data.get("seniors", 0) or 0), 0), people - children)
    adults = people - children - seniors
    equivalent = adults + children * CHILD_TICKET_RATE + seniors * SENIOR_TICKET_RATE
    return equivalent, children, seniors


def calculate_budget(
    user_data: dict,
    transport_plan: dict | None,
    attractions: list[dict],
    hotel: dict | None,
    city_mode: str,
) -> BudgetBreakdown:
    people = max(int(user_data.get("people", 2) or 1), 1)
    days = max(int(user_data.get("days", 3) or 0), 0)

    transport = 0.0
    if transport_plan:
        transport = float(transport_plan.get("price_per_person", 0) or 0) * people * 2

    city_transport = _city_transport_cost(city_mode, people, days)

    adult_equivalent, _children, _seniors = _ticket_adult_equivalent(user_data, people)
    tickets = sum(max(float(a.get("ticket_price", 0) or 0), 0.0) for a in attractions) * adult_equivalent

    avg_food = float(user_data.get("_avg_food", 0) or 0) or 80.0
    food = (25 + avg_food * 0.8 + avg_food + 15) * people * days

    hotel_nights = max(days - 1, 0)
    hotel_cost = 0.0
    if hotel and hotel_nights > 0:
        price = hotel.get("price", hotel.get("price_per_night", 300))
        hotel_cost = float(price or 0) * hotel_nights

    shopping = max(float(user_data.get("shopping", user_data.get("shopping_budget", 0)) or 0), 0.0)

    breakdown = {
        "transport": round(transport, 2),
        "hotel": round(hotel_cost, 2),
        "tickets": round(tickets, 2),
        "food": round(food, 2),
        "city_transport": round(city_transport, 2),
        "shopping": round(shopping, 2),
    }
    subtotal = round(sum(breakdown.values()), 2)
    reserve = round(subtotal * RESERVE_RATE, 2)
    grand_total = round(subtotal + reserve, 2)

    result = BudgetBreakdown(
        **breakdown,
        reserve=reserve,
        grand_total=grand_total,
        per_person=round(grand_total / people, 2),
    )
    log_event(
        logger,
        "budget_calculated",
        outcome="ok",
        provider="core.budget",
        grand_total=result.grand_total,
        people=people,
        days=days,
    )
    return result


def assert_balanced(b: BudgetBreakdown, tol: float = 0.01) -> None:
    items = (
        b.transport
        + b.hotel
        + b.tickets
        + b.food
        + b.city_transport
        + b.shopping
        + b.reserve
    )
    if abs(items - b.grand_total) > tol:
        log_event(
            logger,
            "budget_not_balanced",
            outcome="error",
            provider="core.budget",
            error="budget_not_balanced",
        )
        raise ValueError("budget_not_balanced")