"""自由制定对话路由：外呼失败已在服务层降级，这里只校验入参。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services import ai_config, chat_service

router = APIRouter(prefix="/api", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatBody(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    prefs: dict[str, Any] | None = None


@router.post("/chat")
def chat(body: ChatBody, request: Request) -> dict[str, Any]:
    try:
        return chat_service.reply(
            [item.model_dump() for item in body.messages],
            body.prefs,
            ai_config.from_headers(request.headers),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc