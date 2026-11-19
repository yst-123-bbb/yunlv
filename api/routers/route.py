"""两点间路线规划路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from providers import amap

router = APIRouter(prefix="/api/route", tags=["route"])


def _as_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    dump = getattr(result, "model_dump", None)
    if callable(dump):
        return dump()
    return dict(vars(result))


@router.get("")
def plan_route(
    from_lng: float,
    from_lat: float,
    to_lng: float,
    to_lat: float,
    mode: str = "driving",
) -> dict[str, Any]:
    data = _as_dict(amap.route(from_lng, from_lat, to_lng, to_lat, mode))
    return {
        "distance_m": int(data.get("distance_m") or 0),
        "duration_s": int(data.get("duration_s") or 0),
        "polyline": str(data.get("polyline") or ""),
    }