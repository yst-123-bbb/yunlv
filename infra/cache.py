"""分层缓存：文件与 SQLite 双实现，读写失败不中断调用方。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Protocol

from datastore.db import connect, init_db
from infra.logging_setup import get_logger, log_event
from settings import settings

TTL_STATIC = 90 * 86400
TTL_SEMI_STATIC = 30 * 86400
TTL_DYNAMIC = 600
TTL_TRANSPORT = 600

_logger = get_logger("cache")
_UNSAFE_NS = re.compile(r"[^0-9A-Za-z_.-]+")


def namespaced(ns: str, key: str) -> str:
    return f"{ns}:{key}"


def _namespace_of(key: str) -> str:
    return key.split(":", 1)[0]


class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_s: int) -> None: ...

    def delete(self, key: str) -> None: ...

    def clear_namespace(self, ns: str) -> None: ...


class FileCache(CacheBackend):
    """每键一个 JSON 文件，按 namespace 分目录，便于整段清理。"""

    def __init__(self, cache_dir: str | os.PathLike[str] | None = None) -> None:
        base = Path(cache_dir if cache_dir is not None else settings.cache_dir)
        self._root = base / "kv"

    def _dir_for(self, namespace: str) -> Path:
        return self._root / (_UNSAFE_NS.sub("_", namespace) or "_")

    def _path_for(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self._dir_for(_namespace_of(key)) / f"{digest}.json"

    def get(self, key: str) -> Any | None:
        path = self._path_for(key)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("cache payload is not an object")
            expires_at = float(payload["expires_at"])
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log_event(_logger, "cache_read_failed", backend="file", key=key, error=repr(exc))
            self.delete(key)
            return None
        if time.time() > expires_at:
            self.delete(key)
            return None
        return payload.get("value")

    def set(self, key: str, value: Any, ttl_s: int) -> None:
        path = self._path_for(key)
        payload = {"key": key, "expires_at": time.time() + float(ttl_s), "value": value}
        try:

            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)
        except (OSError, TypeError, ValueError) as exc:
            log_event(_logger, "cache_write_failed", backend="file", key=key, error=repr(exc))

    def delete(self, key: str) -> None:
        try:
            self._path_for(key).unlink(missing_ok=True)
        except OSError as exc:
            log_event(_logger, "cache_delete_failed", backend="file", key=key, error=repr(exc))

    def clear_namespace(self, ns: str) -> None:
        shutil.rmtree(self._dir_for(ns), ignore_errors=True)


class SqliteCache(CacheBackend):
    """存放在 `kv_cache` 表，首次访问时确保 schema 已就绪。"""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._schema_ready = False
        self._lock = threading.Lock()

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._lock:
            if not self._schema_ready:
                init_db(self._db_path)
                self._schema_ready = True

    def _open(self) -> sqlite3.Connection:
        self._ensure_schema()
        return connect(self._db_path)

    def get(self, key: str) -> Any | None:
        try:
            conn = self._open()
            try:
                row = conn.execute(
                    "SELECT value_json, expires_at FROM kv_cache WHERE key = ?", (key,)
                ).fetchone()
            finally:
                conn.close()
        except (sqlite3.Error, OSError) as exc:
            log_event(_logger, "cache_read_failed", backend="sqlite", key=key, error=repr(exc))
            return None
        if row is None:
            return None
        if time.time() > float(row["expires_at"]):
            self.delete(key)
            return None
        try:
            return json.loads(row["value_json"])
        except (ValueError, TypeError) as exc:
            log_event(_logger, "cache_decode_failed", backend="sqlite", key=key, error=repr(exc))
            self.delete(key)
            return None

    def set(self, key: str, value: Any, ttl_s: int) -> None:
        try:
            payload = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            log_event(_logger, "cache_encode_failed", backend="sqlite", key=key, error=repr(exc))
            return
        try:
            conn = self._open()
            try:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO kv_cache"
                        " (key, namespace, value_json, expires_at) VALUES (?, ?, ?, ?)",
                        (key, _namespace_of(key), payload, time.time() + float(ttl_s)),
                    )
            finally:
                conn.close()
        except (sqlite3.Error, OSError) as exc:
            log_event(_logger, "cache_write_failed", backend="sqlite", key=key, error=repr(exc))

    def delete(self, key: str) -> None:
        try:
            conn = self._open()
            try:
                with conn:
                    conn.execute("DELETE FROM kv_cache WHERE key = ?", (key,))
            finally:
                conn.close()
        except (sqlite3.Error, OSError) as exc:
            log_event(_logger, "cache_delete_failed", backend="sqlite", key=key, error=repr(exc))

    def clear_namespace(self, ns: str) -> None:
        try:
            conn = self._open()
            try:
                with conn:
                    conn.execute("DELETE FROM kv_cache WHERE namespace = ?", (ns,))
            finally:
                conn.close()
        except (sqlite3.Error, OSError) as exc:
            log_event(_logger, "cache_clear_failed", backend="sqlite", ns=ns, error=repr(exc))


_cache: CacheBackend | None = None
_cache_lock = threading.Lock()


def get_cache() -> CacheBackend:
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = SqliteCache() if settings.cache_backend == "sqlite" else FileCache()
    return _cache