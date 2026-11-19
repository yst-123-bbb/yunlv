# -*- coding: utf-8 -*-
"""云旅AI 数据迁移脚本：把 Python 兜底数据 -> Flutter 可用的 JSON 资源。

运行：python tools/migrate_data.py
输出：assets/data/*.json
"""
import importlib.util
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 云旅flutter+ai/
SRC = os.path.join(os.path.dirname(BASE), "云旅ai", "data")          # 源 Python 数据目录
OUT = os.path.join(BASE, "assets", "data")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_json(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print("  +", name, "(%d 项)" % (len(obj) if hasattr(obj, "__len__") else 0))


def main():
    attr = load_module("attraction", os.path.join(SRC, "attraction_data.py"))
    hotel = load_module("hotel", os.path.join(SRC, "hotel_data.py"))
    food = load_module("food", os.path.join(SRC, "food_data.py"))
    train = load_module("train", os.path.join(SRC, "train_data.py"))
    flight = load_module("flight", os.path.join(SRC, "flight_data.py"))

    # 1) 热门城市列表
    cities = [{"name": c, "tag": t, "spots": s}
              for c, t, s in attr.HOT_TOURIST_CITIES]
    write_json("cities.json", {"cities": cities})

    # 2) 景点 / 酒店 / 美食：真实数据优先，缺省城市用兜底函数补齐
    attractions = {c: attr.get_attraction_backup(c) for c, _, _ in attr.HOT_TOURIST_CITIES}
    hotels = {c: hotel.get_hotel_backup(c) for c, _, _ in attr.HOT_TOURIST_CITIES}
    foods = {c: food.get_food_backup(c) for c, _, _ in attr.HOT_TOURIST_CITIES}
    write_json("attractions.json", attractions)
    write_json("hotels.json", hotels)
    write_json("foods.json", foods)

    # 3) 交通：保留原始线路表 + 支撑数据，生成逻辑由 Dart 侧重写
    train_routes = {}
    for k, rows in train._PAIRS.items():
        train_routes[k] = [{
            "train_no": r[0], "dep_station": r[1], "arr_station": r[2],
            "dep_time": r[3], "arr_time": r[4], "duration": r[5],
            "second_seat": r[6], "first_seat": r[7],
        } for r in rows]

    airports = {}
    for c, _, _ in attr.HOT_TOURIST_CITIES:
        airports[c] = flight.get_city_airport(c)

    transit = {
        "train_routes": train_routes,
        "airlines": [{"code": a[0], "name": a[1], "group": a[2], "baggage": a[3]}
                     for a in flight._AIRLINES],
        "flight_routes": [{"departure": r[0], "destination": r[1], "duration": r[2],
                           "base_price": r[3], "hours": r[4], "minutes": r[5]}
                          for r in flight._TIMES],
        "airports": airports,
        "flight_time_slots": flight._TIME_SLOTS,
    }
    write_json("transit.json", transit)

    print("完成，输出目录：", OUT)


if __name__ == "__main__":
    main()
