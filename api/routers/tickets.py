"""门票查询路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from providers.registry import registry

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("")
def search_tickets(place: str, city: str) -> dict[str, Any]:
    offers, attempted = registry.search("ticket", place_name=place, city=city)
    return {"offers": offers, "attempted": attempted}