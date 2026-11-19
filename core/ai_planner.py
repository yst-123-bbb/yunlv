# -*- coding: utf-8 -*-
"""AI 增强型行程规划器
功能:
  1. 如果配置了 Kimi -> 用 Kimi 生成智能行程
  2. 否则 -> 回退到本地 core.plan_generator 规则引擎
  3. 返回统一格式, 对 main.py 透明

使用:
  from core.ai_planner import generate_trip_plan
  result = generate_trip_plan(user_data, attractions, hotels, foods)
  # result = { "source": "kimi" | "local", "content": ... }
"""
import sys
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE = os.path.dirname(_THIS_DIR)
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)


def _try_kimi(user_data, attractions, restaurants, hotels, style_name=None):
    """尝试用 Kimi 生成, 失败返回 None"""
    try:
        from apis.kimi_api import KimiClient
    except Exception:
        return None
    try:
        from config import KIMI_ENABLED, KIMI_API_KEY
    except Exception:
        KIMI_ENABLED = False
        KIMI_API_KEY = ""
    if not KIMI_ENABLED or not KIMI_API_KEY:
        return None
    client = KimiClient()
    if not client.available():
        return None
    reply = client.generate_plan(user_data, attractions, restaurants,
                                 hotels, style_name=style_name)
    if not reply:
        return None
    return {
        "source": "kimi",
        "model": client.model,
        "text": reply,
        "style": style_name or "智能规划",
    }


def _fallback_local(user_data, attractions, restaurants, hotels):
    """回退到本地规则引擎, 组装成统一的输出格式"""
    try:
        from core.plan_generator import (generate_plans, PLAN_STYLES)
    except Exception as e:
        return {"source": "local", "text": "本地引擎不可用: " + str(e),
                "style": "基础规则"}

    budget_level = user_data.get("hotel_level", "mid")
    preferences = {
        "age_group": user_data.get("age_group", "friends"),
        "tastes": user_data.get("tastes", []),
    }
    dest = user_data.get("destination", "当地")
    days = int(user_data.get("days", 3) or 3)

    try:
        plans = generate_plans(dest, days, attractions, hotels,
                               restaurants, budget_level, preferences)
    except Exception:
        plans = []

    if not plans:
        return {"source": "local", "style": "基础规则",
                "text": "抱歉, 暂无足够数据生成方案。"}

    # 选第一个方案(评分最高)输出成文本
    plan = plans[0]
    style = plan.get("style", {})
    lines = []
    lines.append("【%s %s】评分:%s分 - %s" % (
        style.get("emoji", "📌"),
        style.get("name", "经典方案"),
        plan.get("score", 80),
        style.get("desc", ""),
    ))
    attrs = plan.get("attractions", [])
    if attrs:
        lines.append("\n推荐景点 (%d处):" % len(attrs))
        for a in attrs[:days * 3]:
            if isinstance(a, dict):
                lines.append("  · %s  %s" % (
                    a.get("name", ""),
                    ("门票" + str(a.get("ticket_price", "")) + "元")
                    if a.get("ticket_price") else "",
                ))
    rests = plan.get("restaurants", [])
    if rests:
        lines.append("\n推荐餐厅 (%d家):" % len(rests))
        for r in rests[:days * 2]:
            if isinstance(r, dict):
                lines.append("  · %s  人均%s元" % (
                    r.get("name", ""),
                    r.get("avg_price", "-"),
                ))
    hots = plan.get("hotels", [])
    if hots:
        lines.append("\n推荐住宿 (%d家):" % len(hots))
        for h in hots[:3]:
            if isinstance(h, dict):
                lines.append("  · %s  %s元/晚" % (
                    h.get("name", ""),
                    h.get("price_per_night", h.get("price", "-")),
                ))
    lines.append("\n注: 此方案由本地规则引擎生成, 启用 Kimi 可获得更智能的行程。")
    return {"source": "local", "style": style.get("name", "经典方案"),
            "text": "\n".join(lines)}


def generate_trip_plan(user_data, attractions=None, hotels=None,
                       restaurants=None, style_name=None, prefer_kimi=True):
    """统一入口: 先试 Kimi, 失败自动回退本地
    参数:
      user_data: dict (departure, destination, days, people, budget...)
      attractions/restaurants/hotels: list of dict POI
      style_name: 可选, 方案风格名称
      prefer_kimi: True=优先使用 Kimi
    返回:
      dict = {"source": "kimi"|"local", "text": str, "style": str, "model": str}
    """
    attractions = attractions or []
    restaurants = restaurants or []
    hotels = hotels or []

    if prefer_kimi:
        kimi_result = _try_kimi(user_data, attractions, restaurants,
                                hotels, style_name=style_name)
        if kimi_result:
            return kimi_result
    return _fallback_local(user_data, attractions, restaurants, hotels)


def quick_summary(summary_text):
    """便捷: 用 Kimi 做文案润色, 失败返回原文"""
    try:
        from apis.kimi_api import KimiClient
        from config import KIMI_ENABLED, KIMI_API_KEY
    except Exception:
        return summary_text
    if not KIMI_ENABLED or not KIMI_API_KEY:
        return summary_text
    client = KimiClient()
    if not client.available():
        return summary_text
    reply = client.summarize(summary_text)
    return reply or summary_text


if __name__ == "__main__":
    # 简单测试
    demo_user = {
        "departure": "北京", "destination": "长沙",
        "dep_date": "2026-06-15", "days": 3, "people": 2,
        "age_group": "friends", "tastes": ["local", "spicy"],
        "hotel_level": "mid", "transport_pref": "both", "budget": 2500,
    }
    demo_attrs = [
        {"name": "岳麓山", "rating": "4.7", "ticket_price": 0,
         "feature": "登山赏景, 爱晚亭"},
        {"name": "橘子洲", "rating": "4.6", "ticket_price": 0,
         "feature": "湘江小岛, 毛主席雕像"},
        {"name": "湖南省博物馆", "rating": "4.8", "ticket_price": 0,
         "feature": "马王堆汉墓文物"},
    ]
    result = generate_trip_plan(demo_user, attractions=demo_attrs)
    print("来源:", result.get("source"))
    print("风格:", result.get("style"))
    print("----\n")
    print(result.get("text", "")[:600])