"""行程编排路由：创建、分步提交、回退、查询与局部修改。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from services import plan_service, profile_service, weather_service

router = APIRouter(prefix="/api/plan", tags=["plan"])


class PlanStartBody(BaseModel):
    user_data: dict[str, Any] = Field(default_factory=dict)


class StageBody(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class WeatherBody(BaseModel):
    weather_by_day: dict[str, Any]


@router.post("")
def create_plan(body: PlanStartBody) -> dict[str, Any]:
    state = plan_service.run_all(body.user_data)
    return {
        "session_id": state.session_id,
        "stage": state.stage,
        "state": state,
    }


@router.post("/async")
def create_plan_async(body: PlanStartBody) -> dict[str, Any]:
    return {"session_id": plan_service.run_all_async(body.user_data), "stage": 0}


@router.post("/{session_id}/stage/{stage}")
def submit_stage(session_id: str, stage: int, body: StageBody) -> dict[str, Any]:
    return {"state": plan_service.submit_stage(session_id, stage, body.payload)}


@router.post("/{session_id}/back")
def go_back(session_id: str) -> dict[str, Any]:
    return {"state": plan_service.back(session_id)}


@router.post("/{session_id}/modify")
def modify_plan(session_id: str, patch: dict[str, Any] = Body(...)) -> dict[str, Any]:
    state, issues = plan_service.modify(session_id, patch)
    return {"state": state, "issues": issues}


@router.get("/{session_id}")
def get_plan(session_id: str) -> dict[str, Any]:
    return {"state": profile_service.enrich_state(plan_service.get(session_id))}


@router.post("/{session_id}/replan-weather")
def replan_weather(session_id: str, body: WeatherBody) -> dict[str, Any]:
    return weather_service.replan(session_id, body.weather_by_day)