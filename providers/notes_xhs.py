"""小红书单链导入 Provider：只抓取用户粘贴的单条笔记，不遍历站点。"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

try:  # 可选依赖：缺失时退化为仅用 meta/标题提取
    import trafilatura
except ImportError:  # pragma: no cover - 取决于运行环境
    trafilatura = None
from bs4 import BeautifulSoup

from infra.http import get_text
from infra.logging_setup import get_logger, log_event, new_req_id
from providers.models import NoteItem, ProviderUnavailable

logger = get_logger(__name__)

SUMMARY_LIMIT = 500

_TZ = timezone(timedelta(hours=8))
_ALLOWED_HOST = "xiaohongshu.com"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}
_AUTHOR_META_KEYS = (
    "og:xhs:note_author",
    "xhs:note_author",
    "og:article:author",
    "author",
)
_TITLE_META_KEYS = ("og:title", "twitter:title")
_WS_RE = re.compile(r"\s+")


def _now_iso() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")


def _is_xhs_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == _ALLOWED_HOST or host.endswith(f".{_ALLOWED_HOST}")


def _meta(soup: BeautifulSoup, keys: tuple[str, ...]) -> str:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find(
            "meta", attrs={"name": key}
        )
        content = _WS_RE.sub(" ", str(tag.get("content") or "")).strip() if tag else ""
        if content:
            return content
    return ""


def _summarize(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()[:SUMMARY_LIMIT]


class XhsNoteProvider:
    """C-PROVIDER@1 的 NoteProvider 实现：单条链接，无本地兜底。"""

    name = "notes_xhs"

    def fetch(self, url: str) -> NoteItem:
        req_id = new_req_id()
        if not _is_xhs_url(url):
            log_event(
                logger,
                "note_rejected",
                req_id=req_id,
                provider=self.name,
                outcome="unsupported_domain",
                url=url,
            )
            raise ProviderUnavailable(f"unsupported_domain: {url}")

        try:
            html = get_text(url, provider=self.name, headers=_BROWSER_HEADERS)
        except Exception as exc:
            # 抓取失败统一转成 ProviderUnavailable，由降级链接手处理
            log_event(
                logger,
                "note_fetch_failed",
                req_id=req_id,
                provider=self.name,
                outcome="error",
                error=str(exc),
                url=url,
            )
            raise ProviderUnavailable(str(exc)) from exc

        summary = _summarize(
            (trafilatura.extract(html, include_comments=False, include_tables=False) if trafilatura else "")
            or ""
        )
        soup = BeautifulSoup(html, "html.parser")
        author = _meta(soup, _AUTHOR_META_KEYS)
        title = _meta(soup, _TITLE_META_KEYS)
        if not title and soup.title is not None:
            title = _WS_RE.sub(" ", soup.title.get_text(strip=True)).strip()

        if not summary and not title:
            log_event(
                logger,
                "note_extract_failed",
                req_id=req_id,
                provider=self.name,
                outcome="empty_content",
                url=url,
            )
            raise ProviderUnavailable("empty_content")

        log_event(
            logger,
            "note_fetched",
            req_id=req_id,
            provider=self.name,
            outcome="ok",
            url=url,
            has_author=bool(author),
        )
        return NoteItem(
            title=title or summary[:20] or "小红书笔记",
            author=author or "未知作者",
            summary=summary,
            source_url=url,
            fetched_at=_now_iso(),
            # 抓取成功但正文/作者可能不全，按 C-MODEL@1 取 0.6
            confidence=0.6,
        )