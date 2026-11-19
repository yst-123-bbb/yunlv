"""SQLite 连接、Schema 初始化与事务上下文。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from settings import settings

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _resolve_path(db_path: str | None) -> str:
    return db_path or settings.db_path


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """打开连接：Row 工厂 + WAL + 外键约束。"""
    path = _resolve_path(db_path)
    if path != ":memory:":
        parent = Path(path).parent
        if str(parent):
            parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    """建表与索引，幂等；不改变已有数据。"""
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = connect(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """事务上下文：正常结束提交，异常回滚后原样抛出。"""
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()