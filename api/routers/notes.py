"""游记单链解析路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from providers.registry import registry

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteBody(BaseModel):
    url: str


@router.post("")
def fetch_note(body: NoteBody) -> Any:
    items, _attempted = registry.search("note", url=body.url)
    if not items:
        raise HTTPException(status_code=404, detail="note_not_found")
    return items[0]