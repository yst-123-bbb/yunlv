# -*- coding: utf-8 -*-
"""云旅AI模块验证测试 - 验证所有模块能否正常导入和运行"""
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
_BASE = os.path.dirname(os.path.abspath(__file__))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

print("=" * 60)
print("  云旅AI - 模块验证测试")
print("=" * 60)
print()

results = []

# 1. utils模块
try:
    from utils.helpers import cprint, title
    cprint("[✓] utils.helpers 导入成功", "OKGREEN")
    results.append(("utils", True))
except Exception as e:
    print("[✗] utils.helpers 失败: " + str(e))
    results.append(("utils", False))

# 2. data模块
try:
    from data.train_data import get_train_backup
    trains = get_train_backup("北京", "长沙")
    print("[✓] data.train_data 成功 高铁方案: " + str(len(trains)) + "个")
    results.append(("train_data", True))
except Exception as e:
    print("[✗] data.train_data 失败: " + str(e))
    results.append(("train_data", False))

try:
    from data.flight_data import get_flight_backup
    flights = get_flight_backup("北京", "长沙")
    print("[✓] data.flight_data 成功 航班方案: " + str(len(flights)) + "个")
    results.append(("flight_data", True))
except Exception as e:
    print("[✗] data.flight_data 失败: " + str(e))
    results.append(("flight_data", False))

try:
    from data.attraction_data import get_attraction_backup
    attrs = get_attraction_backup("长沙")
    print("[✓] data.attraction_data 成功 景点: " + str(len(attrs)) + "个")
    results.append(("attraction_data", True))
except Exception as e:
    print("[✗] data.attraction_data 失败: " + str(e))
    results.append(("attraction_data", False))

try:
    from data.food_data import get_food_backup
    foods = get_food_backup("长沙")
    print("[✓] data.food_data 成功 餐厅: " + str(len(foods)) + "家")
    results.append(("food_data", True))
except Exception as e:
    print("[✗] data.food_data 失败: " + str(e))
    results.append(("food_data", False))

try:
    from data.hotel_data import get_hotel_backup
    hotels = get_hotel_backup("长沙")
    print("[✓] data.hotel_data 成功 住宿: " + str(len(hotels)) + "家")
    results.append(("hotel_data", True))
except Exception as e:
    print("[✗] data.hotel_data 失败: " + str(e))
    results.append(("hotel_data", False))

# 3. API模块
try:
    from apis.geo_api import get_weather, parse_address
    w = get_weather("长沙", "2026-06-15")
    print("[✓] apis.geo_api 成功 天气: " + str(w.get("weather", "")) +
          " " + str(w.get("temp_low", "")) + "~" + str(w.get("temp_high", "")) + "°C")
    results.append(("geo_api", True))
except Exception as e:
    print("[✗] apis.geo_api 失败: " + str(e))
    import traceback
    traceback.print_exc()
    results.append(("geo_api", False))

# 4. 爬虫模块
try:
    from crawlers.spiders import crawl_train, crawl_flight, crawl_attractions, crawl_food, crawl_hotels
    t = crawl_train("北京", "长沙")
    f = crawl_flight("北京", "长沙")
    a = crawl_attractions("长沙")
    fd = crawl_food("长沙")
    hd = crawl_hotels("长沙")
    print("[✓] crawlers.spiders 全部数据采集成功")
    print("    高铁: " + str(len(t)) + "  航班: " + str(len(f)) +
          "  景点: " + str(len(a)) + "  美食: " + str(len(fd)) +
          "  住宿: " + str(len(hd)))
    results.append(("spiders", True))
except Exception as e:
    print("[✗] crawlers.spiders 失败: " + str(e))
    import traceback
    traceback.print_exc()
    results.append(("spiders", False))

# 5. 筛选模块
try:
    from core.filter import filter_all
    user_data = {
        "departure": "北京", "destination": "长沙",
        "dep_date": "2026-06-15", "return_date": "2026-06-18",
        "days": 3, "budget": 2500, "people": 2,
        "tastes": ["light", "local"],
        "attraction_prefs": ["culture", "internet", "nature"],
        "transport_pref": "both", "hotel_level": "mid",
        "hotel_location": "subway", "age_group": "friends",
    }
    trains2 = get_train_backup("北京", "长沙")
    flights2 = get_flight_backup("北京", "长沙")
    attrs2 = get_attraction_backup("长沙")
    foods2 = get_food_backup("长沙")
    hotels2 = get_hotel_backup("长沙")
    result = filter_all(trains2, flights2, attrs2, foods2, hotels2, user_data)
    print("[✓] core.filter 筛选成功")
    print("    高铁: " + str(len(result["trains"])) + "  航班: " + str(len(result["flights"])))
    print("    景点: " + str(len(result["attractions"])) + "  美食: " + str(len(result["foods"])))
    print("    住宿: " + str(len(result["hotels"])))
    results.append(("filter", True))
except Exception as e:
    print("[✗] core.filter 失败: " + str(e))
    import traceback
    traceback.print_exc()
    results.append(("filter", False))

# 6. 预算模块
try:
    from core.budget import calculate_budget, print_budget
    trans = {"price_per_person": 500}
    hd2 = hotels2[0] if hotels2 else {"price": 380}
    budget = calculate_budget(user_data, trans, result["attractions"], hd2, "mix")
    print("[✓] core.budget 预算核算成功")
    print("    总花费: " + str(int(budget["grand_total"])) + "元")
    print("    是否超支: " + str(budget["over_budget"]))
    results.append(("budget", True))
except Exception as e:
    print("[✗] core.budget 失败: " + str(e))
    import traceback
    traceback.print_exc()
    results.append(("budget", False))

print()
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
total = len(results)
print("  测试结果: " + str(passed) + "/" + str(total) + " 模块通过")
if passed == total:
    print("  ✓ 所有模块验证成功! 运行 'python main.py' 开始行程规划")
else:
    print("  ⚠ 有模块失败，请检查上述错误信息")
print("=" * 60)
print()
print("  完整运行命令:")
print("    python verify.py   # 验证测试")
print("    python main.py     # 完整交互式行程规划")
print()