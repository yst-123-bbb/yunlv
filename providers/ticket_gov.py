"""景区官网门票 Provider：分档白名单 + 静态解析/Playwright 兜底 + 票价抽取校验。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from datastore.db import connect, transaction
from datastore.repository import enqueue_review, upsert_entity, upsert_field
from infra.cache import TTL_SEMI_STATIC, get_cache, namespaced
from infra.http import get_text
from infra.logging_setup import get_logger, log_event
from providers.models import ExtractionInvalid, ProviderUnavailable, TicketOffer

TICKET_CITY_TIERS: dict[str, Literal["A", "B", "C"]] = {
    # A 档：超热门
    "北京": "A",
    "上海": "A",
    "西安": "A",
    "成都": "A",
    "杭州": "A",
    "重庆": "A",
    "三亚": "A",
    # B 档：热门
    "厦门": "B",
    "丽江": "B",
    "大理": "B",
    "青岛": "B",
    "武汉": "B",
    "南京": "B",
    "长沙": "B",
    "苏州": "B",
    "广州": "B",
    "深圳": "B",
    "哈尔滨": "B",
    "昆明": "B",
    # C 档：潜力
    "张家界": "C",
    "桂林": "C",
    "黄山": "C",
    "洛阳": "C",
    "敦煌": "C",
    "拉萨": "C",
    "西宁": "C",
}

TICKET_WHITELIST: dict[str, dict[str, str]] = {
    "北京": {
        "故宫博物院": "https://www.dpm.org.cn/",
        "八达岭长城": "https://www.badaling.cn/",
        "颐和园": "https://www.summerpalace-china.com/",
        "天坛公园": "https://www.tiantanpark.com/",
        "中国国家博物馆": "https://www.chnmuseum.cn/",
    },
    "上海": {
        "上海博物馆": "https://www.shanghaimuseum.net/",
        "东方明珠": "https://www.orientalpearltower.com/",
        "豫园": "https://www.yugarden.com.cn/",
        "上海科技馆": "https://www.sstm.org.cn/",
    },
    "西安": {
        "秦始皇帝陵博物院": "https://www.bmy.com.cn/",
        "陕西历史博物馆": "https://www.sxhm.com/",
        "华清宫": "https://www.hqc.cn/",
        "西安城墙": "https://www.xiancitywall.com/",
    },
    "成都": {
        "成都大熊猫繁育研究基地": "https://www.panda.org.cn/",
        "武侯祠": "https://www.wuhouci.net.cn/",
        "杜甫草堂": "https://www.cddfct.com/",
        "金沙遗址博物馆": "https://www.jinshasitemuseum.com/",
    },
    "杭州": {
        "灵隐寺": "https://www.lingyinsi.org/",
        "浙江省博物馆": "https://www.zhejiangmuseum.com/",
        "西溪湿地": "https://www.xixiwetland.com.cn/",
        "雷峰塔": "https://www.leifengta.net/",
    },
    "重庆": {
        "重庆中国三峡博物馆": "http://www.3gmuseum.cn/",
        "大足石刻": "https://www.dazushike.com/",
        "武隆天生三桥": "https://www.wlkst.com/",
        "洪崖洞": "http://www.hongyadong.com/",
    },
    "三亚": {
        "天涯海角": "http://www.tianyahaijiao.com.cn/",
        "南山文化旅游区": "http://www.sanyananshan.com/",
        "蜈支洲岛": "https://www.wuzhizhou.com/",
        "大小洞天": "http://www.daxiaodongtian.com/",
    },
    "厦门": {
        "鼓浪屿": "http://www.gly.cn/",
        "厦门大学": "https://www.xmu.edu.cn/",
    },
    "丽江": {
        "玉龙雪山": "http://www.yulongmountain.com/",
        "丽江古城": "http://www.ljgc.gov.cn/",
    },
    "大理": {
        "崇圣寺三塔": "http://www.dalisanta.com/",
        "苍山": "http://www.dalicangshan.com/",
    },
    "青岛": {
        "崂山": "http://www.qdls.gov.cn/",
        "青岛啤酒博物馆": "http://www.tsingtaobeermuseum.cn/",
    },
    "武汉": {
        "黄鹤楼": "http://www.cnhhl.com/",
        "湖北省博物馆": "https://www.hbww.org/",
    },
    "南京": {
        "中山陵": "https://www.zschina.org.cn/",
        "南京博物院": "https://www.njmuseum.com/",
    },
    "长沙": {
        "岳麓书院": "http://ylsy.hnu.edu.cn/",
        "湖南博物院": "https://www.hnmuseum.com/",
    },
    "苏州": {
        "拙政园": "http://www.szzzy.com/",
        "苏州博物馆": "https://www.szmuseum.com/",
    },
    "广州": {
        "陈家祠": "http://www.gzchenjiaci.com/",
        "广州塔": "https://www.cantontower.com/",
    },
    "深圳": {
        "世界之窗": "https://www.szwwco.com/",
        "深圳博物馆": "https://www.shenzhenmuseum.com/",
    },
    "哈尔滨": {
        "冰雪大世界": "https://www.hrbicesnow.com/",
        "圣索菲亚教堂": "http://www.sophiachurch.com/",
    },
    "昆明": {
        "石林": "https://www.chinastoneforest.com/",
        "云南民族村": "https://www.ynmzc.com/",
    },
    "张家界": {
        "武陵源核心景区": "http://www.zjjwly.com/",
    },
    "桂林": {
        "象鼻山": "http://www.glbss.com/",
    },
    "黄山": {
        "黄山风景区": "https://www.huangshan.gov.cn/",
    },
    "洛阳": {
        "龙门石窟": "http://www.lmsk.cn/",
    },
    "敦煌": {
        "莫高窟": "https://www.mgk.org.cn/",
    },
    "拉萨": {
        "布达拉宫": "http://www.potalapalace.cn/",
    },
    "西宁": {
        "塔尔寺": "http://www.kumbum.net/",
    },
}


_MIN_PRICE = 0.0
_MAX_PRICE = 2000.0
_CACHE_NS = "ticket_gov"
_PLAYWRIGHT_TIMEOUT_MS = 20_000
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_PRICE_RANGE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:元|¥|￥)?\s*[-~—至到]\s*(\d+(?:\.\d+)?)\s*(?:元|¥|￥)"
)
_PRICE_SINGLE_RE = re.compile(r"(?:¥|￥)?\s*(\d+(?:\.\d+)?)\s*元")
_TIME_RANGE_RE = re.compile(
    r"(\d{1,2}\s*[:：]\s*\d{2})\s*[-—~至到]\s*(\d{1,2}\s*[:：]\s*\d{2})"
)
_EXCERPT_LIMIT = 500

_logger = get_logger("ticket_gov")


def tier_of(city: str) -> Literal["A", "B", "C"] | None:
    return TICKET_CITY_TIERS.get(city)


def whitelist_for(city: str) -> dict[str, str]:
    return dict(TICKET_WHITELIST.get(city, {}))


def list_cities(tier: Literal["A", "B", "C"] | None = None) -> list[str]:
    if tier is None:
        return list(TICKET_CITY_TIERS)
    return [city for city, level in TICKET_CITY_TIERS.items() if level == tier]


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _normalize_time(value: str) -> str:
    return value.replace("：", ":").replace(" ", "")


def _parse_price_text(text: str) -> dict[str, Any] | None:
    range_match = _PRICE_RANGE_RE.search(text)
    if range_match:
        low, high = float(range_match.group(1)), float(range_match.group(2))
        return {"price_min": min(low, high), "price_max": max(low, high)}

    prices = [float(m) for m in _PRICE_SINGLE_RE.findall(text)]
    if not prices:
        return None
    return {"price_min": min(prices), "price_max": max(prices)}


def _parse_open_time(text: str) -> str:
    match = _TIME_RANGE_RE.search(text)
    if not match:
        return ""
    return f"{_normalize_time(match.group(1))}-{_normalize_time(match.group(2))}"


def _kimi_extract(text: str, place_name: str) -> dict[str, Any] | None:
    """官网正文噪声较大时用 Kimi 兜底抽票务字段；不可用或解析失败返回 None。"""
    try:
        from apis.kimi_api import KimiClient

        client = KimiClient()
        if not client.available():
            return None
        prompt = (
            f"下面是一段景区官网正文，请抽取「{place_name}」的票务信息，"
            '只输出 JSON：{"price_min": 数字或null, "price_max": 数字或null, '
            '"open_time": "HH:MM-HH:MM 或空串", "booking_required": true/false, '
            '"booking_channel": "字符串或空串"}。不要输出任何解释。\n\n'
            f"正文：\n{text[:4000]}"
        )
        reply = client.ask(prompt, remember=False)
    except Exception as exc:
        log_event(_logger, "ticket_kimi_failed", provider="ticket_gov", error=str(exc))
        return None
    if not reply:
        return None

    cleaned = reply.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.S).strip()
    try:
        data = json.loads(cleaned)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    low, high = data.get("price_min"), data.get("price_max")
    if low is None and high is None:
        return None
    if low is None:
        low = high
    if high is None:
        high = low
    try:
        return {
            "price_min": float(low),
            "price_max": float(high),
            "open_time": str(data.get("open_time") or ""),
            "booking_required": bool(data.get("booking_required")),
            "booking_channel": str(data.get("booking_channel") or ""),
        }
    except (TypeError, ValueError):
        return None


def extract_ticket(text: str, place_name: str) -> dict[str, Any]:
    """从官网正文抽取票务字段；价区间无法识别时抛 ExtractionInvalid。"""
    body = text or ""
    parsed = _parse_price_text(body)
    if parsed is None:
        parsed = _kimi_extract(body, place_name)
    if parsed is None:
        excerpt = body[:_EXCERPT_LIMIT]
        raise ExtractionInvalid("ticket_price_not_found", raw_excerpt=excerpt)

    channel = ""
    if "公众号" in body:
        channel = "官方微信公众号"
    elif "预约" in body:
        channel = "官网预约"

    return {
        "price_min": float(parsed["price_min"]),
        "price_max": float(parsed["price_max"]),
        "open_time": parsed.get("open_time") or _parse_open_time(body),
        "booking_required": bool(parsed.get("booking_required")) or "预约" in body,
        "booking_channel": parsed.get("booking_channel") or channel,
    }


class TicketGovProvider:
    name = "ticket_gov"

    def search(self, place_name: str, city: str) -> list[TicketOffer]:
        url = whitelist_for(city).get(place_name)
        if not url:
            return []

        cache = get_cache()
        cache_key = namespaced(_CACHE_NS, f"{city}:{place_name}")
        cached = cache.get(cache_key)
        if cached:
            try:
                return [TicketOffer(**item) for item in cached]
            except Exception:
                cache.delete(cache_key)

        html = self._fetch(url)
        text = self._to_text(html)
        fields = extract_ticket(text, place_name)

        low, high = fields["price_min"], fields["price_max"]
        if not (_MIN_PRICE <= low <= high <= _MAX_PRICE):
            self._enqueue_invalid(place_name, city, fields, text)
            raise ExtractionInvalid("ticket_price_out_of_range", raw_excerpt=text[:_EXCERPT_LIMIT])

        offer = TicketOffer(
            name=place_name,
            city=city,
            price_min=low,
            price_max=high,
            open_time=fields["open_time"],
            booking_required=fields["booking_required"],
            booking_channel=fields["booking_channel"],
            source=self.name,
            source_url=url,
            fetched_at=_now(),
            confidence=0.6,
        )
        self._persist(offer)
        cache.set(cache_key, [offer.model_dump()], TTL_SEMI_STATIC)
        log_event(
            _logger,
            "ticket_extracted",
            provider=self.name,
            outcome="ok",
            city=city,
            place=place_name,
        )
        return [offer]

    def _fetch(self, url: str) -> str:
        try:
            return get_text(url, headers=_HEADERS, provider=self.name)
        except Exception as exc:
            log_event(
                _logger,
                "ticket_static_failed",
                provider=self.name,
                error=str(exc),
                outcome="fallback",
            )
        try:
            return self._fetch_playwright(url)
        except Exception as exc:
            log_event(
                _logger,
                "ticket_playwright_failed",
                provider=self.name,
                error=str(exc),
                outcome="failed",
            )
            raise ProviderUnavailable(f"ticket_gov_unavailable: {url}") from exc

    @staticmethod
    def _fetch_playwright(url: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ProviderUnavailable("playwright_unavailable") from exc

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=_HEADERS["User-Agent"])
                page.goto(url, timeout=_PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
                return page.content()
            finally:
                browser.close()

    @staticmethod
    def _to_text(html: str) -> str:
        try:
            import trafilatura

            extracted = trafilatura.extract(html)
        except Exception:
            extracted = None
        if extracted:
            return extracted
        # 去除脚本与标签，作为无 trafilatura 时的降级正文
        stripped = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
        return re.sub(r"(?s)<[^>]+>", " ", stripped)

    def _persist(self, offer: TicketOffer) -> None:
        try:
            conn = connect()
            try:
                with transaction(conn):
                    entity_id = upsert_entity(
                        conn, type="place", city=offer.city, name=offer.name
                    )
                    upsert_field(
                        conn,
                        entity_id=entity_id,
                        field_name="ticket_price",
                        value={"price_min": offer.price_min, "price_max": offer.price_max},
                        source=self.name,
                        source_url=offer.source_url,
                        confidence=offer.confidence,
                    )
            finally:
                conn.close()
        except Exception as exc:
            log_event(_logger, "ticket_persist_failed", provider=self.name, error=str(exc))

    def _enqueue_invalid(
        self, place_name: str, city: str, fields: dict[str, Any], text: str
    ) -> None:
        try:
            conn = connect()
            try:
                with transaction(conn):
                    entity_id = upsert_entity(conn, type="place", city=city, name=place_name)
                    enqueue_review(
                        conn,
                        entity_id=entity_id,
                        field_name="ticket_price",
                        proposed={
                            "price_min": fields.get("price_min"),
                            "price_max": fields.get("price_max"),
                        },
                        current=None,
                        reason="ticket_price_out_of_range",
                        raw_excerpt=text[:_EXCERPT_LIMIT],
                    )
            finally:
                conn.close()
        except Exception as exc:
            log_event(_logger, "ticket_review_enqueue_failed", provider=self.name, error=str(exc))