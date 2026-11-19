"""字段级仓储：实体与字段值读写、变更留痕与低置信度冲突入审核队列。

所有写函数只在调用方事务内执行，自身不 commit。
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

_TZ = timezone(timedelta(hours=8))

# 与 C-REPO@1 的 canonical_key 规则一致：去掉括号、间隔号、空白、反斜杠与连字符。
_CANONICAL_NOISE = re.compile(r"[()（）·・\s\\\\-]+")


def _now() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _decode(text: str | None) -> Any:
    if text is None:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def _same_value(stored_json: str, value: Any) -> bool:
    try:
        return json.loads(stored_json) == value
    except (TypeError, ValueError):
        return False


def _canonical_key(entity_type: str, city: str, name: str) -> str:
    return f"{entity_type}:{city}:{_CANONICAL_NOISE.sub('', name)}"


def upsert_entity(
    conn: sqlite3.Connection,
    *,
    type: str,
    city: str,
    name: str,
    alias: str | None = None,
) -> int:
    key = _canonical_key(type, city, name)
    row = conn.execute("SELECT id FROM entity WHERE canonical_key = ?", (key,)).fetchone()
    if row is not None:
        return int(row["id"])

    ts = _now()
    cur = conn.execute(
        "INSERT INTO entity (type, city, name, alias, canonical_key, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
        (type, city, name, alias, key, ts, ts),
    )
    return int(cur.lastrowid)


def get_entity_id(
    conn: sqlite3.Connection,
    *,
    type: str,
    city: str,
    name: str,
) -> int | None:
    key = _canonical_key(type, city, name)
    row = conn.execute("SELECT id FROM entity WHERE canonical_key = ?", (key,)).fetchone()
    return int(row["id"]) if row is not None else None


def _log_change(
    conn: sqlite3.Connection,
    entity_id: int,
    field_name: str,
    old_value_json: str | None,
    new_value_json: str,
    source: str,
    changed_at: str,
    batch_id: int | None,
) -> None:
    conn.execute(
        "INSERT INTO change_log (entity_id, field_name, old_value_json, new_value_json, "
        "source, operator, batch_id, changed_at) VALUES (?, ?, ?, ?, ?, 'system', ?, ?)",
        (entity_id, field_name, old_value_json, new_value_json, source, batch_id, changed_at),
    )


def upsert_field(
    conn: sqlite3.Connection,
    *,
    entity_id: int,
    field_name: str,
    value: Any,
    source: str,
    source_url: str | None,
    confidence: float,
    fetched_at: str | None = None,
    batch_id: int | None = None,
) -> Literal["written", "queued", "skipped"]:
    ts = fetched_at or _now()
    new_json = _encode(value)
    confidence = float(confidence)

    current = conn.execute(
        "SELECT id, value_json, confidence, version FROM field_value "
        "WHERE entity_id = ? AND field_name = ? AND is_current = 1",
        (entity_id, field_name),
    ).fetchone()

    if current is None:
        conn.execute(
            "INSERT INTO field_value (entity_id, field_name, value_json, source, source_url, "
            "confidence, fetched_at, is_current, version) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)",
            (entity_id, field_name, new_json, source, source_url, confidence, ts),
        )
        _log_change(conn, entity_id, field_name, None, new_json, source, ts, batch_id)
        return "written"

    if _same_value(current["value_json"], value):
        return "skipped"

    if confidence < float(current["confidence"]):
        enqueue_review(
            conn,
            entity_id=entity_id,
            field_name=field_name,
            proposed=value,
            current=_decode(current["value_json"]),
            reason="lower_confidence_conflict",
        )
        return "queued"

    conn.execute("UPDATE field_value SET is_current = 0 WHERE id = ?", (current["id"],))
    conn.execute(
        "INSERT INTO field_value (entity_id, field_name, value_json, source, source_url, "
        "confidence, fetched_at, is_current, version) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
        (
            entity_id,
            field_name,
            new_json,
            source,
            source_url,
            confidence,
            ts,
            int(current["version"]) + 1,
        ),
    )
    _log_change(conn, entity_id, field_name, current["value_json"], new_json, source, ts, batch_id)
    return "written"


def read_entity(conn: sqlite3.Connection, entity_id: int) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT field_name, value_json FROM field_value WHERE entity_id = ? AND is_current = 1",
        (entity_id,),
    ).fetchall()
    return {row["field_name"]: _decode(row["value_json"]) for row in rows}


def search_entities(
    conn: sqlite3.Connection,
    *,
    type: str | None,
    city: str | None,
    keyword: str | None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    sql = "SELECT id, name, city, type FROM entity WHERE 1 = 1"
    params: list[Any] = []
    if type:
        sql += " AND type = ?"
        params.append(type)
    if city:
        sql += " AND city = ?"
        params.append(city)
    if keyword:
        sql += " AND (name LIKE ? OR IFNULL(alias, '') LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])
    sql += " ORDER BY id LIMIT ?"
    params.append(int(limit))

    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "entity_id": int(row["id"]),
            "name": row["name"],
            "city": row["city"],
            "type": row["type"],
            "fields": read_entity(conn, int(row["id"])),
        }
        for row in rows
    ]


def enqueue_review(
    conn: sqlite3.Connection,
    *,
    entity_id: int | None,
    field_name: str,
    proposed: Any,
    current: Any,
    reason: str,
    raw_excerpt: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO review_queue (entity_id, field_name, proposed_value_json, "
        "current_value_json, reason, raw_excerpt, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
        (
            entity_id,
            field_name,
            _encode(proposed),
            None if current is None else _encode(current),
            reason,
            raw_excerpt,
            _now(),
        ),
    )
    return int(cur.lastrowid)