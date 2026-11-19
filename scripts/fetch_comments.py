# -*- coding: utf-8 -*-
"""离线采集小红书公开笔记标题摘要，落库为网友评语。

用法：``python scripts/fetch_comments.py --city 北京 [--limit 3] [--target-type city|attraction]``

采集与线上读取完全解耦：只在人工执行时访问外网，逐条限速、单条失败跳过，
不写登录态 Cookie、不重试、不并发，任何失败都不让进程以非 0 退出。
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from datastore.db import init_db  # noqa: E402
from services.comment_service import upsert_comments  # noqa: E402

logger = logging.getLogger("fetch_comments")

SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={keyword}"
SITE_ROOT = "https://www.xiaohongshu.com"

CARD_SELECTORS = ("section.note-item", "div.note-item", ".note-item")
TITLE_SELECTORS = ("a.title", ".footer .title", ".title")
DESC_SELECTORS = (".footer .desc", ".desc")
AUTHOR_SELECTORS = (".author .name", ".author-wrapper .name", ".name")
LINK_SELECTORS = ("a.cover", "a[href*='/explore/']", "a[href]")

MAX_PER_RUN = 10
MAX_TEXT_LEN = 200
THROTTLE_S = 2.0
DEFAULT_AUTHOR = "网友"


def _first_text(card, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        node = card.query_selector(selector)
        if node is None:
            continue
        text = (node.inner_text() or "").strip()
        if text:
            return text
    return ""


def _first_href(card) -> str:
    for selector in LINK_SELECTORS:
        node = card.query_selector(selector)
        if node is None:
            continue
        href = (node.get_attribute("href") or "").strip()
        if not href:
            continue
        if href.startswith("http"):
            return href
        return SITE_ROOT + (href if href.startswith("/") else "/" + href)
    return ""


def _collect(city: str, limit: int, target_type: str) -> int:
    """打开站内搜索页，逐条解析并落库，返回写入条数。"""
    from playwright.sync_api import sync_playwright

    saved = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(
                SEARCH_URL.format(keyword=quote(city)),
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.wait_for_timeout(3000)

            cards = []
            for selector in CARD_SELECTORS:
                cards = page.query_selector_all(selector)
                if cards:
                    break

            for card in cards:
                if saved >= limit:
                    break
                try:
                    title = _first_text(card, TITLE_SELECTORS)
                    href = _first_href(card)
                    if not title or not href:
                        logger.warning("跳过一条无标题或无链接的笔记")
                        continue
                    desc = _first_text(card, DESC_SELECTORS)
                    text = title if not desc or desc == title else f"{title} {desc}"
                    item = {
                        "target": city,
                        "target_type": target_type,
                        "author": _first_text(card, AUTHOR_SELECTORS) or DEFAULT_AUTHOR,
                        "text": text.strip()[:MAX_TEXT_LEN],
                        "source_url": href,
                    }
                    upsert_comments([item])
                    saved += 1
                except Exception as exc:
                    logger.warning("跳过一条采集失败的笔记: %s", exc)
                    continue
                if saved < limit:
                    time.sleep(THROTTLE_S)
        finally:
            browser.close()
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="采集小红书公开笔记作为网友评语")
    parser.add_argument("--city", default="", help="城市或景点名，作为评语 target")
    parser.add_argument("--limit", type=int, default=3, help=f"本次最多采集条数（上限 {MAX_PER_RUN}）")
    parser.add_argument(
        "--target-type",
        choices=("city", "attraction"),
        default="city",
        help="评语归属类型",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    city = str(args.city).strip()
    if not city:
        logger.warning("未提供 --city，跳过采集")
        return 0

    limit = max(1, min(args.limit, MAX_PER_RUN))
    try:
        init_db()
    except Exception as exc:
        logger.warning("数据库初始化失败，跳过采集: %s", exc)
        return 0

    try:
        saved = _collect(city, limit, args.target_type)
    except Exception as exc:
        logger.warning("采集失败，跳过本次运行: %s", exc)
        return 0

    logger.info("采集完成：target=%s 类型=%s 写入 %d 条", city, args.target_type, saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())