# -*- coding: utf-8 -*-
"""爬虫模块（升级版）- 参考LX SkyRoam Agent风格
数据来源:
  - 交通(高铁/航班): 本地兜底数据
  - 景点/美食/酒店: 优先高德地图POI搜索(多关键词并行) + 本地兜底
特色:
  - 增量预览: 每一步显示进度
  - 标准化: 统一输出格式(lng/lat/rating/price/tags)
  - 智能去重: 避免重复数据
  - 评分排序: 结果按评分排序
"""
import sys
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE = os.path.dirname(_THIS_DIR)
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from data.train_data import get_train_backup
from data.flight_data import get_flight_backup
from data.attraction_data import get_attraction_backup
from data.food_data import get_food_backup
from data.hotel_data import get_hotel_backup
from utils.helpers import mark_source, dedup
from core.filter import filter_places

# 尝试导入高德地图 API 模块（新版统一地图服务）
try:
    from apis.geo_api import search_attractions, search_restaurants, search_hotels, get_api_status
    HAS_AMAP_API = True
except Exception:
    HAS_AMAP_API = False
    def search_attractions(city, limit=12, show_progress=False):
        return []
    def search_restaurants(city, keyword="美食", limit=12, show_progress=False):
        return []
    def search_hotels(city, keyword="酒店", limit=10, show_progress=False):
        return []
    def get_api_status():
        return {"amap_enabled": False}


def _amap_available():
    """检查高德API是否已配置可用"""
    if not HAS_AMAP_API:
        return False
    try:
        return get_api_status().get("amap_enabled", False)
    except Exception:
        return False


def _filtered(items, user_data, kind):
    """筛选结果进入后续流程；筛选异常时退回原始结果"""
    try:
        return filter_places(items, user_data or {}, kind=kind)
    except Exception as e:
        print("  [筛选-" + kind + "] 异常: " + str(e))
        return items


# ============================================================
# 1. 交通方案 - 始终使用本地兜底
# ============================================================
def crawl_train(departure, destination):
    """高铁方案"""
    try:
        trains = get_train_backup(departure, destination)
        if trains:
            return mark_source(dedup(trains), False)
    except Exception:
        pass
    return mark_source(get_train_backup(departure, destination), False)


def crawl_flight(departure, destination):
    """航班方案"""
    try:
        flights = get_flight_backup(departure, destination)
        if flights:
            return mark_source(dedup(flights), False)
    except Exception:
        pass
    return mark_source(get_flight_backup(departure, destination), False)


# ============================================================
# 2. 景点 - 优先高德POI，失败则本地兜底
# ============================================================
def crawl_attractions(city, show_progress=True, user_data=None):
    """景点信息 - 优先高德POI搜索，失败时使用本地兜底"""
    use_amap = _amap_available()

    if use_amap:
        try:
            if show_progress:
                print("  → 正在搜索" + city + "景点信息(高德地图)...")
            pois = search_attractions(city, limit=15, show_progress=show_progress)
            if pois:
                converted = []
                for idx, p in enumerate(pois):
                    rating = float(p.get("rating", 4.5))
                    price = int(p.get("ticket_price", 0))
                    if price == 0:
                        price = random.choice([0, 0, 50, 60, 80, 100, 150])
                    name = p.get("name", "景点" + str(idx + 1))
                    addr = p.get("address", city + "市区")
                    features = p.get("features", [])
                    if isinstance(features, str):
                        features = [features]
                    if not features:
                        tags = str(p.get("tags", ""))
                        is_museum = any(k in tags for k in ["博物馆", "展览馆", "纪念馆"])
                        is_park = any(k in tags for k in ["公园", "广场", "花园"])
                        if is_museum:
                            features = ["历史文化", "室内参观", "适合亲子"]
                        elif is_park:
                            features = ["自然风光", "户外散步", "免费开放"]
                        else:
                            features = ["风景名胜", "网红打卡", "拍照出片"]

                    play_hours = 2 if "博物馆" in str(features) else (3 if "公园" in str(features) else 4)

                    item = {
                        "name": name, "address": addr,
                        "feature": "、".join(features),
                        "features": features,
                        "play_hours": play_hours,
                        "ticket_price": price,
                        "rating": rating,
                        "is_indoor": "室内" in str(features),
                        "is_free": price == 0,
                        "lat": p.get("lat", 0),
                        "lng": p.get("lng", 0),
                        "tips": "推荐游玩" + str(play_hours) + "小时，评分" + str(rating) + "分",
                        "_source": "高德地图POI",
                    }
                    converted.append(item)

                if converted:
                    if show_progress:
                        print("  ✓ 找到" + str(len(converted)) + "处景点")
                    return mark_source(
                        _filtered(dedup(converted), user_data, "attraction"), True
                    )
        except Exception as e:
            print("  [景点-高德] 获取异常: " + str(e))

    # 兜底: 本地数据
    try:
        if show_progress:
            print("  → 使用本地精选景点...")
        attrs = get_attraction_backup(city)
        if attrs:
            if show_progress:
                print("  ✓ 找到" + str(len(attrs)) + "处景点")
            return mark_source(
                _filtered(dedup(attrs), user_data, "attraction"), False
            )
    except Exception:
        pass
    return mark_source(
        _filtered(get_attraction_backup(city), user_data, "attraction"), False
    )


# ============================================================
# 3. 美食 - 优先高德POI，失败则本地兜底
# ============================================================
def crawl_food(city, show_progress=True, user_data=None):
    """美食餐厅 - 优先高德POI搜索"""
    use_amap = _amap_available()

    if use_amap:
        try:
            if show_progress:
                print("  → 正在搜索" + city + "美食餐厅...")
            pois = search_restaurants(city, limit=15, show_progress=show_progress)
            if pois:
                converted = []
                for p in pois:
                    name = p.get("name", "餐厅")
                    addr = p.get("address", city)
                    rating = float(p.get("rating", 4.5))
                    price = int(p.get("avg_price", 0))
                    if price == 0:
                        price = random.choice([30, 50, 60, 80, 100, 120, 150, 180, 200])
                    tags = str(p.get("cuisine", ""))

                    if price >= 150:
                        level = "高档餐厅"
                    elif price >= 80:
                        level = "中高档"
                    elif price >= 50:
                        level = "大众消费"
                    else:
                        level = "经济实惠"

                    features = [level]
                    if any(k in tags for k in ["火锅", "川菜", "湘菜"]):
                        features.append("口味地道")
                    if "小吃" in tags or "快餐" in tags:
                        features.append("快餐小吃")
                    if rating >= 4.7:
                        features.append("高评分")

                    item = {
                        "name": name, "address": addr,
                        "feature": "、".join(features),
                        "features": features,
                        "avg_price": price,
                        "price": price,
                        "rating": rating,
                        "cuisine": tags,
                        "phone": p.get("phone", ""),
                        "signature": "人均约" + str(price) + "元",
                        "tips": "人均约" + str(price) + "元，评分" + str(rating) + "分",
                        "_source": "高德地图POI",
                    }
                    converted.append(item)

                if converted:
                    if show_progress:
                        print("  ✓ 找到" + str(len(converted)) + "家餐厅")
                    return mark_source(
                        _filtered(dedup(converted), user_data, "food"), True
                    )
        except Exception as e:
            print("  [美食-高德] 获取异常: " + str(e))

    # 兜底: 本地数据
    try:
        if show_progress:
            print("  → 使用本地精选美食...")
        foods = get_food_backup(city)
        if foods:
            if show_progress:
                print("  ✓ 找到" + str(len(foods)) + "家餐厅")
            return mark_source(_filtered(dedup(foods), user_data, "food"), False)
    except Exception:
        pass
    return mark_source(_filtered(get_food_backup(city), user_data, "food"), False)


# ============================================================
# 4. 酒店 - 优先高德POI，失败则本地兜底
# ============================================================
def crawl_hotels(city, show_progress=True, user_data=None):
    """住宿酒店 - 优先高德POI搜索"""
    use_amap = _amap_available()

    if use_amap:
        try:
            if show_progress:
                print("  → 正在搜索" + city + "酒店住宿...")
            pois = search_hotels(city, limit=12, show_progress=show_progress)
            if pois:
                converted = []
                for p in pois:
                    name = p.get("name", "酒店")
                    addr = p.get("address", city)
                    rating = float(p.get("rating", 4.5))
                    price = int(p.get("price", 0))
                    if price == 0:
                        price = random.choice([180, 220, 260, 300, 350, 400, 500, 600, 800])
                    tags = str(p.get("tags", ""))

                    if price >= 800:
                        stars = "豪华型"
                        star_num = 5
                    elif price >= 500:
                        stars = "高档型"
                        star_num = 4
                    elif price >= 300:
                        stars = "舒适型"
                        star_num = 3
                    elif price >= 150:
                        stars = "经济型"
                        star_num = 2
                    else:
                        stars = "民宿/客栈"
                        star_num = 2

                    features = [stars]
                    if rating >= 4.7:
                        features.append("高口碑")
                    if "民宿" in name or "客栈" in name or "公寓" in name:
                        features.append("民宿风格")
                    if "国际" in name or "大酒店" in name or "宾馆" in name:
                        features.append("连锁品牌")

                    item = {
                        "name": name, "address": addr,
                        "stars": stars, "star_num": star_num,
                        "price_per_night": price, "price": price,
                        "room_type": stars,
                        "rating": rating,
                        "feature": "、".join(features),
                        "features": features,
                        "phone": p.get("phone", ""),
                        "lat": p.get("lat", 0),
                        "lng": p.get("lng", 0),
                        "distance": "市区中心位置",
                        "facilities": "Wi-Fi、空调、热水",
                        "reviews": "评分 " + str(rating) + " 分",
                        "tips": stars + "·约" + str(price) + "元/晚，评分" + str(rating) + "分",
                        "_source": "高德地图POI",
                    }
                    converted.append(item)

                if converted:
                    if show_progress:
                        print("  ✓ 找到" + str(len(converted)) + "家酒店")
                    return mark_source(
                        _filtered(dedup(converted), user_data, "hotel"), True
                    )
        except Exception as e:
            print("  [酒店-高德] 获取异常: " + str(e))

    # 兜底: 本地数据
    try:
        if show_progress:
            print("  → 使用本地精选酒店...")
        hotels = get_hotel_backup(city)
        if hotels:
            if show_progress:
                print("  ✓ 找到" + str(len(hotels)) + "家酒店")
            return mark_source(_filtered(dedup(hotels), user_data, "hotel"), False)
    except Exception:
        pass
    return mark_source(_filtered(get_hotel_backup(city), user_data, "hotel"), False)


# ============================================================
# 5. 一次性获取全部数据（带进度显示）
# ============================================================
def crawl_all(departure, destination, show_progress=True, user_data=None):
    """一次性爬取全部数据（参考LX SkyRoam风格）

    返回: 字典，包含交通+景点+美食+酒店+数据源状态
    """
    amap_on = _amap_available()
    source_label = " (高德地图POI实时数据)" if amap_on else " (本地精选数据)"

    print()
    print("  " + "=" * 56)
    print("  📡 正在获取" + destination + "旅行数据" + source_label)
    print("  " + "=" * 56)

    results = {}

    if show_progress:
        # 交通
        print("  [1/4] 交通方案...")
        results["trains"] = crawl_train(departure, destination)
        results["flights"] = crawl_flight(departure, destination)
        print("  ✓ 高铁 " + str(len(results["trains"])) + "条 + 航班 " + str(len(results["flights"])) + "条")

        # 景点
        print()
        print("  [2/4] 景点信息...")
        results["attractions"] = crawl_attractions(
            destination, show_progress=show_progress, user_data=user_data
        )

        # 美食
        print()
        print("  [3/4] 美食餐厅...")
        results["foods"] = crawl_food(
            destination, show_progress=show_progress, user_data=user_data
        )

        # 酒店
        print()
        print("  [4/4] 住宿酒店...")
        results["hotels"] = crawl_hotels(
            destination, show_progress=show_progress, user_data=user_data
        )
    else:
        tasks = {
            "trains": lambda: crawl_train(departure, destination),
            "flights": lambda: crawl_flight(departure, destination),
            "attractions": lambda: crawl_attractions(
                destination, show_progress=False, user_data=user_data
            ),
            "foods": lambda: crawl_food(
                destination, show_progress=False, user_data=user_data
            ),
            "hotels": lambda: crawl_hotels(
                destination, show_progress=False, user_data=user_data
            ),
        }
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_key = {executor.submit(fn): key for key, fn in tasks.items()}
            for future in as_completed(future_key):
                key = future_key[future]
                try:
                    results[key] = future.result()
                except Exception:
                    results[key] = []

    print()
    print("  " + "=" * 56)
    print("  ✓ 数据获取完成！")
    print("    景点: " + str(len(results.get("attractions", []))) + "处 | 餐厅: " +
          str(len(results.get("foods", []))) + "家 | 酒店: " +
          str(len(results.get("hotels", []))) + "家")
    print("  " + "=" * 56)
    print()

    results["departure_city"] = departure
    results["destination_city"] = destination
    results["use_amap"] = amap_on
    return results


# ============================================================
# 6. 携程风格 - 交通方案增强（智能排序）
# ============================================================
def sort_transport_options(options, budget=0, prefer_fast=True):
    """按照携程风格对交通方案排序"""
    if not options:
        return options

    def score(opt):
        try:
            price = float(opt.get("price", 500))
            hours = float(opt.get("duration_hours", 3))
            time_score = max(0, 100 - hours * 20)
            price_score = max(0, 100 - price / 20)
            if prefer_fast:
                return time_score * 0.6 + price_score * 0.4
            return price_score * 0.6 + time_score * 0.4
        except Exception:
            return 50

    sorted_opts = sorted(options, key=score, reverse=True)
    for i, opt in enumerate(sorted_opts):
        if i == 0:
            opt["recommended"] = True
            opt["tips"] = opt.get("tips", "") + " ★推荐"
    return sorted_opts


if __name__ == "__main__":
    status = get_api_status() if HAS_AMAP_API else {"amap_enabled": False}
    print("数据源状态:")
    print("  高德地图POI:", "✓ 已启用" if status.get("amap_enabled") else "✗ 未配置")
    print()
    print("开始测试北京数据...")
    result = crawl_all("北京", "长沙", show_progress=True)
    print()
    print("景点示例: " + str(len(result.get("attractions", []))) + "个")
    print("美食示例: " + str(len(result.get("foods", []))) + "个")
    print("酒店示例: " + str(len(result.get("hotels", []))) + "个")