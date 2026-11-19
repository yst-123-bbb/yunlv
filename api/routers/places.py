"""景点检索路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from providers.registry import registry

router = APIRouter(prefix="/api/places", tags=["places"])


@router.get("")
def search_places(city: str, keyword: str = "", limit: int = 15) -> dict[str, Any]:
    items, attempted = registry.search("place", city=city, keyword=keyword, limit=limit)
    return {"items": items, "attempted": attempted}