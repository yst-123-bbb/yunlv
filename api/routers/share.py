"""只读分享存取路由。"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from services import plan_service

router = APIRouter(prefix="/api/share", tags=["share"])

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class ShareBody(BaseModel):
    session_id: str


@router.post("")
def create_share(body: ShareBody) -> dict[str, str]:
    # 导出服务依赖 Playwright 等可选运行环境，延迟导入以避免启动期硬耦合
    from services import export_service

    session = plan_service.get(body.session_id)
    short_id = export_service.save_share(session)
    base_url = os.getenv("APP_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    return {"short_id": short_id, "url": f"{base_url}/share/{short_id}"}


@router.get("/{short_id}")
def read_share(short_id: str) -> dict[str, Any]:
    from services import export_service

    return {"plan": export_service.load_share(short_id)}