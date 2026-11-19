"""网友评语只读路由：按城市或景点名取已采集的评语。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services import comment_service

router = APIRouter(prefix="/api", tags=["comments"])


@router.get("/comments")
def list_comments(target: str, limit: int = 5) -> dict[str, list[dict]]:
    try:
        items = comment_service.list_comments(target, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": items}