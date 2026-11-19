# -*- coding: utf-8 -*-
"""兜底景点数据"""
# ============================================================
# 热门旅游城市列表（用户选择目的城市时提示）
# ============================================================

_ATTRACTION_DB = {
    "长沙": [
        {"name": "橘子洲", "address": "岳麓区橘子洲头", "ticket_price": 0,
         "open_time": "07:00-22:00", "tags": ["网红打卡", "自然风光"],
         "features": "湘江中心江心岛，青年毛泽东雕像，免费乘地铁直达",
         "tips": "傍晚去最美，有灯光音乐喷泉，可租自行车环岛",
         "indoor": False, "likes": 45200},
        {"name": "岳麓山+岳麓书院", "address": "岳麓区登高路", "ticket_price": 50,
         "open_time": "06:00-23:00", "tags": ["人文古迹", "自然风光"],
         "features": "千年学府岳麓书院+南岳衡山72峰之一，爱晚亭红叶",
         "tips": "书院单独门票50元，建议早上登山凉爽",
         "indoor": False, "likes": 38900},
        {"name": "湖南博物院", "address": "开福区东风路", "ticket_price": 0,
         "open_time": "09:00-17:00(周一闭馆)", "tags": ["人文古迹"],
         "features": "马王堆汉墓出土文物，辛追夫人遗体，国家一级博物馆",
         "tips": "需提前3天公众号预约免费，讲解器20元",
         "indoor": True, "likes": 29800},
        {"name": "IFS国金中心+黄兴路步行街", "address": "芙蓉区解放西路", "ticket_price": 0,
         "open_time": "全天", "tags": ["网红打卡"],
         "features": "长沙最繁华商圈，IFS楼顶kaws雕塑，小吃一条街",
         "tips": "晚上最热闹，排队拍照约20分钟",
         "indoor": True, "likes": 62300},
        {"name": "太平老街+坡子街", "address": "天心区", "ticket_price": 0,
         "open_time": "全天", "tags": ["网红打卡", "美食文化"],
         "features": "长沙老街区，贾谊故居，整条街都是臭豆腐和小吃",
         "tips": "晚上去最有氛围，一次性可吃多种小吃",
         "indoor": False, "likes": 41500},
        {"name": "湘江夜游", "address": "湘江沿岸码头", "ticket_price": 158,
         "open_time": "19:00-21:30", "tags": ["网红打卡"],
         "features": "乘船游湘江，两岸灯光秀，杜甫江阁夜景尽收眼底",
         "tips": "19:30班次日落夜景双重体验最佳",
         "indoor": False, "likes": 22100},
        {"name": "世界之窗", "address": "开福区三一大道", "ticket_price": 200,
         "open_time": "09:00-22:00", "tags": ["主题乐园"],
         "features": "仿世界名胜建筑+过山车等游乐设施",
         "tips": "建议一整天，节假日人多",
         "indoor": False, "likes": 25400},
    ],
    "北京": [
        {"name": "故宫博物院", "address": "东城区景山前街4号", "ticket_price": 60,
         "open_time": "08:30-17:00", "tags": ["人文古迹"],
         "features": "明清两代皇宫，世界文化遗产，馆藏186万件文物",
         "tips": "提前7天官网预约，午门进神武门出",
         "indoor": False, "likes": 185000},
        {"name": "八达岭长城", "address": "延庆区八达岭镇", "ticket_price": 40,
         "open_time": "07:30-17:30", "tags": ["人文古迹", "自然风光"],
         "features": "长城保存最完好一段，不到长城非好汉",
         "tips": "北京北站高铁约30分钟直达，缆车省力",
         "indoor": False, "likes": 142000},
        {"name": "天安门广场", "address": "东城区长安街", "ticket_price": 0,
         "open_time": "05:00-22:00", "tags": ["人文古迹", "网红打卡"],
         "features": "世界最大城市广场，可观看升旗仪式",
         "tips": "升旗需提前1天预约，安检禁带打火机",
         "indoor": False, "likes": 98000},
        {"name": "颐和园", "address": "海淀区新建宫门路", "ticket_price": 30,
         "open_time": "06:30-18:00", "tags": ["人文古迹", "自然风光"],
         "features": "皇家园林，昆明湖万寿山长廊彩绘，世界遗产",
         "tips": "建议游览3小时，联票60元含佛香阁",
         "indoor": False, "likes": 72000},
        {"name": "天坛公园", "address": "东城区天坛东路", "ticket_price": 15,
         "open_time": "06:00-22:00", "tags": ["人文古迹"],
         "features": "明清皇帝祭天场所，祈年殿回音壁设计精妙",
         "tips": "联票34元含祈年殿，早上当地人晨练很有味道",
         "indoor": False, "likes": 58000},
        {"name": "798艺术区", "address": "朝阳区酒仙桥路", "ticket_price": 0,
         "open_time": "10:00-18:00", "tags": ["网红打卡"],
         "features": "老工厂改造当代艺术区，画廊咖啡馆雕塑",
         "tips": "大多数画廊免费，适合文艺青年拍照",
         "indoor": True, "likes": 65000},
        {"name": "三里屯太古里", "address": "朝阳区工体北路", "ticket_price": 0,
         "open_time": "10:00-22:00", "tags": ["网红打卡", "购物"],
         "features": "北京最潮流商圈国际品牌酒吧街美食餐厅",
         "tips": "晚上最热闹，周边有很多优质餐厅",
         "indoor": True, "likes": 88000},
    ],
    "上海": [
        {"name": "外滩", "address": "黄浦区中山东一路", "ticket_price": 0,
         "open_time": "全天", "tags": ["网红打卡", "自然风光"],
         "features": "黄浦江畔万国建筑博览群，对岸陆家嘴天际线",
         "tips": "晚上灯光秀最美，可乘浦江游轮",
         "indoor": False, "likes": 156000},
        {"name": "南京路步行街", "address": "黄浦区南京东路", "ticket_price": 0,
         "open_time": "全天", "tags": ["购物", "美食文化"],
         "features": "中华商业第一街老字号林立",
         "tips": "步行到外滩，沿途有很多老字号美食",
         "indoor": False, "likes": 98000},
        {"name": "东方明珠", "address": "浦东新区世纪大道", "ticket_price": 180,
         "open_time": "08:30-21:30", "tags": ["网红打卡"],
         "features": "上海地标电视塔，可俯瞰黄浦江两岸",
         "tips": "建议傍晚去同时看日景和夜景",
         "indoor": True, "likes": 89000},
        {"name": "豫园城隍庙", "address": "黄浦区福佑路", "ticket_price": 40,
         "open_time": "09:00-16:30", "tags": ["人文古迹", "美食文化"],
         "features": "江南古典园林，老上海小吃聚集地",
         "tips": "南翔小笼包必吃，节假日人多",
         "indoor": False, "likes": 76000},
        {"name": "迪士尼乐园", "address": "浦东新区川沙新镇", "ticket_price": 475,
         "open_time": "08:30-20:30", "tags": ["主题乐园"],
         "features": "中国第一座迪士尼主题乐园",
         "tips": "建议两天，提前APP买快速通行证",
         "indoor": False, "likes": 128000},
        {"name": "田子坊", "address": "黄浦区泰康路", "ticket_price": 0,
         "open_time": "10:00-22:00", "tags": ["网红打卡"],
         "features": "上海老弄堂改造创意园区",
         "tips": "适合拍照逛街，有很多特色小店",
         "indoor": False, "likes": 65000},
    ],
}


def get_attraction_backup(city):
    if city in _ATTRACTION_DB:
        return list(_ATTRACTION_DB[city])
    generic = [
        {"name": city + "博物馆", "address": "市中心", "ticket_price": 0,
         "open_time": "09:00-17:00", "tags": ["人文古迹"],
         "features": "了解" + city + "历史文化",
         "tips": "周一闭馆，建议提前预约",
         "indoor": True, "likes": 20000},
        {"name": city + "步行街", "address": "市中心", "ticket_price": 0,
         "open_time": "全天", "tags": ["网红打卡", "购物"],
         "features": city + "最热闹商业街",
         "tips": "晚上人多注意保管财物",
         "indoor": False, "likes": 30000},
        {"name": city + "公园", "address": "市中心", "ticket_price": 0,
         "open_time": "06:00-22:00", "tags": ["自然风光"],
         "features": "市民休闲好去处",
         "tips": "免费开放，早晨空气好",
         "indoor": False, "likes": 15000},
        {"name": city + "古城景区", "address": "老城区", "ticket_price": 50,
         "open_time": "08:00-22:00", "tags": ["人文古迹", "网红打卡"],
         "features": "古建筑群感受历史韵味",
         "tips": "傍晚开灯后最美",
         "indoor": False, "likes": 25000},
    ]
    return generic
# 在文件末尾追加以下内容

# ============================================================
# 热门旅游城市列表
# ============================================================

HOT_TOURIST_CITIES = [
    ("北京", "历史文化首都", ["故宫", "长城", "天安门", "颐和园"]),
    ("上海", "国际化大都市", ["外滩", "东方明珠", "迪士尼", "南京路"]),
    ("广州", "岭南美食之都", ["长隆", "小蛮腰", "沙面"]),
    ("深圳", "年轻活力都市", ["世界之窗", "大梅沙", "欢乐谷"]),
    ("成都", "休闲美食天堂", ["宽窄巷子", "锦里", "大熊猫基地"]),
    ("长沙", "娱乐美食之都", ["橘子洲", "岳麓山", "火宫殿"]),
    ("杭州", "人间天堂西湖", ["西湖", "灵隐寺", "千岛湖"]),
    ("西安", "千年古都", ["兵马俑", "大雁塔", "华清池"]),
    ("三亚", "热带海岛度假", ["亚龙湾", "天涯海角", "蜈支洲岛"]),
    ("厦门", "文艺小清新海岛", ["鼓浪屿", "曾厝垵", "厦门大学"]),
    ("青岛", "海滨啤酒之城", ["栈桥", "八大关", "崂山"]),
    ("丽江", "慢生活古镇", ["丽江古城", "玉龙雪山", "束河古镇"]),
    ("大理", "风花雪月", ["洱海", "大理古城", "苍山"]),
    ("昆明", "春城花都", ["滇池", "石林", "翠湖"]),
    ("哈尔滨", "冰雪之都", ["中央大街", "冰雪大世界"]),
    ("重庆", "8D魔幻山城", ["洪崖洞", "解放碑", "磁器口"]),
    ("武汉", "江城美食之都", ["黄鹤楼", "东湖", "户部巷"]),
    ("南京", "六朝古都", ["中山陵", "夫子庙", "秦淮河"]),
    ("苏州", "江南园林水乡", ["拙政园", "虎丘", "周庄"]),
    ("桂林", "山水甲天下", ["漓江", "阳朔", "象鼻山"]),
]


def get_hot_cities():
    """获取热门旅游城市列表
    返回: [(城市名, 标签, 代表景点列表)
    """
    return HOT_TOURIST_CITIES


def get_hot_cities_simple():
    """获取简化版热门城市列表
    返回: [城市名列表]
    """
    return [c[0] for c in HOT_TOURIST_CITIES]


if __name__ == "__main__":
    print("热门旅游城市:")
    for city, tag, spots in HOT_TOURIST_CITIES:
        print("  " + city + " - " + tag)
        print("    代表景点: " + "、".join(spots[:3]))