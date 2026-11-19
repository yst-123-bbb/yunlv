"""pytest 公共夹具：临时 SQLite 库与文件缓存实例。"""

from __future__ import annotations

import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_db(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """已完成 DDL 初始化的临时 SQLite 连接。"""
    from datastore.db import connect, init_db

    db_path = tmp_path / "cloudtrip_test.db"
    init_db(str(db_path))
    conn = connect(str(db_path))
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def file_cache(tmp_path: Path):
    """缓存目录指向独立临时目录的 FileCache，避免测试之间串数据。"""
    from infra.cache import FileCache

    return FileCache(str(tmp_path / "cache"))