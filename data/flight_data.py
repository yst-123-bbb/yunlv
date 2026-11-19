# -*- coding: utf-8 -*-
"""航班数据 - 参考携程/飞常准风格，包含: 航班号、航空公司、起降时间、多舱位价格、免费托运额度、准点率
"""

# 航空公司代码及服务等级说明
_AIRLINES = [
    ("CA", "国航", "星空联盟", "免费托运:手提7kg+托运30kg免费"),
    ("MU", "东航", "天合联盟", "免费托运:手提7kg+托运20kg免费"),
    ("CZ", "南航", "天合联盟", "免费托运:手提7kg+托运20kg免费"),
    ("HU", "海航", "非联盟", "免费托运:手提7kg+托运20kg免费"),
    ("3U", "川航", "非联盟", "免费托运:手提7kg+托运20kg免费"),
    ("ZH", "深航", "星空联盟", "免费托运:手提7kg+托运20kg免费"),
    ("FM", "上航", "星空联盟", "免费托运:手提7kg+托运20kg免费"),
    ("SC", "山航", "星空联盟", "免费托运:手提7kg+托运20kg免费"),
]

# 热门航线：(出发, 到达, 飞行时长文字, 经济舱基准价, 小时数, 分钟数)
_TIMES = [
    ("北京", "长沙", "2h30m", 980, 2, 30),
    ("北京", "上海", "2h10m", 780, 2, 10),
    ("北京", "广州", "3h10m", 1280, 3, 10),
    ("北京", "成都", "2h50m", 1180, 2, 50),
    ("北京", "杭州", "2h20m", 880, 2, 20),
    ("北京", "西安", "2h15m", 880, 2, 15),
    ("北京", "三亚", "4h00m", 1880, 4, 0),
    ("北京", "昆明", "3h40m", 1580, 3, 40),
    ("北京", "厦门", "2h50m", 1180, 2, 50),
    ("上海", "成都", "3h20m", 1080, 3, 20),
    ("上海", "广州", "2h45m", 980, 2, 45),
    ("上海", "长沙", "2h20m", 880, 2, 20),
    ("上海", "三亚", "3h30m", 1680, 3, 30),
    ("上海", "西安", "2h40m", 1080, 2, 40),
    ("广州", "成都", "2h30m", 980, 2, 30),
    ("广州", "杭州", "2h15m", 880, 2, 15),
    ("长沙", "北京", "2h30m", 980, 2, 30),
    ("长沙", "上海", "2h00m", 780, 2, 0),
    ("成都", "北京", "2h50m", 1180, 2, 50),
    ("成都", "广州", "2h30m", 980, 2, 30),
    ("西安", "北京", "2h15m", 880, 2, 15),
    ("三亚", "北京", "4h00m", 1880, 4, 0),
    ("长沙", "广州", "1h20m", 480, 1, 20),
]

_TIME_SLOTS = ["06:30", "08:00", "09:30", "11:00", "13:00", "14:30", "16:00", "17:30", "19:00", "21:00"]


def _add_hours(time_str, hours, minutes):
    try:
        parts = time_str.split(":")
        h = int(parts[0]) + hours
        m = int(parts[1]) + minutes
        h += m // 60
        m = m % 60
        h = h % 24
        return str(h).zfill(2) + ":" + str(m).zfill(2)
    except Exception:
        return time_str


def get_city_airport(city):
    """城市->机场名称"""
    mapping = {
        "北京": "首都T3",
        "上海": "虹桥T2",
        "广州": "白云T2",
        "深圳": "宝安T3",
        "成都": "双流T2",
        "杭州": "萧山T3",
        "长沙": "黄花T2",
        "西安": "咸阳T3",
        "昆明": "长水T2",
        "三亚": "凤凰T2",
        "厦门": "高崎T3",
        "青岛": "流亭T2",
        "武汉": "天河T3",
        "重庆": "江北T3",
        "哈尔滨": "太平T2",
    }
    return mapping.get(city, city + "机场")


def get_flight_backup(departure, destination):
    """生成航班方案 - 参考12306/携程风格

    返回: 航班列表，每航班含:
    flight_no, airline, airline_group, dep_airport, arr_airport,
    dep_time, arr_time, duration, punctuality,
    cabin(经济舱/明珠经济舱/商务舱/头等舱),
    free_baggage(免费托运额度说明), airline_full(完整航空公司全称)
    """
    matched = None
    for row in _TIMES:
        if (row[0] == departure and row[1] == destination) or \
           (row[0] == destination and row[1] == departure):
            matched = row
            break

    if matched:
        dur, base_price, h, m = matched[2], matched[3], matched[4], matched[5]
    else:
        dur, base_price, h, m = "2h30m", 880, 2, 30

    dep_ap = get_city_airport(departure)
    arr_ap = get_city_airport(destination)

    flights = []
    for i, t in enumerate(_TIME_SLOTS):
        code, airline_short, group, bag_info = _AIRLINES[i % len(_AIRLINES)]
        fno = code + str(1000 + i * 137)
        arr_time = _add_hours(t, h, m)
        price_economy = base_price + i * 50 - 80
        price_economy = max(price_economy, 400)
        flights.append({
            "flight_no": fno,
            "airline": airline_short,
            "airline_full": airline_short + "(" + code + ")",
            "airline_group": group,
            "dep_airport": dep_ap,
            "arr_airport": arr_ap,
            "dep_time": t,
            "arr_time": arr_time,
            "duration": dur,
            "cabin": {
                "经济舱": price_economy,
                "超级经济舱": int(price_economy * 1.5),
                "商务舱": int(price_economy * 3),
                "头等舱": int(price_economy * 5),
            },
            "luggage": bag_info,  # 免费托运额度
            "free_baggage": bag_info,  # 兼容字段
            "punctuality": str(80 + (i * 3) % 15) + "%",
            "on_time_rate": 80 + (i * 3) % 15,
            "meal": "提供餐食",
            "aircraft": "空客A320/波音737",
        })

    if flights:
        flights[0]["_tag"] = "推荐"
        if len(flights) >= 3:
            lowest_idx = min(range(len(flights)), key=lambda x: flights[x]["cabin"]["经济舱"])
            if isinstance(lowest_idx, tuple):
                lowest_idx = lowest_idx[0]
            if lowest_idx != 0:
                flights[lowest_idx]["_tag"] = "价格最低"
        if len(flights) >= 5:
            flights[2]["_tag"] = flights[2].get("_tag", "时间最好")
    return flights


if __name__ == "__main__":
    result = get_flight_backup("北京", "长沙")
    for f in result[:3]:
        print(f["flight_no"], f["airline"], f["dep_time"], "->", f["arr_time"], f["cabin"])