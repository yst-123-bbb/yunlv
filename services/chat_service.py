# -*- coding: utf-8 -*-
"""自由制定对话：DeepSeek 可用时走大模型，否则降级为本地规则应答。

服务端不保存任何对话历史，消息列表由前端持有；任何外呼异常都在本模块内
吞掉并降级，路由层因此永不返回 5xx。
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

import settings
from data.place_catalog import CITIES

_DRAFT_START = "<<DRAFT>>"
_DRAFT_END = "<<END>>"

_CITY_NAMES = [str(item.get("name") or "") for item in CITIES if item.get("name")]

_SYSTEM_PROMPT = (
    "你是「云旅」旅行规划助手，用中文与用户逐轮对话，追问出发地、目的地、天数、"
    "人数与预算信息。信息齐备时，在回复最后另起一行追加标记段："
    "<<DRAFT>>{\"departure\":\"\",\"destination\":\"\",\"days\":0,\"people\":0,"
    "\"dep_date\":\"\",\"tastes\":[],\"attraction_prefs\":[],\"transport_pref\":\"\","
    "\"hotel_level\":\"\",\"budget\":0}<<END>>，其中 json 的 destination 必须是中文城市名，"
    "days 为整数天数，budget 为总预算元数，其余字段缺失时留空字符串/空数组/0。"
    "信息不齐备时不要输出该标记段。"
)


def reply(messages: list[dict], prefs: dict | None = None) -> dict:
    cleaned = _validate_messages(messages)

    if str(settings.DEEPSEEK_API_KEY or "").strip():
        try:
            return _ask_deepseek(cleaned)
        except Exception:
            pass

    return _local_reply(cleaned, prefs if isinstance(prefs, dict) else None)


def _validate_messages(messages: list[dict]) -> list[dict]:
    if not isinstance(messages, list) or not messages:
        raise ValueError("invalid_messages")

    cleaned: list[dict] = []
    for item in messages:
        if not isinstance(item, dict):
            raise ValueError("invalid_messages")
        role = str(item.get("role") or "")
        content = str(item.get("content") or "")
        if role not in ("user", "assistant") or not content.strip():
            raise ValueError("invalid_messages")
        cleaned.append({"role": role, "content": content})

    if cleaned[-1]["role"] != "user":
        raise ValueError("invalid_messages")
    return cleaned


def _ask_deepseek(messages: list[dict]) -> dict:
    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [{"role": "system", "content": _SYSTEM_PROMPT}, *messages],
        "temperature": 0.7,
    }
    response = httpx.post(
        settings.DEEPSEEK_BASE_URL,
        headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
        json=payload,
        timeout=settings.DEEPSEEK_TIMEOUT_S,
    )
    response.raise_for_status()
    data = response.json()
    text = str(data["choices"][0]["message"]["content"] or "")
    text_reply, draft = _split_draft(text)
    return {"reply": text_reply, "draft": draft, "provider": "deepseek"}


def _split_draft(text: str) -> tuple[str, dict | None]:
    start = text.find(_DRAFT_START)
    end = text.find(_DRAFT_END, start + len(_DRAFT_START)) if start >= 0 else -1
    if start < 0 or end < 0:
        return text.strip(), None

    raw = text[start + len(_DRAFT_START) : end].strip()
    visible = (text[:start] + text[end + len(_DRAFT_END) :]).strip()
    try:
        draft = _normalize_draft(json.loads(raw))
    except (json.JSONDecodeError, TypeError):
        draft = None
    return visible, draft


def _normalize_draft(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None

    draft: dict[str, Any] = {
        "departure": str(raw.get("departure") or "").strip(),
        "destination": str(raw.get("destination") or "").strip(),
        "days": _to_int(raw.get("days")),
        "people": _to_int(raw.get("people")),
        "dep_date": str(raw.get("dep_date") or "").strip(),
        "tastes": _to_str_list(raw.get("tastes")),
        "attraction_prefs": _to_str_list(raw.get("attraction_prefs")),
        "transport_pref": str(raw.get("transport_pref") or "").strip(),
        "hotel_level": str(raw.get("hotel_level") or "").strip(),
        "budget": _to_float(raw.get("budget")),
    }
    if not draft["destination"] or draft["days"] <= 0:
        return None
    return draft


def _local_reply(messages: list[dict], prefs: dict | None) -> dict:
    text = "\n".join(item["content"] for item in messages)
    prefs = prefs or {}

    destination = next((name for name in _CITY_NAMES if name in text), "")
    days = _match_int(r"(\d+)\s*天", text)
    people = _match_int(r"(\d+)\s*人", text)
    budget = _match_float(r"(\d+)\s*元", text)

    departure = str(prefs.get("departure") or "").strip()
    tastes = _to_str_list(prefs.get("tastes"))
    if "total_budget" in prefs:
        budget = budget or _to_float(prefs.get("total_budget"))

    if not destination:
        return _local_result("想去哪座城市？告诉我目的地，我来帮你排行程。")
    if days <= 0:
        return _local_result(f"{destination}打算玩几天？")
    if not departure:
        return _local_result(f"准备从哪出发去{destination}？玩{days}天。")

    draft: dict[str, Any] = {
        "departure": departure,
        "destination": destination,
        "days": days,
        "people": people,
        "dep_date": "",
        "tastes": tastes,
        "attraction_prefs": [],
        "transport_pref": _transport_from_style(prefs.get("travel_style")),
        "hotel_level": "",
        "budget": budget,
    }

    hints: list[str] = []
    if people <= 0:
        hints.append("几个人出行")
    if budget <= 0:
        hints.append("总预算大概多少")
    closing = "，另外还想确认：" + "、".join(hints) + "？" if hints else "。"
    return _local_result(
        f"已按{departure}出发、{destination}{days}天整理好行程草稿"
        f"{closing}可以点「生成行程」继续。",
        draft,
    )


def _local_result(reply_text: str, draft: dict | None = None) -> dict:
    return {"reply": reply_text, "draft": draft, "provider": "local"}


def _transport_from_style(style: Any) -> str:
    if style == "fast":
        return "flight"
    if style == "slow":
        return "train"
    return ""


def _match_int(pattern: str, text: str) -> int:
    found = re.search(pattern, text)
    return int(found.group(1)) if found else 0


def _match_float(pattern: str, text: str) -> float:
    found = re.search(pattern, text)
    return float(found.group(1)) if found else 0.0


def _to_int(value: Any) -> int:
    try:
        return max(0, int(float(str(value).strip())))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return max(0.0, float(str(value).strip()))
    except (TypeError, ValueError):
        return 0.0


def _to_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,，、\s]+", value) if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []