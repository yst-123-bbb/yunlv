"""城际交通查询路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from providers.registry import registry
from services import transfer_service

router = APIRouter(prefix="/api/transport", tags=["transport"])


@router.get("")
def search_transport(origin: str, dest: str, date: str) -> dict[str, Any]:
    offers, attempted = registry.search("transport", origin=origin, dest=dest, date=date)
    return {"offers": offers, "attempted": attempted}


@router.get("/transfers")
def search_transfers(origin: str, dest: str, people: int = 1, limit: int = 5) -> dict[str, Any]:
    return transfer_service.find_transfers(origin, dest, people=people, limit=limit)