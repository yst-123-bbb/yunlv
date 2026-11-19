# -*- coding: utf-8 -*-
"""云旅AI - 命令行薄壳

只负责两件事：采集用户输入（含 Kimi 自然语言解析）与展示编排结果。
六步编排、交通筛选、行程校验与预算核算都在 services.plan_service 中完成。
"""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
_BASE = os.path.dirname(os.path.abspath(__file__))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from datetime import datetime, timedelta

from utils.helpers import cprint, title
from services import plan_service

# Kimi AI 规划器（仅用于输入解析）
try:
    from apis.kimi_api import KimiClient
    from config import KIMI_ENABLED
    _kc = KimiClient()
    KIMI_AVAILABLE = bool(KIMI_ENABLED) and _kc.available()
except Exception:
    _kc = None
    KIMI_AVAILABLE = False

# 尝试导入高德地图 API 状态
try:
    from apis.geo_api import get_api_status
    HAS_API_STATUS = True
except Exception:
    HAS_API_STATUS = False

    def get_api_status():
        return {"amap_enabled": False, "requests": False}


def _banner():
    print()
    cprint("═══════════════════════════════════════════════════════", "OKGREEN")
    cprint("     ✈  云旅AI · 一站式智能旅行规划系统 (升级版)     ", "OKGREEN")
    cprint("  多方案生成 | 景点推荐 | 美食精选 | 住宿攻略 | 预算核算 ", "OKGREEN")
    cprint("═══════════════════════════════════════════════════════", "OKGREEN")
    cprint("  📅 " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "  开启您的完美旅程", "OKCYAN")
    print()


def _show_api_status():
    """显示当前数据来源状态"""
    status = get_api_status() if HAS_API_STATUS else {}
    amap_on = status.get("amap_enabled", False)
    cprint("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "OKCYAN")
    cprint("  【数据源状态】", "HEADER")
    if amap_on:
        cprint("    ✓ 高德地图API: 已连接 (景点/美食/酒店实时POI搜索)", "OKGREEN")
    else:
        cprint("    ○ 高德地图API: 未配置 (使用本地精选数据)", "WARNING")
    if KIMI_AVAILABLE:
        cprint("    ✓ Kimi AI: 已启用 (自然语言智能行程规划)", "OKGREEN")
    else:
        cprint("    ○ Kimi AI: 未启用 (在 .env 填入 KIMI_API_KEY 即可开启)", "WARNING")
    cprint("    ✓ 多方案生成器: 已启用 (本地规则引擎降级)", "OKGREEN")
    cprint("    ○ 12306高铁: 本地精选方案", "OKBLUE")
    cprint("    ○ 携程航班: 本地精选方案", "OKBLUE")
    cprint("    ○ 天气数据: " + ("高德实时" if amap_on else "本地模拟"), "OKBLUE")
    if not amap_on:
        cprint("  提示: 在 .env 填入 AMAP_KEY 即可启用真实POI搜索", "WARNING")
        cprint("        申请地址: https://lbs.amap.com/", "WARNING")
    cprint("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "OKCYAN")
    print()


def _kimi_parse_user_input(raw_text):
    """让 Kimi 把用户的自然语言需求解析成结构化 user_data dict"""
    if not KIMI_AVAILABLE or not _kc:
        return None

    prompt = """请把用户的旅行需求解析成严格的 JSON 格式。不要输出任何解释文字，只输出 JSON。

用户输入: """ + raw_text.replace("{", "{{").replace("}", "}}") + """

输出格式（字段全部必填）:
{
  "departure": "出发城市名，如北京",
  "cities": [{"city": "目的地城市名", "days": 整数天数}],
  "days": 总天数（整数）,
  "people": 出行人数（整数）,
  "dep_date": "出发日期 YYYY-MM-DD 格式（如果用户没说，默认2026-07-01）",
  "age_group": "年轻人/老人/小孩/家庭/商务（用户没说则默认年轻人）",
  "tastes": ["美食偏好", "如川菜", "素食"],
  "hotel_level": "经济/舒适/高档（用户没说则默认舒适）",
  "transport_pref": "高铁/飞机/都可以（用户没说则默认高铁）",
  "budget": 人均总预算（整数，单位元，用户没说则给一个合理估算）
}

重要提示:
- 单城市时 cities 只含一个元素
- "大理3天昆明2天" 应解析为 [{"city":"大理","days":3}, {"city":"昆明","days":2}]
- days = 所有 cities 的 days 之和
- budget 如用户没说，根据目的地给一个合理估算（如大理3000、成都2500）
- 输出必须是合法 JSON，可以被 json.loads() 直接解析
- 不要输出 ```json 或其他标记，只输出纯 JSON 文本"""

    result = _kc.ask(prompt)
    if not result:
        return None

    text = result.strip()
    first = text.find("{")
    last = text.rfind("}")
    json_str = text[first:last + 1] if first >= 0 and last > first else text

    try:
        import json

        data = json.loads(json_str)
        if "departure" in data and "cities" in data and "budget" in data:
            data["destination"] = data["cities"][0]["city"] if data["cities"] else data.get("departure", "")
            data["is_multi_city"] = len(data.get("cities", [])) > 1
            if "days" not in data or not data["days"]:
                data["days"] = sum(c.get("days", 0) for c in data.get("cities", []))
            return data
    except Exception:
        pass
    return None


# ========== 输入采集: 用户基础信息（支持单/多城市 + Kimi 智能解析） ==========
def collect_user_info():
    title("【步骤1/6】基础信息录入", level=1)

    # ---- 🤖 Kimi 智能输入模式 ----
    if KIMI_AVAILABLE:
        cprint("  🤖 Kimi AI 已启用，您可以选择以下输入方式:", "OKCYAN")
        cprint("    1. 逐步输入（一步步填，适合详细配置）", "OKCYAN")
        cprint("    2. 一句话描述（Kimi 智能解析，如: 从北京去大理3天昆明2天 2人 预算3000）", "OKCYAN")
        mode = input("    选择 [默认1逐步输入]: ").strip() or "1"
        print()

        if mode == "2":
            cprint("  💡 示例: 我想从上海去成都玩4天 1个人 预算2500 喜欢美食", "OKBLUE")
            raw = input("  请描述您的旅行需求: ").strip()
            print()
            if raw:
                parsed = _kimi_parse_user_input(raw)
                if parsed:
                    cprint("  ✓ Kimi 已为您解析:", "OKGREEN")
                    cprint("    出发城市: " + str(parsed.get("departure", "")), "OKCYAN")
                    cities = parsed.get("cities", [])
                    if cities:
                        cprint("    目的地: " + " → ".join(c["city"] + str(c["days"]) + "天" for c in cities), "OKCYAN")
                    cprint("    出行人数: " + str(parsed.get("people", "")), "OKCYAN")
                    cprint("    人均预算: " + str(parsed.get("budget", "")) + "元", "OKCYAN")
                    cprint("    出发日期: " + str(parsed.get("dep_date", "")), "OKCYAN")
                    print()
                    confirm = input("  确认使用此配置？(y/n) [默认y]: ").strip().lower() or "y"
                    if confirm == "y":
                        return parsed
                cprint("  ⚠ 解析失败，切换到逐步输入模式", "WARNING")
                print()

    # ---- 逐步输入模式 ----
    dep = input("  ① 出发城市 [默认北京]: ").strip() or "北京"
    print()

    # ---- ② 单城市/多城市选择 ----
    title("② 选择目的地模式", level=2)
    cprint("  1. 单城市（推荐: 只去一个城市）", "OKCYAN")
    cprint("  2. 多城市（如: 大理3天→昆明2天, 杭州2天→上海1天→苏州2天）", "OKCYAN")
    mode = input("  选择 [默认1单城市]: ").strip() or "1"
    is_multi = mode == "2"

    cities = []  # [{"city": "大理", "days": 3}, ...]

    if is_multi:
        title("②-a 多城市输入", level=2)
        cprint("  💡 格式: 城市天数,城市天数  例如: 大理3天,昆明2天  或  杭州2天,上海1天,苏州2天", "OKCYAN")
        cprint("  💡 每个城市名+天数，英文逗号分隔", "OKCYAN")
        raw = input("  输入城市计划: ").strip()

        # 解析输入，容忍多种格式
        parsed = []
        for part in raw.replace("，", ",").split(","):
            part = part.strip()
            if not part:
                continue
            # 支持 "大理3天" "大理3日" "大理 3天" "大理3"
            if part and part[-1] in "天日":
                part = part[:-1].strip()
            j = len(part) - 1
            num_str = ""
            while j >= 0 and part[j].isdigit():
                num_str = part[j] + num_str
                j -= 1
            city_name = part[:j + 1].strip()
            if city_name and num_str:
                parsed.append({"city": city_name, "days": int(num_str)})

        if not parsed:
            cprint("  ⚠ 未识别到有效城市，使用默认: 大理3天,昆明2天", "WARNING")
            parsed = [{"city": "大理", "days": 3}, {"city": "昆明", "days": 2}]

        cities = parsed
        total_days = sum(c["days"] for c in cities)
        dest = cities[0]["city"]
        cprint("  ✓ 已识别: " + " → ".join(c["city"] + str(c["days"]) + "天" for c in cities),
               "OKGREEN")
        cprint("  共 " + str(total_days) + " 天", "OKGREEN")
    else:
        # ---- 单城市 ----
        title("② 选择目的城市", level=2)
        try:
            from data.attraction_data import get_hot_cities

            hot_cities = get_hot_cities()
            cprint("  🔥 热门旅游城市推荐:", "OKCYAN")
            for i, (city, tag, spots) in enumerate(hot_cities, 1):
                print("  " + str(i) + ". " + city + " - " + tag + " (" + "、".join(spots[:2]) + ")")
            print("  0. 手动输入其他城市")
            dest_input = input("  选择序号或输入城市名 [默认2长沙]: ").strip() or "2"
            if dest_input == "0":
                dest = input("  请输入目的城市: ").strip() or "长沙"
            elif dest_input.isdigit():
                idx = int(dest_input) - 1
                dest = hot_cities[idx][0] if 0 <= idx < len(hot_cities) else "长沙"
            else:
                dest = dest_input
        except Exception:
            dest = input("  ② 目的城市 [默认长沙]: ").strip() or "长沙"

        while dest == dep:
            cprint("  目的城市不能与出发城市相同", "WARNING")
            dest = input("  ② 目的城市: ").strip()

        # 单城市下，总天数在后面问
        cities = []
        total_days = None

    print()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    dep_date = input("  ③ 出发日期 YYYY-MM-DD [默认" + tomorrow + "]: ").strip() or tomorrow
    print()

    # 天数: 多城市时用已输入的总天数，单城市时询问
    if is_multi:
        days = total_days
        cprint("  ④ 游玩天数: " + str(days) + "天（根据城市计划自动计算）", "OKCYAN")
    else:
        days_raw = input("  ④ 游玩天数 [默认3天]: ").strip() or "3"
        try:
            days = int(days_raw)
            if days < 1:
                days = 1
            if days > 30:
                days = 30
        except Exception:
            days = 3
        cities = [{"city": dest, "days": days}]
    print()

    people_raw = input("  ⑤ 出行人数 [默认2人]: ").strip() or "2"
    try:
        people = int(people_raw)
        if people < 1:
            people = 1
    except Exception:
        people = 2

    print()
    title("⑥ 出行人群特征 (选择序号)", level=2)
    age_opts = [
        ("youth", "年轻人/学生党 - 活力打卡网红地"),
        ("couple", "情侣/蜜月 - 浪漫温馨"),
        ("family", "亲子家庭 - 老人小孩需轻松"),
        ("senior", "中老年群体 - 节奏慢养生"),
        ("business", "商务出行 - 便捷高效"),
        ("friends", "朋友结伴 - 吃喝玩乐自由随性"),
    ]
    for i, (_, desc) in enumerate(age_opts, 1):
        print("  " + str(i) + ". " + desc)
    age_idx = input("  选择 [默认6朋友结伴]: ").strip() or "6"
    try:
        idx = int(age_idx) - 1
        age_group = age_opts[idx][0] if 0 <= idx < len(age_opts) else "friends"
    except Exception:
        age_group = "friends"

    print()
    title("⑦ 饮食口味偏好", level=2)
    taste_opts = [
        ("light", "清淡不辣 - 粤菜江浙菜西餐"),
        ("mild", "微辣可接受 - 一般湘菜"),
        ("spicy", "重辣爱好者 - 地道川湘火锅"),
        ("seafood", "海鲜/日料刺身"),
        ("local", "当地小吃/夜市文化"),
    ]
    for i, (_, desc) in enumerate(taste_opts, 1):
        print("  " + str(i) + ". " + desc)
    print("  0. 全部接受（默认推荐，系统自动匹配）")
    taste_input = input("  选择，逗号分隔多选，如 1,3,5 [默认0全部]: ").strip() or "0"
    try:
        if taste_input == "0":
            tastes = [t[0] for t in taste_opts]
        elif "," in taste_input:
            tastes = []
            for part in taste_input.split(","):
                part = part.strip()
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(taste_opts):
                        tastes.append(taste_opts[idx][0])
            if not tastes:
                tastes = [t[0] for t in taste_opts]
        elif taste_input.isdigit():
            idx = int(taste_input) - 1
            tastes = [taste_opts[idx][0]] if 0 <= idx < len(taste_opts) else [t[0] for t in taste_opts]
        else:
            tastes = [t[0] for t in taste_opts]
    except Exception:
        tastes = [t[0] for t in taste_opts]

    print()
    title("⑧ 住宿价位倾向", level=2)
    hotel_opts = [
        ("budget", "经济型 - <300元/晚 干净够用"),
        ("mid", "中端舒适 - 300-600元/晚 品质保障"),
        ("high", "高端豪华 - >600元/晚 尊享体验"),
    ]
    for i, (_, desc) in enumerate(hotel_opts, 1):
        print("  " + str(i) + ". " + desc)
    hotel_input = input("  选择 [默认2中端舒适]: ").strip() or "2"
    try:
        h_idx = int(hotel_input) - 1
        hotel_level = hotel_opts[h_idx][0] if 0 <= h_idx < len(hotel_opts) else "mid"
    except Exception:
        hotel_level = "mid"

    print()
    title("⑨ 往返交通方式倾向", level=2)
    trans_opts = [
        ("flight", "优先飞机省时 - 推荐"),
        ("both", "两者均可看性价比"),
        ("train", "优先高铁动车"),
    ]
    for i, (_, desc) in enumerate(trans_opts, 1):
        print("  " + str(i) + ". " + desc)
    trans_input = input("  选择 [默认1优先飞机省时]: ").strip() or "1"
    try:
        t_idx = int(trans_input) - 1
        transport_pref = trans_opts[t_idx][0] if 0 <= t_idx < len(trans_opts) else "flight"
    except Exception:
        transport_pref = "flight"

    print()
    default_budget = "3500" if is_multi and days >= 5 else "2500"
    budget_raw = input("  ⑩ 人均总预算(元) [默认" + default_budget + "]: ").strip() or default_budget
    try:
        budget = float(budget_raw)
        if budget < 500:
            budget = 500
    except Exception:
        budget = 2500

    try:
        ret_date = (datetime.strptime(dep_date, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
    except ValueError:
        ret_date = dep_date

    user_data = {
        "departure": dep,
        "destination": dest,            # 兼容字段（首个城市）
        "cities": cities,               # 完整城市计划
        "is_multi_city": is_multi,
        "dep_date": dep_date,
        "return_date": ret_date,
        "days": days,
        "people": people,
        "age_group": age_group,
        "tastes": tastes,
        "attraction_prefs": ["culture", "nature", "internet", "food_tour"],
        "transport_pref": transport_pref,
        "hotel_level": hotel_level,
        "hotel_location": "subway",
        "budget": budget,
    }

    print()
    city_str = (" → ".join(c["city"] + str(c["days"]) + "天" for c in cities)) if is_multi else (dep + " → " + dest)
    cprint("  ✓ 信息已确认: " + city_str + " 共" + str(days) +
           "天 " + str(people) + "人 人均" + str(int(budget)) + "元", "OKGREEN")
    if KIMI_AVAILABLE:
        cprint("  🤖 Kimi AI 已启用，将为您生成智能行程方案", "OKCYAN")
    print()
    return user_data


# ========== 结果展示 ==========
def _transport_code(option, mode):
    if mode == "flight":
        return str(option.get("flight_no") or "航班")
    return str(option.get("train_no") or "车次")


def display_transport(session):
    title("【步骤2/6】往返交通方案", level=1)
    transport = session.transport or {}
    if not transport:
        cprint("  ○ 未获取到交通方案", "WARNING")
        print()
        return

    mode = str(transport.get("outbound_type") or transport.get("mode") or "flight")
    label = "✈航班" if mode == "flight" else "🚄高铁"
    outbound = transport.get("outbound") or {}
    inbound = transport.get("return") or {}

    cprint("  ✓ 已为您选定往返交通", "OKGREEN")
    print("  去程: " + label + " " + _transport_code(outbound, mode) +
          "  约" + str(int(float(transport.get("outbound_price") or 0))) + "元/人")
    print("  返程: " + label + " " + _transport_code(inbound, mode) +
          "  约" + str(int(float(transport.get("return_price") or 0))) + "元/人")
    print("  交通总花费(往返): " + str(int(float(transport.get("total") or 0))) + "元 (" +
          str(int(session.user_data.get("people") or 1)) + "人)")
    print()


def display_plans(session):
    title("【步骤3-4/6】行程方案", level=1)
    plans = session.plans or []
    cprint("  共生成 " + str(len(plans)) + " 个方案", "OKCYAN")
    for i, plan in enumerate(plans, 1):
        style = plan.get("style") or {}
        city_tag = (str(plan.get("_city") or "") + "·") if plan.get("_city") else ""
        print("  【方案" + str(i) + "】 " + str(style.get("emoji", "📌")) + " " + city_tag +
              str(style.get("name", "方案")) + "  综合评分:" + str(plan.get("score", 80)) + "分")
        print("    景点 " + str(len(plan.get("attractions") or [])) + "处 | 餐厅 " +
              str(len(plan.get("restaurants") or [])) + "家")

    chosen = session.chosen_plan or {}
    style = chosen.get("style") or {}
    cprint("  ✓ 已选定: " + str(style.get("emoji", "")) + " " + str(style.get("name", "方案")), "OKGREEN")
    print()


def display_itinerary(session):
    title("【步骤5/6】每日行程安排", level=1)
    itinerary = session.itinerary or []
    if not itinerary:
        cprint("  ○ 暂无行程安排", "WARNING")
        print()
        return

    for entry in itinerary:
        cprint("  第" + str(entry.get("day")) + "天 · " + str(entry.get("date")), "OKGREEN")
        cprint("  " + "─" * 52, "OKCYAN")
        items = entry.get("items") or []
        if not items:
            print("  （自由活动）")
        for item in items:
            print("  " + str(item.get("start", "")) + "-" + str(item.get("end", "")) +
                  " 【" + str(item.get("name", "")) + "】")
        print()


def display_budget(session):
    title("【步骤6/6】预算明细", level=1)
    budget = session.budget or {}
    if not budget:
        cprint("  ○ 暂无预算数据", "WARNING")
        print()
        return

    people = int(session.user_data.get("people") or 1)
    total_budget = float(session.user_data.get("budget") or 0) * people
    rows = [
        ("1. 交通费(往返)", "transport"),
        ("2. 市内交通", "city_transport"),
        ("3. 景点门票", "tickets"),
        ("4. 餐饮费", "food"),
        ("5. 住宿费", "hotel"),
        ("6. 购物", "shopping"),
        ("7. 备用金(10%)", "reserve"),
    ]
    print("  " + "=" * 52)
    if total_budget:
        cprint("  总预算(" + str(people) + "人 × " + str(int(total_budget / people)) +
               "元): " + str(int(total_budget)) + "元", "OKCYAN")
    for label, key in rows:
        print("  " + label + ": " + str(int(float(budget.get(key) or 0))) + "元")
    print("  " + "-" * 52)

    grand_total = float(budget.get("grand_total") or 0)
    cprint("  预计总花费: " + str(int(grand_total)) + "元", "OKGREEN")
    print("  人均花费: " + str(int(float(budget.get("per_person") or 0))) + "元")
    print("  " + "=" * 52)
    print()

    if total_budget:
        diff = grand_total - total_budget
        if diff > 0:
            cprint("  ⚠ 超出预算 " + str(int(diff)) + "元 (人均超" + str(int(diff / people)) + "元)", "WARNING")
            cprint("  💡 可参考: 交通选更低价车次 / 住宿降级 / 多选当地小吃 / 优先免费景点", "OKCYAN")
        else:
            cprint("  ✓ 预算内! 结余 " + str(int(-diff)) + "元 可升级住宿/增加项目", "OKGREEN")
        print()


def display_summary(session):
    user_data = session.user_data
    budget = session.budget or {}
    chosen = session.chosen_plan or {}

    print()
    cprint("═" * 60, "OKGREEN")
    if user_data.get("is_multi_city") and user_data.get("cities"):
        dest_desc = " → ".join(str(c["city"]) for c in user_data["cities"])
    else:
        dest_desc = str(user_data.get("destination") or "")
    cprint("  🎉 云旅AI 已为您完成 " + dest_desc + " " + str(user_data.get("days")) + "日游完整规划", "OKGREEN")
    cprint("═" * 60, "OKGREEN")
    print()

    style = chosen.get("style") or {}
    if style.get("name"):
        cprint("  📌 方案风格: " + str(style.get("emoji", "")) + " " + str(style.get("name")), "OKCYAN")
    cprint("  📍 " + str(user_data.get("departure") or "") + " → " + dest_desc, "OKCYAN")
    cprint("  📅 " + str(user_data.get("dep_date") or "") + " 至 " +
           str(user_data.get("return_date") or "") + " (" + str(user_data.get("days")) + "天)", "OKCYAN")
    cprint("  👥 " + str(user_data.get("people")) + "人 | " +
           str(len(chosen.get("attractions") or [])) + "个景点", "OKCYAN")
    cprint("  💰 预计总花费: " + str(int(float(budget.get("grand_total") or 0))) +
           "元 (人均" + str(int(float(budget.get("per_person") or 0))) + "元)", "OKGREEN")
    print()
    cprint("  💡 出行前请确认票务/天气 祝您旅途愉快!", "OKCYAN")
    print()


# ========== 主程序 ==========
def main():
    _banner()
    _show_api_status()
    try:
        user_data = collect_user_info()
        session = plan_service.run_all(user_data)

        display_transport(session)
        display_plans(session)
        display_itinerary(session)
        display_budget(session)
        display_summary(session)

        try:
            input("  按回车键退出...")
        except Exception:
            pass
    except KeyboardInterrupt:
        cprint("\n\n  已取消 再见!", "WARNING")
        sys.exit(0)
    except Exception as e:
        cprint("\n  ❌ 系统异常: " + str(e), "FAIL")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()