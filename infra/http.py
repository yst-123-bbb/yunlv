"""统一 HTTP 客户端：限速、重试、高德配额守护与抓取记录。"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from datastore.db import connect
from infra.logging_setup import get_logger, log_event
from infra.ratelimit import limiter
from settings import settings

PROVIDER_AMAP = "amap"
MAX_ATTEMPTS = 2

_CST = timezone(timedelta(hours=8))
_logger = get_logger("http")
_quota_lock = threading.Lock()


class QuotaExceeded(RuntimeError):
    """高德当日调用配额已用尽。"""


def _today() -> str:
    return datetime.now(_CST).strftime("%Y-%m-%d")


def _read_quota() -> dict:
    try:
        raw = json.loads(Path(settings.amap_quota_state).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"date": _today(), "count": 0}
    if not isinstance(raw, dict) or raw.get("date") != _today():
        return {"date": _today(), "count": 0}
    try:
        count = max(int(raw.get("count", 0) or 0), 0)
    except (TypeError, ValueError):
        count = 0
    return {"date": _today(), "count": count}


def _write_quota(state: dict) -> None:
    path = Path(settings.amap_quota_state)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log_event(_logger, "quota_state_write_failed", outcome="warn", error=str(exc))


def amap_quota_used(reset: bool = False) -> int:
    """返回当日高德调用计数；reset=True 时清零并落盘。"""
    with _quota_lock:
        state = _read_quota()
        if reset:
            state = {"date": _today(), "count": 0}
            _write_quota(state)
        return int(state["count"])


def _consume_amap_quota() -> int:
    with _quota_lock:
        state = _read_quota()
        if state["count"] >= settings.amap_daily_quota:
            raise QuotaExceeded(
                f"amap 当日配额已用尽: {state['count']}/{settings.amap_daily_quota}"
            )
        state["count"] += 1
        _write_quota(state)
        return int(state["count"])


def record_fetch(
    conn,
    *,
    provider: str,
    url: str,
    status_code: int | None,
    ok: bool,
    duration_ms: int,
    error: str | None,
    batch_id: int | None = None,
) -> None:
    """写一条 fetch_log；不传 conn 时用临时连接并提交。"""
    owns_conn = conn is None
    try:
        target = connect() if owns_conn else conn
        try:
            target.execute(
                "INSERT INTO fetch_log (provider, url, status_code, ok, duration_ms, error, "
                "fetched_at, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    provider,
                    url,
                    status_code,
                    1 if ok else 0,
                    int(duration_ms),
                    error,
                    datetime.now(_CST).isoformat(timespec="seconds"),
                    batch_id,
                ),
            )
            if owns_conn:
                target.commit()
        finally:
            if owns_conn:
                target.close()
    except Exception as exc:  # 抓取记录失败不影响业务请求
        log_event(_logger, "fetch_log_failed", provider=provider, outcome="warn", error=str(exc))


def _fetch(
    url: str,
    *,
    as_json: bool,
    params: dict | None,
    headers: dict | None,
    provider: str,
    timeout_s: float | None,
    conn,
    batch_id: int | None,
):
    if provider == PROVIDER_AMAP:
        _consume_amap_quota()

    domain = urlparse(url).netloc
    timeout = settings.http_timeout_s if timeout_s is None else timeout_s
    last_error: httpx.HTTPError | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        limiter.acquire(domain)
        started = time.perf_counter()
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            retryable = isinstance(exc, httpx.TransportError) and attempt < MAX_ATTEMPTS
            record_fetch(
                conn,
                provider=provider,
                url=url,
                status_code=status_code,
                ok=False,
                duration_ms=duration_ms,
                error=str(exc),
                batch_id=batch_id,
            )
            log_event(
                _logger,
                "http_error",
                provider=provider,
                duration_ms=duration_ms,
                outcome="retry" if retryable else "error",
                error=str(exc),
            )
            last_error = exc
            if not retryable:
                raise
            continue

        if as_json:
            try:
                payload = response.json()
            except ValueError as exc:
                duration_ms = int((time.perf_counter() - started) * 1000)
                record_fetch(
                    conn,
                    provider=provider,
                    url=url,
                    status_code=response.status_code,
                    ok=False,
                    duration_ms=duration_ms,
                    error=f"invalid_json: {exc}",
                    batch_id=batch_id,
                )
                raise
            if not isinstance(payload, dict):
                duration_ms = int((time.perf_counter() - started) * 1000)
                record_fetch(
                    conn,
                    provider=provider,
                    url=url,
                    status_code=response.status_code,
                    ok=False,
                    duration_ms=duration_ms,
                    error="json_object_expected",
                    batch_id=batch_id,
                )
                raise ValueError(f"json_object_expected: {url}")
        else:
            payload = response.text

        duration_ms = int((time.perf_counter() - started) * 1000)
        record_fetch(
            conn,
            provider=provider,
            url=url,
            status_code=response.status_code,
            ok=True,
            duration_ms=duration_ms,
            error=None,
            batch_id=batch_id,
        )
        log_event(
            _logger,
            "http_ok",
            provider=provider,
            duration_ms=duration_ms,
            outcome="ok",
        )
        return payload

    raise last_error if last_error is not None else RuntimeError("http_unreachable")


def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    provider: str,
    timeout_s: float | None = None,
    conn=None,
    batch_id: int | None = None,
) -> dict:
    return _fetch(
        url,
        as_json=True,
        params=params,
        headers=headers,
        provider=provider,
        timeout_s=timeout_s,
        conn=conn,
        batch_id=batch_id,
    )


def get_text(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    provider: str,
    timeout_s: float | None = None,
    conn=None,
    batch_id: int | None = None,
) -> str:
    return _fetch(
        url,
        as_json=False,
        params=params,
        headers=headers,
        provider=provider,
        timeout_s=timeout_s,
        conn=conn,
        batch_id=batch_id,
    )