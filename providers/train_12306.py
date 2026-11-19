"""12306 官方公开车次页只读查询：httpx 优先、Playwright 兜底，失败交由降级链处理。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from infra.cache import TTL_TRANSPORT, get_cache, namespaced
from infra.http import get_json, get_text
from infra.logging_setup import get_logger, log_event
from infra.ratelimit import breaker, singleflight
from providers.models import ProviderUnavailable, TransportOffer

PROVIDER_NAME = "train_12306"
STATION_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
INIT_URL = "https://kyfw.12306.cn/otn/leftTicket/init"
QUERY_URL = "https://kyfw.12306.cn/otn/leftTicket/queryZ"
OFFICIAL_URL = "https://www.12306.cn"
PLAYWRIGHT_TIMEOUT_MS = 20_000
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": INIT_URL,
}
# 12306 公开查询返回的余票字段下标（无座席信息时可能整段缺失）
SEAT_FIELDS: tuple[tuple[int, str], ...] = (
    (29, "二等座"),
    (30, "一等座"),
    (31, "商务座"),
    (33, "动卧"),
    (23, "软卧"),
    (26, "硬卧"),
    (28, "硬座"),
    (24, "软座"),
    (21, "高级软卧"),
)
EMPTY_SEAT_MARKS = frozenset({"", "无", "*", "--"})
CST = timezone(timedelta(hours=8))

_STATIONS: dict[str, str] = {}


class Train12306Provider:
    name = PROVIDER_NAME

    def search(self, origin: str, dest: str, date: str) -> list[TransportOffer]:
        origin = (origin or "").strip()
        dest = (dest or "").strip()
        if not origin or not dest:
            raise ProviderUnavailable("train_12306 missing_station")
        _parse_date(date)

        key = namespaced("transport", f"{PROVIDER_NAME}:{origin}:{dest}:{date}")
        cache = get_cache()
        cached = cache.get(key)
        if cached is not None:
            return [TransportOffer.model_validate(item) for item in cached]

        offers = singleflight(key, lambda: self._search_uncached(origin, dest, date))
        if offers:
            cache.set(key, [offer.model_dump() for offer in offers], TTL_TRANSPORT)
        return offers

    def _search_uncached(self, origin: str, dest: str, date: str) -> list[TransportOffer]:
        logger = get_logger(__name__)
        errors: list[str] = []
        strategies = (("httpx", self._fetch_httpx), ("playwright", self._fetch_playwright))

        for strategy_name, strategy in strategies:
            started = time.monotonic()
            try:
                offers = strategy(origin, dest, date)
            except Exception as exc:
                errors.append(f"{strategy_name}:{exc}")
                log_event(
                    logger,
                    "provider_attempt",
                    provider=self.name,
                    strategy=strategy_name,
                    duration_ms=_elapsed_ms(started),
                    outcome="error",
                    error=str(exc),
                )
                continue
            duration_ms = _elapsed_ms(started)
            if offers:
                breaker.record_success(self.name)
                log_event(
                    logger,
                    "provider_attempt",
                    provider=self.name,
                    strategy=strategy_name,
                    duration_ms=duration_ms,
                    outcome="ok",
                )
                return offers
            errors.append(f"{strategy_name}:empty_result")
            log_event(
                logger,
                "provider_attempt",
                provider=self.name,
                strategy=strategy_name,
                duration_ms=duration_ms,
                outcome="empty",
            )

        breaker.record_failure(self.name)
        raise ProviderUnavailable("train_12306 failed: " + "; ".join(errors))

    def _fetch_httpx(self, origin: str, dest: str, date: str) -> list[TransportOffer]:
        stations = _stations_via_http()
        from_code, to_code = _resolve_codes(stations, origin, dest)
        payload = get_json(
            QUERY_URL,
            params=_query_params(from_code, to_code, date),
            headers=HEADERS,
            provider=self.name,
        )
        return self._build_offers(_result_rows(payload), origin, dest, stations, date)

    def _fetch_playwright(self, origin: str, dest: str, date: str) -> list[TransportOffer]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ProviderUnavailable("playwright_unavailable") from exc

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(INIT_URL, timeout=PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
                station_text = page.request.get(STATION_URL, timeout=PLAYWRIGHT_TIMEOUT_MS).text()
                stations = _parse_stations(station_text)
                if not stations:
                    raise ProviderUnavailable("station_list_empty")
                _STATIONS.update(stations)
                from_code, to_code = _resolve_codes(stations, origin, dest)
                response = page.request.get(
                    QUERY_URL,
                    params=_query_params(from_code, to_code, date),
                    headers=HEADERS,
                    timeout=PLAYWRIGHT_TIMEOUT_MS,
                )
                if not response.ok:
                    raise ProviderUnavailable(f"playwright_http_{response.status}")
                payload = response.json()
            finally:
                browser.close()

        return self._build_offers(_result_rows(payload), origin, dest, stations, date)

    def _build_offers(
        self,
        rows: list[str],
        origin: str,
        dest: str,
        stations: dict[str, str],
        date: str,
    ) -> list[TransportOffer]:
        names = {code: name for name, code in stations.items()}
        fetched_at = _now_iso()
        offers: list[TransportOffer] = []
        seen: set[str] = set()

        for row in rows:
            parts = row.split("|")
            if len(parts) < 11:
                continue
            code = parts[3].strip()
            depart, arrive = parts[8].strip(), parts[9].strip()
            duration_min = _parse_duration(parts[10].strip())
            if not code or code in seen or duration_min is None or not depart or not arrive:
                continue
            try:
                depart_dt = datetime.strptime(f"{date} {depart}", "%Y-%m-%d %H:%M")
            except ValueError:
                continue
            seen.add(code)
            arrive_dt = depart_dt + timedelta(minutes=duration_min)
            offers.append(
                TransportOffer(
                    mode="train",
                    code=code,
                    from_station=names.get(parts[6].strip(), origin),
                    to_station=names.get(parts[7].strip(), dest),
                    depart_time=depart_dt.strftime("%Y-%m-%d %H:%M"),
                    arrive_time=arrive_dt.strftime("%Y-%m-%d %H:%M"),
                    duration_min=duration_min,
                    # 官方公开查询页不再返回票价，价格置 0.0 并以 0.6 标注字段不全
                    price_cny=0.0,
                    seat_class=_seat_class(parts),
                    source=self.name,
                    source_url=OFFICIAL_URL,
                    fetched_at=fetched_at,
                    confidence=0.6,
                )
            )
        return offers


def _query_params(from_code: str, to_code: str, date: str) -> dict[str, str]:
    return {
        "leftTicketDTO.train_date": date,
        "leftTicketDTO.from_station": from_code,
        "leftTicketDTO.to_station": to_code,
        "purpose_codes": "ADULT",
    }


def _stations_via_http() -> dict[str, str]:
    if _STATIONS:
        return _STATIONS
    stations = _parse_stations(get_text(STATION_URL, headers=HEADERS, provider=PROVIDER_NAME))
    if not stations:
        raise ProviderUnavailable("station_list_empty")
    _STATIONS.update(stations)
    return _STATIONS


def _parse_stations(text: str) -> dict[str, str]:
    stations: dict[str, str] = {}
    for entry in text.split("@"):
        parts = entry.split("|")
        if len(parts) < 3:
            continue
        name, code = parts[1].strip(), parts[2].strip()
        if name and code:
            stations.setdefault(name, code)
    return stations


def _resolve_codes(stations: dict[str, str], origin: str, dest: str) -> tuple[str, str]:
    from_code = _resolve_code(stations, origin)
    if from_code is None:
        raise ProviderUnavailable(f"unknown_station:{origin}")
    to_code = _resolve_code(stations, dest)
    if to_code is None:
        raise ProviderUnavailable(f"unknown_station:{dest}")
    return from_code, to_code


def _resolve_code(stations: dict[str, str], name: str) -> str | None:
    for candidate in (name, f"{name}站", name.removesuffix("站")):
        code = stations.get(candidate)
        if code:
            return code
    return None


def _result_rows(payload: Any) -> list[str]:
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data.get("result") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ProviderUnavailable("train_12306 unexpected_payload")
    return [row for row in rows if isinstance(row, str)]


def _seat_class(parts: list[str]) -> str:
    for index, label in SEAT_FIELDS:
        if index < len(parts) and parts[index].strip() not in EMPTY_SEAT_MARKS:
            return label
    return ""


def _parse_duration(raw: str) -> int | None:
    pieces = raw.split(":")
    if len(pieces) != 2:
        return None
    try:
        hours, minutes = int(pieces[0]), int(pieces[1])
    except ValueError:
        return None
    if hours < 0 or not 0 <= minutes < 60:
        return None
    return hours * 60 + minutes


def _parse_date(date: str) -> datetime:
    try:
        return datetime.strptime(date, "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise ProviderUnavailable(f"train_12306 invalid_date:{date}") from exc


def _now_iso() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)