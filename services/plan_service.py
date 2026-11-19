"""行程编排服务：六步状态机、回退与局部修改。

会话整体持久化到 ``{cache_dir}/sessions/{session_id}.json``，CLI 与 API 共用同一份状态。
"""

from __future__ import annotations

import copy
import json
import os
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable

from pydantic import BaseModel, Field

from core.budget import calculate_budget
from core.filter import filter_transport
from core.itinerary_validator import Issue, validate_itinerary
from core.plan_generator import generate_plans
from crawlers.spiders import crawl_all, crawl_flight, crawl_train, sort_transport_options
from infra.logging_setup import get_logger, log_event
from providers.models import PlaceItem
from settings import settings

_HISTORY_LIMIT = 12

# 每天最多编排 4 个景点，时段互不重叠，避免自身触发 time_overlap 校验
_SLOTS: tuple[tuple[str, str], ...] = (
    ("09:00", "12:00"),
    ("14:00", "17:30"),
    ("18:00", "20:00"),
    ("20:00", "21:30"),
)

_CROWD_BY_AGE = {"family": "family", "senior": "senior", "accessible": "accessible"}

_FALLBACK_FLIGHT: dict = {"flight_no": "CA001", "cabin": {"经济舱": 800}}

_logger = get_logger("plan_service")


class PlanSession(BaseModel):
    session_id: str
    stage: int = 0
    user_data: dict = Field(default_factory=dict)
    transport: dict | None = None
    plans: list[dict] = Field(default_factory=list)
    chosen_plan: dict | None = None
    itinerary: list[dict] = Field(default_factory=list)
    budget: dict | None = None
    history: list[dict] = Field(default_factory=list)
    generation_error: str | None = None


# ---------------------------------------------------------------------------
# 持久化
# ---------------------------------------------------------------------------
def _session_path(session_id: str) -> str:
    return os.path.join(settings.cache_dir, "sessions", f"{session_id}.json")


def _save(session: PlanSession) -> None:
    path = _session_path(session.session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(session.model_dump(), fh, ensure_ascii=False, default=str)


def _push_history(session: PlanSession) -> PlanSession:
    """把变更前的完整状态压栈（不含 history 自身，避免快照嵌套膨胀）。"""
    snapshot = copy.deepcopy(session.model_dump())
    snapshot.pop("history", None)
    session.history = (list(session.history) + [snapshot])[-_HISTORY_LIMIT:]
    return session


def _log_stage(session: PlanSession, event: str) -> None:
    log_event(_logger, event, session_id=session.session_id, stage=session.stage, outcome="ok")


# ---------------------------------------------------------------------------
# 公共入口
# ---------------------------------------------------------------------------
def start(user_data: dict) -> PlanSession:
    session = PlanSession(session_id=uuid.uuid4().hex[:12], stage=0, user_data=dict(user_data or {}))
    _save(session)
    _log_stage(session, "plan_session_started")
    return session


def get(session_id: str) -> PlanSession:
    try:
        with open(_session_path(session_id), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise KeyError("session_not_found") from exc
    return PlanSession.model_validate(raw)


def submit_stage(session_id: str, stage: int, payload: dict | None = None) -> PlanSession:
    session = get(session_id)
    stage = int(stage)
    if stage < 1 or stage > 6 or stage != session.stage + 1:
        raise ValueError("stage_out_of_order")

    session = _push_history(session)
    _STAGE_HANDLERS[stage](session, dict(payload or {}))
    session.stage = stage
    _save(session)
    _log_stage(session, "plan_stage_submitted")
    return session


def back(session_id: str) -> PlanSession:
    session = get(session_id)
    if session.stage == 0 or not session.history:
        raise ValueError("no_previous_stage")

    remaining = list(session.history[:-1])
    restored = PlanSession.model_validate(session.history[-1])
    restored.history = remaining
    _save(restored)
    _log_stage(restored, "plan_stage_rolled_back")
    return restored


def modify(session_id: str, patch: dict) -> tuple[PlanSession, list[Issue]]:
    session = get(session_id)
    patch = dict(patch or {})
    updated = copy.deepcopy(session.itinerary)
    entry = _day_entry(updated, patch.get("day"))

    if "remove" in patch:
        name = str((patch.get("remove") or {}).get("name") or "")
        items = [item for item in entry.get("items") or [] if str(item.get("name")) != name]
        if len(items) == len(entry.get("items") or []):
            raise KeyError("item_not_found")
        entry["items"] = items
    elif "replace" in patch:
        target = patch.get("replace") or {}
        name = str(target.get("name") or "")
        new_fields = target.get("new") or {}
        hit = False
        for item in entry.get("items") or []:
            if str(item.get("name")) == name:
                item.update(new_fields)
                hit = True
        if not hit:
            raise KeyError("item_not_found")
    elif "reorder" in patch:
        order = [str(name) for name in (patch.get("reorder") or [])]
        order_index = {name: index for index, name in enumerate(order)}
        entry["items"] = sorted(
            entry.get("items") or [],
            key=lambda item: order_index.get(str(item.get("name")), len(order)),
        )
    else:
        raise ValueError("unsupported_patch")

    session = _push_history(session)
    session.itinerary = updated
    session.budget = _compute_budget(session)
    _save(session)
    _log_stage(session, "plan_modified")

    issues = validate_itinerary(
        session.itinerary,
        _places_from_plan(session.chosen_plan or {}, session.user_data),
        start_date=str(session.user_data.get("dep_date") or ""),
        crowd_mode=str(session.user_data.get("crowd_mode") or "normal"),
    )
    return session, issues


def replace_itinerary(session_id: str, itinerary: list[dict]) -> PlanSession:
    """整体覆写行程（天气重排等场景），变更前状态压入 history 以支持回退。"""
    session = get(session_id)
    if not isinstance(itinerary, list) or not itinerary:
        raise ValueError("invalid_itinerary")

    session = _push_history(session)
    session.itinerary = copy.deepcopy(itinerary)
    session.budget = _compute_budget(session)
    _save(session)
    _log_stage(session, "plan_itinerary_replaced")
    return session


def run_all(user_data: dict) -> PlanSession:
    session = start(user_data)
    _run_stages(session.session_id)
    return get(session.session_id)


def run_all_async(user_data: dict) -> str:
    session = start(user_data)
    threading.Thread(target=_run_stages, args=(session.session_id,), daemon=True).start()
    return session.session_id


def _run_stages(session_id: str) -> None:
    """顺序推进 stage 1..6；失败只落库 error 并停止，已完成的阶段保留。"""
    stage = 0
    try:
        for stage in range(1, 7):
            submit_stage(session_id, stage, {})
    except Exception as exc:
        log_event(_logger, "plan_generation_failed", session_id=session_id, stage=stage, outcome="error")
        try:
            failed = get(session_id)
            failed.generation_error = f"第 {stage} 步失败：{type(exc).__name__}"
            _save(failed)
        except Exception as save_exc:
            log_event(
                _logger,
                "plan_generation_error_save_failed",
                session_id=session_id,
                error=f"{type(save_exc).__name__}: {save_exc}",
                outcome="error",
            )


# ---------------------------------------------------------------------------
# 六个阶段
# ---------------------------------------------------------------------------
def _stage_user_info(session: PlanSession, payload: dict) -> None:
    merged = dict(session.user_data)
    merged.update(payload)
    session.user_data = _normalize_user_data(merged)


def _stage_transport(session: PlanSession, payload: dict) -> None:
    user_data = session.user_data
    departure = str(user_data.get("departure") or "")
    destination = str(user_data.get("destination") or "")

    trains = _sorted_transport(_safe_call(crawl_train, [], departure, destination))
    flights = _sorted_transport(_safe_call(crawl_flight, [], departure, destination))
    try:
        filtered = filter_transport(trains, flights, user_data)
    except Exception as exc:
        log_event(_logger, "transport_filter_failed", error=f"{type(exc).__name__}: {exc}")
        filtered = {"trains": trains, "flights": flights}

    pools = {
        "train": list(filtered.get("trains") or trains or []),
        "flight": list(filtered.get("flights") or flights or []),
    }
    pref = str(user_data.get("transport_pref") or "both")
    preference_order = ("flight", "train") if pref in ("flight", "both") else ("train", "flight")

    mode = str(payload.get("mode") or "")
    if mode not in ("train", "flight"):
        mode = next((candidate for candidate in preference_order if pools[candidate]), "flight")

    pool = pools.get(mode) or []
    outbound = _pick(pool, payload.get("outbound_index"), _FALLBACK_FLIGHT)
    back_option = _pick(pool, payload.get("return_index"), outbound)

    out_price = _option_price(outbound, mode)
    back_price = _option_price(back_option, mode)
    people = int(user_data.get("people") or 1)

    session.transport = {
        "mode": mode,
        "outbound_type": mode,
        "outbound": outbound,
        "outbound_price": out_price,
        "return": back_option,
        "return_price": back_price,
        "price_per_person": out_price,
        "total": (out_price + back_price) * people,
    }


def _stage_plan_data(session: PlanSession, payload: dict) -> None:
    user_data = session.user_data
    departure = str(user_data.get("departure") or "")
    days = int(user_data.get("days") or 3)
    budget_level = str(user_data.get("hotel_level") or "mid")
    preferences = {
        "age_group": user_data.get("age_group", "friends"),
        "tastes": user_data.get("tastes") or [],
    }
    cities = user_data.get("cities") or [{"city": user_data.get("destination") or "", "days": days}]
    multi_city = bool(user_data.get("is_multi_city")) and len(cities) > 1

    plans: list[dict] = []
    for city_entry in cities:
        city_name = str(city_entry.get("city") or user_data.get("destination") or "")
        city_days = int(city_entry.get("days") or days) if multi_city else days
        city_data = _load_city_data(departure, city_name, user_data)
        if not city_data["attractions"]:
            continue

        built: list[dict] = []
        try:
            built = generate_plans(
                city_name,
                city_days,
                city_data["attractions"],
                city_data["hotels"],
                city_data["foods"],
                budget_level,
                preferences,
            )
        except Exception as exc:
            log_event(_logger, "plan_generate_failed", error=f"{type(exc).__name__}: {exc}")
        if not built:
            built = [_fallback_plan(city_name, city_days, city_data)]

        if multi_city:
            built = built[:2]
            for plan in built:
                plan["_city"] = city_name
        plans.extend(built)
        if not multi_city:
            break

    if not plans:
        plans = [_fallback_plan(str(user_data.get("destination") or ""), days, _empty_city_data())]
    session.plans = plans


def _stage_select_plan(session: PlanSession, payload: dict) -> None:
    plans = session.plans or []
    if not plans:
        raise ValueError("no_plan_available")
    index = int(payload.get("index") or 0)
    session.chosen_plan = copy.deepcopy(plans[index] if 0 <= index < len(plans) else plans[0])


def _stage_itinerary(session: PlanSession, payload: dict) -> None:
    chosen_plan = session.chosen_plan or {}
    session.itinerary = _build_itinerary(session.user_data, chosen_plan)
    session.user_data["_avg_food"] = _avg_food(chosen_plan)


def _stage_budget(session: PlanSession, payload: dict) -> None:
    session.budget = _compute_budget(session)


_STAGE_HANDLERS: dict[int, Callable[[PlanSession, dict], None]] = {
    1: _stage_user_info,
    2: _stage_transport,
    3: _stage_plan_data,
    4: _stage_select_plan,
    5: _stage_itinerary,
    6: _stage_budget,
}


# ---------------------------------------------------------------------------
# 阶段内部实现
# ---------------------------------------------------------------------------
def _normalize_user_data(raw: dict) -> dict:
    data = dict(raw)
    cities = [dict(entry) for entry in (data.get("cities") or []) if entry.get("city")]
    for entry in cities:
        entry["days"] = max(1, int(entry.get("days") or 1))

    days = int(data.get("days") or 0)
    if cities:
        if days <= 0:
            days = sum(entry["days"] for entry in cities)
        destination = str(data.get("destination") or cities[0]["city"])
    else:
        destination = str(data.get("destination") or data.get("departure") or "")
        days = days or 3
        cities = [{"city": destination, "days": days}]

    dep_date = _parse_date(str(data.get("dep_date") or "")) or (datetime.now() + timedelta(days=1))
    days = max(1, min(30, days))

    data["destination"] = destination
    data["cities"] = cities
    data["is_multi_city"] = len(cities) > 1
    data["days"] = days
    data["dep_date"] = dep_date.strftime("%Y-%m-%d")
    data["return_date"] = (dep_date + timedelta(days=days)).strftime("%Y-%m-%d")
    data["people"] = max(1, int(data.get("people") or 2))
    data["budget"] = max(500.0, float(data.get("budget") or 2500))
    data.setdefault("transport_pref", "both")
    data.setdefault("hotel_level", "mid")
    data.setdefault("hotel_location", "subway")
    data.setdefault("tastes", [])
    data.setdefault("age_group", "friends")
    data["crowd_mode"] = str(
        data.get("crowd_mode") or _CROWD_BY_AGE.get(str(data.get("age_group")), "normal")
    )
    return data


def _load_city_data(departure: str, city: str, user_data: dict) -> dict:
    data: dict = {}
    try:
        data = crawl_all(departure, city, show_progress=False, user_data=user_data) or {}
    except Exception as exc:
        log_event(_logger, "crawl_failed", error=f"{type(exc).__name__}: {exc}", provider="spiders")

    attractions = list(data.get("attractions") or [])
    if not attractions:
        try:
            from data.attraction_data import get_attraction_backup

            attractions = list(get_attraction_backup(city) or [])
        except Exception:
            attractions = []
    for item in attractions:
        item.setdefault("_city", city)

    return {
        "attractions": attractions,
        "foods": list(data.get("foods") or []),
        "hotels": list(data.get("hotels") or []),
    }


def _empty_city_data() -> dict:
    return {"attractions": [], "foods": [], "hotels": []}


def _fallback_plan(city: str, days: int, city_data: dict) -> dict:
    attractions = city_data["attractions"][: days * 2]
    return {
        "style": {"id": "classic", "name": (city + "经典") if city else "经典打卡", "emoji": "🏛️"},
        "score": 80,
        "attractions": attractions,
        "hotels": city_data["hotels"][:3],
        "restaurants": city_data["foods"][: days * 3],
        "itinerary": [],
        "total_attractions": len(attractions),
        "total_foods": len(city_data["foods"][: days * 3]),
    }


def _build_itinerary(user_data: dict, chosen_plan: dict) -> list[dict]:
    days = max(1, int(user_data.get("days") or 3))
    attractions = list(chosen_plan.get("attractions") or [])
    plan_days = list(chosen_plan.get("itinerary") or [])

    if plan_days:
        per_day = [list(entry.get("attractions") or []) for entry in plan_days]
    else:
        per_day_count = max(1, (len(attractions) + days - 1) // days)
        per_day = [
            attractions[index * per_day_count:(index + 1) * per_day_count]
            for index in range(days)
        ]

    start = _parse_date(str(user_data.get("dep_date") or "")) or datetime.now()
    itinerary: list[dict] = []
    for day_index, day_attrs in enumerate(per_day, 1):
        items: list[dict] = []
        for slot_index, attr in enumerate(day_attrs[: len(_SLOTS)]):
            slot_start, slot_end = _SLOTS[slot_index]
            items.append(
                {
                    "name": str(attr.get("name") or f"景点{slot_index + 1}"),
                    "start": slot_start,
                    "end": slot_end,
                    "lng": _coord(attr.get("lng")),
                    "lat": _coord(attr.get("lat")),
                    "indoor": bool(attr.get("indoor", attr.get("is_indoor", False))),
                }
            )
        itinerary.append(
            {
                "day": day_index,
                "date": (start + timedelta(days=day_index - 1)).strftime("%Y-%m-%d"),
                "items": items,
            }
        )
    return itinerary


def _compute_budget(session: PlanSession) -> dict:
    chosen_plan = session.chosen_plan or {}
    hotels = chosen_plan.get("hotels") or []
    hotel = hotels[0] if hotels else None
    result = calculate_budget(
        dict(session.user_data),
        session.transport,
        list(chosen_plan.get("attractions") or []),
        hotel,
        str(session.user_data.get("hotel_location") or "subway"),
    )
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return dict(result)


def _places_from_plan(chosen_plan: dict, user_data: dict) -> list[PlaceItem]:
    fetched_at = datetime.now().astimezone().isoformat(timespec="seconds")
    city_default = str(user_data.get("destination") or "")
    places: list[PlaceItem] = []
    for attr in chosen_plan.get("attractions") or []:
        try:
            places.append(
                PlaceItem(
                    name=str(attr.get("name") or ""),
                    type="attraction",
                    city=str(attr.get("_city") or city_default),
                    address=str(attr.get("address") or ""),
                    lng=_coord(attr.get("lng")),
                    lat=_coord(attr.get("lat")),
                    open_time=str(attr.get("open_time") or ""),
                    avg_price=_as_float(attr.get("ticket_price")),
                    phone=str(attr.get("phone") or ""),
                    indoor=bool(attr.get("indoor", attr.get("is_indoor", False))),
                    source=str(attr.get("_source") or "legacy"),
                    source_url=str(attr.get("source_url") or ""),
                    fetched_at=str(attr.get("fetched_at") or fetched_at),
                    confidence=_as_float(attr.get("confidence")) or 0.3,
                )
            )
        except Exception:
            continue
    return places


def _day_entry(itinerary: list[dict], day: Any) -> dict:
    target = int(day or 0)
    for entry in itinerary:
        if int(entry.get("day") or 0) == target:
            return entry
    raise KeyError("day_not_found")


def _avg_food(chosen_plan: dict) -> float:
    prices: list[float] = []
    for food in (chosen_plan.get("restaurants") or [])[:5]:
        price = _as_float(food.get("avg_price"))
        if price is not None:
            prices.append(price)
    return sum(prices) / len(prices) if prices else 80.0


def _sorted_transport(options: list) -> list:
    if not options:
        return []
    try:
        return list(sort_transport_options(options) or [])
    except Exception:
        return list(options)


def _safe_call(func: Callable[..., list], default: list, *args: Any) -> list:
    try:
        return list(func(*args) or [])
    except Exception as exc:
        log_event(_logger, "crawl_transport_failed", error=f"{type(exc).__name__}: {exc}")
        return default


def _pick(pool: list, index: Any, default: dict) -> dict:
    if not pool:
        return dict(default)
    try:
        position = int(index or 0)
    except (TypeError, ValueError):
        position = 0
    if 0 <= position < len(pool):
        return pool[position]
    return pool[0]


def _option_price(option: dict, mode: str) -> float:
    if mode == "flight":
        price = (option.get("cabin") or {}).get("经济舱")
    else:
        price = (option.get("seats") or {}).get("二等座")
    return _as_float(price) or _as_float(option.get("price")) or 0.0


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coord(value: Any) -> float | None:
    number = _as_float(value)
    return None if not number else number


def _parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None