"""分项预算、分档与削减模拟测试。"""

from __future__ import annotations

import pytest

from core.budget import BudgetBreakdown, assert_balanced, calculate_budget
from core.budget_tiers import simulate_cut, tier_range
from services.budget_service import compute

USER_DATA = {
    "people": 2,
    "days": 3,
    "budget": 3000,
    "_avg_food": 100,
    "shopping": 200,
}
TRANSPORT = {"price_per_person": 500}
ATTRACTIONS = [
    {"name": "岳麓山", "ticket_price": 100, "day": 2},
    {"name": "橘子洲", "ticket_price": 50, "day": 2},
]
HOTEL = {"name": "长沙某酒店", "price": 300}


def _plan() -> dict:
    return {
        "user_data": dict(USER_DATA),
        "transport": dict(TRANSPORT),
        "attractions": [dict(a) for a in ATTRACTIONS],
        "hotel": dict(HOTEL),
        "city_mode": "bus",
    }


def test_seven_items_sum_to_grand_total() -> None:
    b = calculate_budget(USER_DATA, TRANSPORT, ATTRACTIONS, HOTEL, "bus")

    assert isinstance(b, BudgetBreakdown)
    total = b.transport + b.hotel + b.tickets + b.food + b.city_transport + b.shopping + b.reserve
    assert total == pytest.approx(b.grand_total, abs=0.01)
    assert b.per_person == pytest.approx(b.grand_total / 2, abs=0.01)
    assert b.grand_total > 0


def test_reserve_is_ten_percent() -> None:
    b = calculate_budget(USER_DATA, TRANSPORT, ATTRACTIONS, HOTEL, "bus")

    without_reserve = b.grand_total - b.reserve
    assert b.reserve == pytest.approx(without_reserve * 0.1, abs=0.01)


def test_child_and_senior_ticket_discount() -> None:
    full = calculate_budget(USER_DATA, None, ATTRACTIONS, None, "bus")

    discounted = calculate_budget(
        {**USER_DATA, "children": 1, "seniors": 1},
        None,
        ATTRACTIONS,
        None,
        "bus",
    )

    assert full.tickets == pytest.approx(150 * 2)
    assert discounted.tickets == pytest.approx(150 * (0.5 + 0.8))
    assert discounted.tickets < full.tickets


def test_assert_balanced_rejects_mismatch() -> None:
    b = calculate_budget(USER_DATA, TRANSPORT, ATTRACTIONS, HOTEL, "bus")
    broken = b.model_copy(update={"grand_total": b.grand_total + 1})

    with pytest.raises(ValueError, match="budget_not_balanced"):
        assert_balanced(broken)


def test_tier_range_increases_with_tier() -> None:
    economy = tier_range("economy", 3, 2)
    comfort = tier_range("comfort", 3, 2)
    quality = tier_range("quality", 3, 2)

    assert economy[0] < comfort[0] < quality[0]
    assert economy[1] < comfort[1] < quality[1]


def test_tier_range_discounts_children_and_seniors() -> None:
    base = tier_range("comfort", 3, 4)
    discounted = tier_range("comfort", 3, 4, children=1, seniors=1)

    assert discounted[0] < base[0]
    assert discounted[1] < base[1]


def test_simulate_cut_remove_place() -> None:
    result = simulate_cut(_plan(), {"kind": "remove_place", "day": 2, "name": "岳麓山"})

    assert result["before"] == pytest.approx(_plan_total())
    assert result["save"] == pytest.approx(100 * 2 * 1.1, abs=0.05)
    assert result["after"] == pytest.approx(result["before"] - result["save"], abs=0.01)
    assert "岳麓山" in result["explain"]


def test_simulate_cut_swap_hotel() -> None:
    result = simulate_cut(_plan(), {"kind": "swap_hotel", "day": 2, "price": 200})

    assert result["save"] == pytest.approx((300 - 200) * 2 * 1.1, abs=0.05)
    assert result["after"] < result["before"]


def test_simulate_cut_swap_transport() -> None:
    result = simulate_cut(_plan(), {"kind": "swap_transport", "price": 420})

    assert result["save"] == pytest.approx((500 - 420) * 2 * 2 * 1.1, abs=0.05)
    assert result["after"] == pytest.approx(result["before"] - result["save"], abs=0.01)


def test_simulate_cut_missing_target_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        simulate_cut(_plan(), {"kind": "remove_place", "day": 2, "name": "不存在的景点"})

    with pytest.raises(KeyError):
        simulate_cut({**_plan(), "hotel": None}, {"kind": "swap_hotel", "price": 200})


def _plan_total() -> float:
    return calculate_budget(USER_DATA, TRANSPORT, ATTRACTIONS, HOTEL, "bus").grand_total


def test_compute_returns_breakdown_from_session() -> None:
    session = {
        "session_id": "abc123",
        "user_data": dict(USER_DATA),
        "transport": dict(TRANSPORT),
        "chosen_plan": {"attractions": [dict(a) for a in ATTRACTIONS], "hotel": dict(HOTEL)},
        "itinerary": [],
        "city_mode": "bus",
    }

    b = compute(session)

    assert isinstance(b, BudgetBreakdown)
    assert b == calculate_budget(USER_DATA, TRANSPORT, ATTRACTIONS, HOTEL, "bus")