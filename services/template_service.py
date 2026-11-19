# -*- coding: utf-8 -*-
"""行程模板：把已完成的会话存成可复用的模板，供方案对比与再次出行使用。

模板落在 ``{cache_dir}/templates/{name}.json``，内容即 ``PlanSession`` 的整体快照。
"""
from __future__ import annotations

import json
import os
import re

from services.plan_service import PlanSession
from settings import settings


def _templates_dir() -> str:
    return os.path.join(settings.cache_dir, "templates")


def _safe_name(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        raise ValueError("invalid_template_name")
    # 模板名会直接成为文件名，剔除路径分隔符等危险字符
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", text).strip("._")
    if not safe:
        raise ValueError("invalid_template_name")
    return safe


def _template_path(name: str) -> str:
    return os.path.join(_templates_dir(), f"{_safe_name(name)}.json")


def save_template(name: str, session: PlanSession) -> str:
    """同名校验后覆盖写入，返回实际使用的模板名。"""
    path = _template_path(name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(session.model_dump(), fh, ensure_ascii=False, default=str)
    os.replace(tmp, path)
    return _safe_name(name)


def list_templates() -> list[str]:
    try:
        names = os.listdir(_templates_dir())
    except OSError:
        return []
    return sorted(os.path.splitext(entry)[0] for entry in names if entry.endswith(".json"))


def load_template(name: str) -> PlanSession:
    try:
        with open(_template_path(name), encoding="utf-8") as fh:
            raw = json.load(fh)
        return PlanSession.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise KeyError("template_not_found") from exc