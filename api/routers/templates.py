"""行程模板路由：列表、按名读取与保存。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import plan_service, template_service

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateBody(BaseModel):
    name: str
    session_id: str


@router.get("")
def list_template_names() -> dict[str, list[str]]:
    return {"items": template_service.list_templates()}


@router.post("")
def create_template(body: TemplateBody) -> dict[str, str]:
    try:
        session = plan_service.get(body.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session_not_found") from exc
    try:
        name = template_service.save_template(body.name, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_template_name") from exc
    return {"name": name}


@router.get("/{name}")
def read_template(name: str) -> dict[str, Any]:
    try:
        state = template_service.load_template(name)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="template_not_found") from exc
    return {"state": state}