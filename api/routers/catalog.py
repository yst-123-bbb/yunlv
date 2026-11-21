"""城市与景点目录路由：城市目录、景点目录、搜索与热门推荐。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from services import ai_config, catalog_service, reco_service

router = APIRouter(prefix="/api", tags=["catalog"])


def _call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return func(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc.args[0])) from exc


@router.get("/cities")
def list_cities() -> dict[str, list[dict]]:
    return {"items": _call(catalog_service.list_cities)}


@router.get("/cities/{name}")
def get_city(name: str) -> dict:
    return _call(catalog_service.get_city, name)


@router.get("/attractions")
def list_attractions(city: str | None = None, limit: int = 12) -> dict[str, list[dict]]:
    return {"items": _call(catalog_service.list_attractions, city, limit)}


@router.get("/attractions/{name}")
def get_attraction(name: str) -> dict:
    return {"attraction": _call(catalog_service.get_attraction, name)}


@router.get("/search")
def search(q: str) -> dict[str, list[dict]]:
    return _call(catalog_service.search, q)


@router.get("/search/hot")
def hot() -> dict[str, list[dict]]:
    return _call(catalog_service.hot)

@router.get("/attractions/{name}/xiaohongshu")
def attraction_xiaohongshu(name: str, request: Request) -> dict:
    cfg = ai_config.from_headers(request.headers)
    return _call(reco_service.attraction_reco, name, cfg)


@router.get("/cities/{name}/xiaohongshu")
def city_xiaohongshu(name: str, request: Request) -> dict:
    cfg = ai_config.from_headers(request.headers)
    return _call(reco_service.city_reco, name, cfg)