# -*- coding: utf-8 -*-
"""网友评语：只读查询与离线采集结果的幂等写入。

请求路径上从不触发外网抓取，评语由 ``scripts/fetch_comments.py`` 离线写入。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from datastore import db

_TZ = timezone(timedelta(hours=8))

_COLUMNS = "id, target, target_type, author, text, likes, source_url, source, fetched_at"

_REQUIRED_KEYS = ("target", "target_type", "author", "text", "source_url")


def _now() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")


def _comment_id(source_url: str, text: str) -> str:
    return hashlib.sha1((source_url + text).encode()).hexdigest()[:16]


def list_comments(target: str, limit: int = 5) -> list[dict]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("invalid_limit")
    name = str(target or "").strip()
    if not name:
        raise ValueError("invalid_target")

    conn = db.connect()
    try:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM city_comment WHERE target = ? "
            "ORDER BY likes DESC, fetched_at DESC LIMIT ?",
            (name, limit),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def upsert_comments(items: list[dict]) -> int:
    """写入评语并返回写入条数；id 由 source_url + text 派生，因此重复采集可幂等覆盖。"""
    rows: list[tuple] = []
    for item in items:
        values: dict[str, str] = {}
        for key in _REQUIRED_KEYS:
            value = str(item.get(key) or "").strip()
            if not value:
                raise ValueError(f"invalid_comment:{key}")
            values[key] = value

        text = values["text"]
        source_url = values["source_url"]
        comment_id = str(item.get("id") or "").strip() or _comment_id(source_url, text)
        likes = int(item.get("likes") or 0)
        source = str(item.get("source") or "").strip() or "xiaohongshu"
        fetched_at = str(item.get("fetched_at") or "").strip() or _now()
        rows.append(
            (
                comment_id,
                values["target"],
                values["target_type"],
                values["author"],
                text,
                likes,
                source_url,
                source,
                fetched_at,
            )
        )

    if not rows:
        return 0

    conn = db.connect()
    try:
        with db.transaction(conn):
            conn.executemany(
                f"INSERT OR REPLACE INTO city_comment ({_COLUMNS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
    finally:
        conn.close()
    return len(rows)