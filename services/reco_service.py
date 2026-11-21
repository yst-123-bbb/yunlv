"""小红书攻略文案与站内搜索直链。

只生成攻略文案与搜索链接，不抓取、不镜像、不缓存小红书笔记内容。
有 AI 配置时用 AI 写结构化长攻略，外呼失败或返回空文本时静默回落本地模板。
未收录的景点/城市也给一份通用攻略，避免直接 404。
"""

from __future__ import annotations

import urllib.parse

import httpx

from data.place_catalog import ATTRACTIONS, CITIES
from services.ai_config import AiConfig
from settings import settings

_SEARCH_URL_PREFIX = "https://www.xiaohongshu.com/search_result?keyword="
_SYSTEM_PROMPT = (
    "你是资深旅行攻略编辑，用简体中文写一份 800–1500 字的攻略，纯文本输出，"
    "不要 Markdown 标记，不要 emoji 堆砌。"
    "必须严格按以下八个板块顺序输出，每个板块标题用【】包裹并独占一行："
    "【怎么去】【门票与开放时间】【必看亮点】【建议路线与时长】"
    "【值与不值】【避坑提醒】【拍照机位】【周边美食】。"
    "硬性要求：不确定的价格、排队时长、营业时间一律写成「以官方公告为准」，"
    "禁止编造精确票价、排队时长和营业时间。"
)
_BLURB_LIMIT = 2000
_MAX_TOKENS = 2000
_UNKNOWN = "以官方公告为准"


def build_search_url(keyword: str) -> str:
    return _SEARCH_URL_PREFIX + urllib.parse.quote(keyword)


def _clamp_blurb(text: str) -> str:
    text = text.strip()
    return text if len(text) <= _BLURB_LIMIT else text[: _BLURB_LIMIT - 1] + "…"


def _find_attraction(name: str) -> tuple[str, dict] | None:
    key = (name or "").strip().casefold()
    if not key:
        return None
    for city_name, items in ATTRACTIONS.items():
        for item in items:
            if item["name"].casefold() == key:
                return city_name, item
    return None


def _find_city(name: str) -> dict | None:
    key = (name or "").strip().casefold()
    if not key:
        return None
    for city in CITIES:
        if city["name"].casefold() == key:
            return city
    return None


def _field(value: object, fallback: str = "未收录") -> str:
    text = str(value or "").strip()
    return text or fallback


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return text if text[-1] in "。！？；" else text + "。"


def _ticket_text(item: dict) -> str:
    price = item.get("ticket_price")
    if isinstance(price, (int, float)) and not isinstance(price, bool):
        return f"{int(price)} 元" if price > 0 else "免费"
    return _UNKNOWN


def _top_features(item: dict) -> str:
    segments = [part.strip() for part in str(item.get("features") or "").split("，")]
    return "，".join([part for part in segments if part][:2])


def _local_attraction_blurb(city: str, item: dict) -> str:
    name = item["name"]
    address = str(item.get("address") or "").strip()
    open_time = _field(item.get("open_time"))
    features = _top_features(item)
    tips = _sentence(str(item.get("tips") or ""))
    scene = "室内景点，雨天也能安排" if item.get("indoor") else "室外景点，建议看好天气"
    how = (
        f"{name}位于{address}，可优先考虑地铁或公交前往，自驾请提前确认周边停车位；具体线路以官方出行 App 为准。"
        if address
        else f"本站暂未收录{name}的详细地址，出发前请用地图 App 确认最近的地铁站或公交线路，再安排出发时间。"
    )
    if features and city:
        highlight = f"{name}是{city}的代表性景点，{features}。"
    elif features:
        highlight = f"{name}的看点：{features}。"
    else:
        highlight = f"本站还没有{name}的详细看点整理，可参考官方介绍与近期游记。"
    return "\n".join(
        [
            f"【怎么去】{how}",
            f"【门票与开放时间】门票{_ticket_text(item)}，开放时间 {open_time}，{scene}。"
            "旺季与节假日的具体安排以官方公告为准，需要预约的建议提前在官方渠道确认。",
            f"【必看亮点】{highlight}",
            f"【避坑提醒】{tips}热门时段人流集中，建议错峰前往；"
            f"最新的排队时长与拍照机位可以到小红书搜「{name} 攻略」查看。",
        ]
    )


def _local_city_blurb(city: dict) -> str:
    name = city["name"]
    province = str(city.get("province") or "").strip()
    tag = str(city.get("tag") or "").strip()
    spots = [str(spot) for spot in (city.get("spots") or []) if str(spot).strip()]
    spot_text = "、".join(spots[:3]) if spots else "多处热门去处"
    how = (
        f"{name}位于{province}，可先飞抵或乘高铁到达，再换乘地铁、公交或城际交通进入市区；"
        if province
        else f"前往{name}可先飞抵或乘高铁到达，再换乘地铁、公交或城际交通进入市区；"
    )
    highlight = f"{spot_text} 是{name}的代表性去处，" + (
        f"{tag}是它的招牌体验，" if tag else ""
    ) + f"建议留出 {max(2, len(spots))} 天慢慢逛。"
    return "\n".join(
        [
            f"【怎么去】{how}具体线路以官方出行 App 为准。",
            f"【门票与开放时间】{name}各景点的门票与开放时间差异较大，热门场馆通常需要提前预约，"
            "具体票价与开放时间以官方公告为准。",
            f"【必看亮点】{highlight}",
            f"【避坑提醒】节假日人流集中在热门景点，建议错峰出行并提前订好酒店与城际交通；"
            f"最新的排队时长、拍照机位与周边美食可以到小红书搜「{name} 攻略」查看。",
        ]
    )


def _attraction_prompt(city: str, item: dict) -> str:
    tags = "、".join(str(tag) for tag in (item.get("tags") or []))
    return (
        "请为下面这个景点写一份完整的出行攻略。\n"
        f"名称：{item['name']}\n"
        f"所在城市：{_field(city)}\n"
        f"地址：{_field(item.get('address'))}\n"
        f"参考票价：{_ticket_text(item)}\n"
        f"开放时间：{_field(item.get('open_time'))}\n"
        f"类型标签：{_field(tags)}\n"
        f"特色：{_field(item.get('features'))}\n"
        f"实用提示：{_field(item.get('tips'))}\n"
        "以上字段是已知信息，可以直接引用；没有给出的信息不要猜测，统一写成「以官方公告为准」。"
    )


def _unknown_attraction_prompt(name: str) -> str:
    return (
        f"请为「{name}」写一份通用出行攻略。\n"
        "本站没有收录它的地址、票价、开放时间等数据，这些一律不要编造，统一写成「以官方公告为准」；"
        "其余板块给出通用的交通、路线、拍照与周边美食建议，并提醒读者以官方公告和当地实际情况为准。"
    )


def _city_prompt(city: dict) -> str:
    spots = "、".join(str(spot) for spot in (city.get("spots") or []))
    return (
        "请为下面这个城市写一份完整的出行攻略。\n"
        f"城市：{city['name']}\n"
        f"省份：{_field(city.get('province'))}\n"
        f"城市特点：{_field(city.get('tag'))}\n"
        f"热门去处：{_field(spots)}\n"
        "以上字段是已知信息，可以直接引用；没有给出的信息不要猜测，统一写成「以官方公告为准」。"
    )


def _unknown_city_prompt(name: str) -> str:
    return (
        f"请为「{name}」写一份通用出行攻略。\n"
        "本站没有收录它的热门去处与票价数据，这些一律不要编造，统一写成「以官方公告为准」；"
        "其余板块给出通用的交通、路线、拍照与周边美食建议，并提醒读者以官方公告和当地实际情况为准。"
    )


def _ask_ai(prompt: str, ai_config: AiConfig) -> str:
    payload = {
        "model": ai_config.model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": _MAX_TOKENS,
    }
    try:
        response = httpx.post(
            ai_config.base_url,
            headers={"Authorization": f"Bearer {ai_config.api_key}"},
            json=payload,
            timeout=settings.DEEPSEEK_TIMEOUT_S,
        )
        response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        return ""


def _build(
    target: str,
    kind: str,
    keyword: str,
    local_blurb: str,
    ai_prompt: str,
    ai_config: AiConfig | None,
) -> dict:
    blurb = ""
    provider = "local"
    if ai_config is not None:
        blurb = _ask_ai(ai_prompt, ai_config)
        if blurb:
            provider = "ai"
    if not blurb:
        blurb = local_blurb
    return {
        "target": target,
        "kind": kind,
        "keyword": keyword,
        "search_url": build_search_url(keyword),
        "blurb": _clamp_blurb(blurb),
        "provider": provider,
    }


def attraction_reco(name: str, ai_config: AiConfig | None = None) -> dict:
    target = (name or "").strip()
    if not target:
        raise ValueError("attraction_not_found")
    found = _find_attraction(target)
    if found is None:
        return _build(
            target,
            "attraction",
            f"{target} 攻略",
            _local_attraction_blurb("", {"name": target}),
            _unknown_attraction_prompt(target),
            ai_config,
        )
    city_name, item = found
    return _build(
        item["name"],
        "attraction",
        f"{item['name']} 攻略",
        _local_attraction_blurb(city_name, item),
        _attraction_prompt(city_name, item),
        ai_config,
    )


def city_reco(name: str, ai_config: AiConfig | None = None) -> dict:
    target = (name or "").strip()
    if not target:
        raise ValueError("city_not_found")
    city = _find_city(target)
    if city is None:
        return _build(
            target,
            "city",
            f"{target} 攻略",
            _local_city_blurb({"name": target, "province": "", "tag": "", "spots": []}),
            _unknown_city_prompt(target),
            ai_config,
        )
    return _build(
        city["name"],
        "city",
        f"{city['name']} 攻略",
        _local_city_blurb(city),
        _city_prompt(city),
        ai_config,
    )