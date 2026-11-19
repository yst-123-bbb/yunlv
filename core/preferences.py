# -*- coding: utf-8 -*-
"""本地偏好学习：记录用户的选择/跳过事件，并按累计权重给候选排序。

数据只落在 ``{cache_dir}/preferences.json``，不联网、不区分用户。
"""
from __future__ import annotations

import json
import os
import threading
from typing import Literal

from settings import settings

SELECT_DELTA = 1.0
# 跳过只做轻微降权：用户跳过一次往往只是口味不同，不足以与"选择"等价
SKIP_DELTA = -0.5

EventKind = Literal["select", "skip"]

_LOCK = threading.Lock()


def _path() -> str:
    return os.path.join(settings.cache_dir, "preferences.json")


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"items": {}}

    items = raw.get("items") if isinstance(raw, dict) else None
    return {"items": items if isinstance(items, dict) else {}}


def _save(data: dict) -> None:
    path = _path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    os.replace(tmp, path)


def _name_of(item: dict) -> str:
    name = item.get("name") if isinstance(item, dict) else None
    text = str(name or "").strip()
    if not text:
        raise ValueError("item_name_required")
    return text


def record_event(kind: EventKind, item: dict) -> None:
    """累计一次选择或跳过事件；同一条目重复出现按次数累加。"""
    if kind not in ("select", "skip"):
        raise ValueError("invalid_event_kind")
    name = _name_of(item)
    delta = SELECT_DELTA if kind == "select" else SKIP_DELTA

    with _LOCK:
        data = _load()
        entry = data["items"].get(name)
        if not isinstance(entry, dict):
            entry = {"select": 0, "skip": 0, "weight": 0.0}
        entry["select"] = int(entry.get("select") or 0) + (1 if kind == "select" else 0)
        entry["skip"] = int(entry.get("skip") or 0) + (1 if kind == "skip" else 0)
        entry["weight"] = round(float(entry.get("weight") or 0.0) + delta, 4)
        data["items"][name] = entry
        _save(data)


def get_weight(name: str) -> float:
    entry = _load()["items"].get(str(name or "").strip())
    if not isinstance(entry, dict):
        return 0.0
    try:
        return float(entry.get("weight") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def rank(items: list[dict], name_key: str = "name") -> list[dict]:
    """按偏好权重降序稳定排序，未记录过的条目权重为 0 且保持原相对顺序。"""
    weights = {name: float(entry.get("weight") or 0.0)
               for name, entry in _load()["items"].items() if isinstance(entry, dict)}

    def _weight(item: dict) -> float:
        name = str((item or {}).get(name_key) or "").strip()
        return weights.get(name, 0.0)

    return sorted(list(items or []), key=_weight, reverse=True)