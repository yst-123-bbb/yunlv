# -*- coding: utf-8 -*-
"""每日强度画像：按人群模式评估行程每天的步行、爬升与无保障情况。"""

from __future__ import annotations

from typing import Any

from core.crowd_profile import profile_day
from services.plan_service import PlanSession


def _field(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_dict(day: Any) -> dict:
    if isinstance(day, dict):
        return day
    if hasattr(day, "model_dump"):
        return day.model_dump(mode="json")
    return dict(day)


def day_profiles(session: PlanSession | dict) -> list[dict]:
    user_data = _field(session, "user_data", {}) or {}
    mode = str((user_data or {}).get("crowd_mode") or "normal")

    profiles: list[dict] = []
    for index, day in enumerate(iter(_field(session, "itinerary") or [])):
        try:
            raw = profile_day(_as_dict(day), mode)
        except ValueError:
            try:
                raw = profile_day(_as_dict(day), "normal")
            except Exception:
                continue
        except Exception:
            continue

        profiles.append(
            {
                "day": int(_field(day, "day") or index + 1),
                "date": str(_field(day, "date") or ""),
                "walk_km": float(raw.get("walk_km") or 0.0),
                "climb_m": float(raw.get("climb_m") or 0.0),
                "elevator_ok": bool(raw.get("elevator_ok", True)),
                "intensity": str(raw.get("intensity") or "mid"),
                "tips": list(raw.get("tips") or []),
            }
        )
    return profiles


def enrich_state(session: PlanSession) -> dict:
    payload = session.model_dump(mode="json")
    payload["day_profile"] = day_profiles(session)
    return payload