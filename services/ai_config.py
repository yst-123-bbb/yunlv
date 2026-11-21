# -*- coding: utf-8 -*-
"""从请求头解析用户自带的 AI 配置。

配置只在本进程内存中流转，不落盘、不写日志，避免 Key 泄漏。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import settings

HEADER_BASE_URL = "x-ai-base-url"
HEADER_API_KEY = "x-ai-key"
HEADER_MODEL = "x-ai-model"


@dataclass(frozen=True)
class AiConfig:
    base_url: str
    api_key: str
    model: str


def _allowed_base_url(base_url: str) -> bool:
    # 只允许公网 https 与本机回环，阻止把外呼指向内网地址
    return (
        base_url.startswith("https://")
        or base_url.startswith("http://localhost")
        or base_url.startswith("http://127.0.0.1")
    )


def from_headers(headers: Mapping[str, str]) -> AiConfig | None:
    try:
        api_key = str(headers.get(HEADER_API_KEY, "") or "").strip()
        if not api_key:
            return None

        base_url = str(headers.get(HEADER_BASE_URL, "") or "").strip()
        if not base_url:
            base_url = settings.DEEPSEEK_BASE_URL
        if not _allowed_base_url(base_url):
            return None

        model = str(headers.get(HEADER_MODEL, "") or "").strip() or settings.DEEPSEEK_MODEL
    except Exception:
        return None

    return AiConfig(base_url=base_url, api_key=api_key, model=model)