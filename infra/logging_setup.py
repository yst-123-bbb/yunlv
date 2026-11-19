"""结构化 JSON 日志：单行输出，字段固定可扩展，写入失败不影响业务流程。"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime

_HANDLER_FLAG = "logging_setup"
_BASE_FIELDS = ("ts", "level", "logger", "event")


def _resolve_level() -> int:
    # settings 可能尚未就绪（或处于独立脚本环境），此时退化为 INFO 而非中断日志初始化
    try:
        from settings import settings

        level_name = str(settings.log_level).upper()
    except Exception:
        return logging.INFO
    return getattr(logging, level_name, logging.INFO)


class _SafeStreamHandler(logging.StreamHandler):
    """JSON 行输出；任何写入异常降级到 stderr，绝不抛给调用方。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except Exception:
            try:
                sys.stderr.write(f"{record.getMessage()}\n")
            except Exception:
                pass


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    # 标记属性判断，保证重复调用不重复挂 handler
    if not getattr(logger, _HANDLER_FLAG, False):
        handler = _SafeStreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(_resolve_level())
        logger.propagate = False
        setattr(logger, _HANDLER_FLAG, True)
    return logger


def log_event(logger: logging.Logger, event: str, **fields) -> None:
    if not logger.isEnabledFor(logging.INFO):
        return

    payload: dict = {
        "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "level": logging.getLevelName(logging.INFO),
        "logger": logger.name,
        "event": event,
    }
    # 基础字段不可被自定义字段覆盖
    for key, value in fields.items():
        if key not in _BASE_FIELDS:
            payload[key] = value

    try:
        line = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        line = json.dumps(
            {
                "ts": payload["ts"],
                "level": payload["level"],
                "logger": logger.name,
                "event": event,
                "error": "log_serialize_failed",
            },
            ensure_ascii=False,
        )

    try:
        logger.info(line)
    except Exception:
        try:
            sys.stderr.write(f"{line}\n")
        except Exception:
            pass


def new_req_id() -> str:
    return uuid.uuid4().hex[:12]