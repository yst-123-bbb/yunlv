"""纠错与审核路由：提交纠错、查询待审项、审核决策。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from datastore import db
from datastore.repository import enqueue_review, upsert_field

router = APIRouter(prefix="/api/review", tags=["review"])

_TZ = timezone(timedelta(hours=8))

_STATUS_BY_ACTION: dict[str, str] = {
    "approve": "approved",
    "reject": "rejected",
    "merge": "merged",
}

_ITEM_COLUMNS = (
    "id, entity_id, field_name, proposed_value_json, current_value_json, "
    "reason, status, created_at"
)


def _now() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")


def _decode(text: str | None) -> Any:
    if text is None:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def _to_item(row: Any) -> ReviewItem:
    return ReviewItem(
        id=int(row["id"]),
        entity_id=None if row["entity_id"] is None else int(row["entity_id"]),
        field_name=row["field_name"],
        proposed_value=_decode(row["proposed_value_json"]),
        current_value=_decode(row["current_value_json"]),
        reason=row["reason"],
        status=row["status"],
        created_at=row["created_at"],
    )


class ReviewItem(BaseModel):
    id: int
    entity_id: int | None = None
    field_name: str
    proposed_value: Any = None
    current_value: Any = None
    reason: str
    status: str
    created_at: str


class ReviewSubmitBody(BaseModel):
    entity_id: int | None = None
    field_name: str
    proposed_value: Any = None
    reason: str
    raw_excerpt: str | None = None


class ReviewDecideBody(BaseModel):
    action: Literal["approve", "reject", "merge"]
    note: str


@router.get("")
def list_review(status: str = "pending") -> dict[str, list[ReviewItem]]:
    conn = db.connect()
    try:
        rows = conn.execute(
            f"SELECT {_ITEM_COLUMNS} FROM review_queue WHERE status = ? ORDER BY id",
            (status,),
        ).fetchall()
    finally:
        conn.close()
    return {"items": [_to_item(row) for row in rows]}


@router.post("")
def submit_review(body: ReviewSubmitBody) -> dict[str, int]:
    conn = db.connect()
    try:
        with db.transaction(conn):
            item_id = enqueue_review(
                conn,
                entity_id=body.entity_id,
                field_name=body.field_name,
                proposed=body.proposed_value,
                current=None,
                reason=body.reason,
                raw_excerpt=body.raw_excerpt,
            )
    finally:
        conn.close()
    return {"id": item_id}


@router.post("/{item_id}/decide")
def decide_review(item_id: int, body: ReviewDecideBody) -> dict[str, bool]:
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT entity_id, field_name, proposed_value_json, status "
            "FROM review_queue WHERE id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="review_not_found")
        if row["status"] != "pending":
            return {"ok": True}

        with db.transaction(conn):
            # 条件更新保证并发的重复 decide 只有一次真正生效
            cur = conn.execute(
                "UPDATE review_queue SET status = ?, reviewed_at = ?, reviewer_note = ? "
                "WHERE id = ? AND status = 'pending'",
                (_STATUS_BY_ACTION[body.action], _now(), body.note, item_id),
            )
            if cur.rowcount and body.action == "approve" and row["entity_id"] is not None:
                upsert_field(
                    conn,
                    entity_id=int(row["entity_id"]),
                    field_name=row["field_name"],
                    value=_decode(row["proposed_value_json"]),
                    source="ugc",
                    source_url=None,
                    confidence=0.9,
                )
    finally:
        conn.close()
    return {"ok": True}