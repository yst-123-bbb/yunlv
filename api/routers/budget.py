"""预算查询路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from services import budget_service, plan_service, tier_service

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("")
def get_budget(session_id: str) -> Any:
    session = plan_service.get(session_id)
    return budget_service.compute(session)


@router.get("/tiers")
def get_budget_tiers(session_id: str) -> Any:
    return tier_service.summary(session_id)