# -*- coding: utf-8 -*-
"""多方案生成器 - 参考LX SkyRoam Agent设计
为同一行程需求生成多个不同风格的方案，用户可选择

特色:
  - 多风格方案: 经典打卡 / 文化深度 / 亲子休闲 / 美食探店 / 轻松漫步
  - 智能筛选: 根据方案风格筛选景点/餐厅/酒店
  - 按天编排: 智能分配景点到各天，考虑地理位置和游玩时长
  - 评分排序: 每个方案从景点丰富度、餐饮匹配度、预算贴合度等维度评分
"""
import sys
import os
import random

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE = os.path.dirname(_THIS_DIR)
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)


# 方案风格定义
PLAN_STYLES = [
    {
        "id": "classic",
        "name": "经典打卡",
        "emoji": "🏛️",
        "desc": "名胜古迹为主，适合初次到访，地标景点全覆盖",
        "tag_priority": ["风景名胜", "网红打卡", "拍照出片", "历史文化"],
        "price_level": "mid",
        "attractions_per_day": 3,
        "food_style": "当地特色",
    },
    {
        "id": "culture",
        "name": "文化深度",
        "emoji": "📚",
        "desc": "博物馆+历史街区，深度了解当地文化",
        "tag_priority": ["历史文化", "室内参观", "适合亲子", "博物馆"],
        "price_level": "low",
        "attractions_per_day": 2,
        "food_style": "老字号",
    },
    {
        "id": "family",
        "name": "亲子休闲",
        "emoji": "👨‍👩‍👧",
        "desc": "公园休闲+轻松节奏，适合带老人小孩",
        "tag_priority": ["自然风光", "户外散步", "免费开放", "适合亲子"],
        "price_level": "mid",
        "attractions_per_day": 2,
        "food_style": "大众消费",
    },
    {
        "id": "foodie",
        "name": "美食探店",
        "emoji": "🍜",
        "desc": "以美食为主线，景点轻松辅助安排",
        "tag_priority": ["网红打卡", "人气热门", "免费开放", "拍照出片"],
        "price_level": "any",
        "attractions_per_day": 2,
        "food_style": "特色美食",
    },
    {
        "id": "relax",
        "name": "轻松漫步",
        "emoji": "🌸",
        "desc": "少景点多留白，适合不想赶行程的慢游",
        "tag_priority": ["免费开放", "户外散步", "自然风光", "网红打卡"],
        "price_level": "low",
        "attractions_per_day": 2,
        "food_style": "休闲餐饮",
    },
]


def _match_score(attr, style):
    """计算景点与方案风格的匹配度(0-100)"""
    score = 0
    tags = ""
    if isinstance(attr, dict):
        tags = " ".join([
            str(attr.get("feature", "")),
            str(attr.get("tags", "")),
            str(" ".join(attr.get("features", []))),
        ])
    else:
        tags = str(attr)

    for tag in style["tag_priority"]:
        if tag in tags:
            score += 25

    rating = float(attr.get("rating", 4.5)) if isinstance(attr, dict) else 4.5
    score += int(rating * 5)

    if attr.get("is_free"):
        score += 5

    return min(100, score)


def generate_plans(city, days, attractions, hotels, restaurants,
                   budget_level="mid", preferences=None):
    """生成多个方案

    Args:
        city: 城市名
        days: 游玩天数
        attractions: 景点列表
        hotels: 酒店列表
        restaurants: 餐厅列表
        budget_level: 预算等级 low/mid/high
        preferences: 用户偏好（可选）

    Returns:
        [{"style": {...}, "score": int, "itinerary": [...], "hotel": {...}}, ...]
    """
    preferences = preferences or {}

    plans = []
    # 为每个风格生成方案，最多3个有意义的
    for style in PLAN_STYLES[:4]:

        # 1. 按风格筛选景点
        scored_attrs = []
        for a in attractions:
            s = _match_score(a, style)
            scored_attrs.append((s, a))
        scored_attrs.sort(key=lambda x: x[0], reverse=True)

        needed = style["attractions_per_day"] * days
        chosen_attrs = [item[1] for item in scored_attrs[:needed]]

        if not chosen_attrs:
            continue

        # 2. 按风格筛选酒店
        if budget_level == "low":
            price_range = (0, 350)
        elif budget_level == "high":
            price_range = (500, 99999)
        else:
            price_range = (250, 650)

        chosen_hotels = []
        for h in hotels:
            p = float(h.get("price", h.get("price_per_night", 300)))
            if price_range[0] <= p <= price_range[1]:
                chosen_hotels.append(h)
        if not chosen_hotels:
            chosen_hotels = hotels[:3]
        chosen_hotel = chosen_hotels[0] if chosen_hotels else None

        # 3. 按风格筛选餐厅
        scored_foods = []
        for r in restaurants:
            fs = 0
            tags = str(r.get("cuisine", "")) + " " + str(r.get("feature", ""))
            if style["food_style"] in tags:
                fs += 30
            fs += int(float(r.get("rating", 4.5)) * 5)
            if budget_level == "low" and int(r.get("avg_price", 80)) <= 80:
                fs += 20
            if budget_level == "high" and int(r.get("avg_price", 80)) >= 100:
                fs += 20
            scored_foods.append((fs, r))
        scored_foods.sort(key=lambda x: x[0], reverse=True)
        chosen_foods = [item[1] for item in scored_foods[:days * 3]]

        # 4. 按天编排
        itinerary = _assign_by_days(city, days, chosen_attrs, chosen_foods, chosen_hotel, style)

        # 5. 计算方案评分
        score = _calc_plan_score(chosen_attrs, chosen_foods, chosen_hotel, itinerary,
                                 budget_level, preferences)

        plans.append({
            "style": style,
            "score": score,
            "itinerary": itinerary,
            "attractions": chosen_attrs,
            "hotels": chosen_hotels[:3],
            "restaurants": chosen_foods,
            "total_attractions": len(chosen_attrs),
            "total_foods": len(chosen_foods),
        })

    plans.sort(key=lambda p: p["score"], reverse=True)
    return plans


def _assign_by_days(city, days, attractions, restaurants, hotel, style):
    """将景点分配到各天，生成每日行程"""
    per_day = max(1, (len(attractions) + days - 1) // days)
    itinerary = []

    idx = 0
    for d in range(days):
        day_attrs = attractions[idx: idx + per_day]
        idx += per_day

        day_foods = []
        food_start = d * 2
        if restaurants:
            day_foods = restaurants[food_start: food_start + 2]

        weather = random.choice(["晴", "多云", "阴"])
        temp_low = random.randint(15, 22)
        temp_high = random.randint(22, 32)

        day_data = {
            "day": d + 1,
            "title": "第" + str(d + 1) + "天 · " + style["name"] + "游",
            "weather": weather,
            "temp_low": temp_low,
            "temp_high": temp_high,
            "weather_tip": "天气良好，适合出行",
            "attractions": day_attrs,
            "foods": day_foods,
            "hotel": hotel if d < days - 1 else None,
            "attractions_count": len(day_attrs),
            "play_hours_total": sum(a.get("play_hours", 3) for a in day_attrs),
            "style_id": style["id"],
            "style_name": style["name"],
        }
        itinerary.append(day_data)

    return itinerary


def _calc_plan_score(attractions, restaurants, hotel, itinerary,
                     budget_level, preferences):
    """计算方案综合评分(0-100)"""
    score = 0

    # 1. 景点丰富度(30分)
    if attractions:
        avg_rating = sum(float(a.get("rating", 4.5)) for a in attractions) / len(attractions)
        score += min(30, int(avg_rating * 6))
        if len(attractions) >= 3:
            score += 5

    # 2. 餐饮匹配度(25分)
    if restaurants:
        avg_price = sum(float(r.get("avg_price", 80)) for r in restaurants[:5]) / max(1, min(5, len(restaurants)))
        if budget_level == "low" and avg_price <= 80:
            score += 25
        elif budget_level == "mid" and 60 <= avg_price <= 150:
            score += 25
        elif budget_level == "high" and avg_price >= 100:
            score += 25
        else:
            score += 15

    # 3. 预算贴合度(20分)
    if hotel:
        hp = float(hotel.get("price", hotel.get("price_per_night", 300)))
        if budget_level == "low" and hp <= 350:
            score += 20
        elif budget_level == "mid" and 250 <= hp <= 650:
            score += 20
        elif budget_level == "high" and hp >= 500:
            score += 20
        else:
            score += 10

    # 4. 时间合理性(15分)
    total_days = len(itinerary)
    total_attrs = len(attractions)
    if total_days > 0 and 1 <= total_attrs / total_days <= 4:
        score += 15
    elif total_days > 0 and total_attrs / total_days <= 5:
        score += 10

    # 5. 多样性(10分)
    categories = set()
    for a in attractions:
        f = a.get("feature", "")
        for c in f.split("、"):
            categories.add(c.strip())
    score += min(10, len(categories) * 2)

    return min(100, score)


def format_plan_summary(plan, city, budget_level):
    """生成方案的简洁摘要，供用户选择时显示"""
    style = plan["style"]
    itin = plan["itinerary"]
    attrs = plan["attractions"]
    score = plan["score"]

    lines = []
    lines.append(style["emoji"] + " 【" + style["name"] + "】 综合评分:" + str(score) + "分")
    lines.append("   " + style["desc"])
    lines.append("   景点: " + str(len(attrs)) + "处 | 餐厅: " +
                 str(plan["total_foods"]) + "家 | " + str(len(itin)) + "天")
    lines.append("   每日行程:")
    for day in itin[:3]:
        names = [a.get("name", "景点") for a in day["attractions"][:3]]
        lines.append("     Day" + str(day["day"]) + ": " + " → ".join(names) if names else "")
    return "\n".join(lines)


def format_full_plan(plan, city, total_days):
    """生成完整的每日行程文本"""
    style = plan["style"]
    lines = []
    lines.append("=" * 56)
    lines.append("  ✈ " + city + " · " + style["name"] + "方案  共" + str(total_days) + "天")
    lines.append("  " + style["desc"])
    lines.append("=" * 56)

    total_ticket = 0
    total_food = 0

    for day in plan["itinerary"]:
        lines.append("")
        lines.append("  第" + str(day["day"]) + "天 · " + day["title"].split("·")[-1].strip())
        lines.append("  天气: " + day["weather"] + " " + str(day["temp_low"]) +
                     "~" + str(day["temp_high"]) + "°C | " + day["weather_tip"])
        lines.append("  " + "-" * 52)

        for i, a in enumerate(day["attractions"], 1):
            lines.append("  " + str(i) + ". " + a.get("name", "景点"))
            lines.append("     地址: " + str(a.get("address", "")))
            if a.get("ticket_price", 0) > 0:
                lines.append("     门票: " + str(a["ticket_price"]) + "元  游玩约" +
                             str(a.get("play_hours", 3)) + "小时")
                total_ticket += a["ticket_price"]
            else:
                lines.append("     免费开放  游玩约" + str(a.get("play_hours", 3)) + "小时")
            lines.append("     特色: " + a.get("feature", ""))

        if day["foods"]:
            lines.append("")
            lines.append("  🍜 推荐餐饮:")
            for f in day["foods"]:
                lines.append("     · " + f.get("name", "餐厅") + "  人均" +
                             str(f.get("avg_price", 80)) + "元  " + f.get("feature", ""))
                total_food += f.get("avg_price", 80)

        if day.get("hotel"):
            h = day["hotel"]
            lines.append("")
            lines.append("  🏨 住宿: " + h.get("name", "酒店") + "  约" +
                         str(h.get("price", h.get("price_per_night", 300))) + "元/晚")
            lines.append("     " + h.get("address", ""))

        lines.append("")

    # 摘要
    lines.append("=" * 56)
    lines.append("  📊 方案摘要")
    lines.append("    景点门票(人均): 约" + str(int(total_ticket)) + "元")
    lines.append("    餐饮(人均): 约" + str(int(total_food)) + "元")
    lines.append("    综合评分: " + str(plan["score"]) + "分")
    lines.append("=" * 56)
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 50)
    print("  多方案生成器 - 测试")
    print("=" * 50)

    # 模拟测试数据
    test_attrs = [
        {"name": "故宫博物院", "address": "北京市东城区", "feature": "历史文化、室内参观、适合亲子",
         "play_hours": 4, "ticket_price": 60, "rating": 4.8, "features": ["历史文化", "室内参观"]},
        {"name": "天安门广场", "address": "北京市中心", "feature": "风景名胜、网红打卡",
         "play_hours": 2, "ticket_price": 0, "rating": 4.7, "features": ["风景名胜", "网红打卡"]},
        {"name": "颐和园", "address": "北京市海淀区", "feature": "自然风光、户外散步、历史文化",
         "play_hours": 3, "ticket_price": 30, "rating": 4.7, "features": ["自然风光", "户外散步"]},
        {"name": "中国国家博物馆", "address": "北京市东城区", "feature": "历史文化、室内参观",
         "play_hours": 3, "ticket_price": 0, "rating": 4.8, "features": ["历史文化", "室内参观"]},
        {"name": "景山公园", "address": "北京市西城区", "feature": "自然风光、户外散步、免费开放",
         "play_hours": 2, "ticket_price": 2, "rating": 4.6, "features": ["自然风光", "免费开放"]},
        {"name": "南锣鼓巷", "address": "北京市东城区", "feature": "网红打卡、拍照出片",
         "play_hours": 2, "ticket_price": 0, "rating": 4.5, "features": ["网红打卡", "拍照出片"]},
    ]

    test_hotels = [
        {"name": "王府井希尔顿酒店", "address": "北京市东城区", "price": 680, "rating": 4.7, "feature": "高档型"},
        {"name": "全季酒店(王府井店)", "address": "北京市东城区", "price": 380, "rating": 4.6, "feature": "舒适型"},
        {"name": "如家快捷酒店", "address": "北京市东城区", "price": 220, "rating": 4.3, "feature": "经济型"},
    ]

    test_foods = [
        {"name": "全聚德烤鸭(前门店)", "cuisine": "北京菜、老字号", "avg_price": 180, "rating": 4.6, "feature": "高档餐厅"},
        {"name": "胡大饭馆(簋街店)", "cuisine": "川菜、小龙虾", "avg_price": 150, "rating": 4.7, "feature": "中高档"},
        {"name": "新和小馆", "cuisine": "京菜、炸酱面", "avg_price": 60, "rating": 4.6, "feature": "大众消费"},
        {"name": "姚记炒肝店", "cuisine": "北京小吃、老字号", "avg_price": 40, "rating": 4.5, "feature": "经济实惠"},
        {"name": "海底捞火锅", "cuisine": "火锅、川菜", "avg_price": 120, "rating": 4.8, "feature": "中高档"},
        {"name": "庆丰包子铺", "cuisine": "小吃、快餐", "avg_price": 30, "rating": 4.4, "feature": "经济实惠"},
    ]

    plans = generate_plans("北京", 3, test_attrs, test_hotels, test_foods, "mid")
    print("\n共生成 " + str(len(plans)) + " 个方案")
    print("-" * 50)
    for i, p in enumerate(plans):
        print("\n方案 " + str(i + 1) + ":")
        print(format_plan_summary(p, "北京", "mid"))