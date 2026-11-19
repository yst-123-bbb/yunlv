"""FastAPI 应用装配：启动钩子、请求标识、统一错误响应与路由注册。"""

from __future__ import annotations

import importlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from datastore.db import connect, init_db
from infra.logging_setup import get_logger, log_event, new_req_id

from api.routers import (
    budget,
    export,
    notes,
    places,
    plan,
    route,
    share,
    templates,
    tickets,
    transport,
)

logger = get_logger(__name__)

# C-EXPORT@1 约定该表由本任务在 init_db 之后建立
SHARE_LINK_DDL = """
CREATE TABLE IF NOT EXISTS share_link (
    short_id TEXT PRIMARY KEY,
    session_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    session_id TEXT NOT NULL UNIQUE
)
"""


def ensure_share_table() -> None:
    init_db()
    conn = connect()
    try:
        conn.execute(SHARE_LINK_DDL)
        conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_share_table()
    log_event(logger, "app_startup", outcome="ok")
    yield


app = FastAPI(title="CloudTrip API", version="2.0.0", lifespan=lifespan)

app.include_router(plan.router)
app.include_router(transport.router)
app.include_router(tickets.router)
app.include_router(notes.router)
app.include_router(budget.router)
app.include_router(places.router)
app.include_router(route.router)
app.include_router(share.router)
app.include_router(export.router)
app.include_router(templates.router)

# C-REVIEW@1: 审核模块可选，缺席时应用仍可启动
try:
    from api.routers import review
except ImportError:
    pass
else:
    app.include_router(review.router)

# C-CATALOG@1 / C-COMMENT@1 / C-CHAT@1: 三个新路由可选注册，文件缺席时应用仍可启动
for _module_name in ("catalog", "comments", "chat"):
    try:
        _module = importlib.import_module(f"api.routers.{_module_name}")
    except ImportError:
        continue
    app.include_router(_module.router)


@app.middleware("http")
async def attach_req_id(request: Request, call_next):
    request.state.req_id = new_req_id()
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.req_id
    return response


@app.exception_handler(KeyError)
async def handle_not_found(_request: Request, exc: KeyError) -> JSONResponse:
    detail = exc.args[0] if exc.args else "not_found"
    return JSONResponse(status_code=404, content={"detail": str(detail)})


@app.exception_handler(ValueError)
async def handle_invalid_request(_request: Request, exc: ValueError) -> JSONResponse:
    detail = exc.args[0] if exc.args else "invalid_request"
    return JSONResponse(status_code=400, content={"detail": str(detail)})


@app.exception_handler(Exception)
async def handle_internal_error(request: Request, exc: Exception) -> JSONResponse:
    req_id = getattr(request.state, "req_id", None) or new_req_id()
    log_event(
        logger,
        "unhandled_error",
        req_id=req_id,
        error=f"{type(exc).__name__}: {exc}",
        outcome="error",
    )
    return JSONResponse(status_code=500, content={"detail": "internal_error"})