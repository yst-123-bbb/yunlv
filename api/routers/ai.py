# -*- coding: utf-8 -*-
"""AI 连通性测试端点：用请求头里的用户 Key 试打一次，永不返回 5xx。"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Request

from services import ai_config

router = APIRouter(prefix="/api/ai", tags=["ai"])

_PING_TIMEOUT_S = 20.0


@router.post("/ping")
def ping(request: Request) -> dict[str, Any]:
    cfg = ai_config.from_headers(request.headers)
    if cfg is None:
        return {"ok": False, "provider": "none", "model": "", "message": "未提供 API Key"}

    payload = {
        "model": cfg.model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
    }
    try:
        response = httpx.post(
            cfg.base_url,
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            json=payload,
            timeout=_PING_TIMEOUT_S,
        )
        response.raise_for_status()
    except Exception as exc:
        # 异常文本可能回显请求头，返回前统一抹掉 Key
        message = f"{type(exc).__name__}: {exc}".replace(cfg.api_key, "***")
        return {"ok": False, "provider": "custom", "model": cfg.model, "message": message}

    return {"ok": True, "provider": "custom", "model": cfg.model, "message": "连接成功"}