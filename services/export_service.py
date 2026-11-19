# -*- coding: utf-8 -*-
"""导出与分享产物：iCalendar、PDF 行程单、PNG 长图与只读分享存取。"""

from __future__ import annotations

import html as html_module
import json
import re
import secrets
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from typing import TYPE_CHECKING, Any

from datastore.db import connect, transaction
from infra.logging_setup import get_logger, log_event

if TYPE_CHECKING:
    from services.plan_service import PlanSession

logger = get_logger(__name__)

TZ = timezone(timedelta(hours=8))
ICS_TZID = "Asia/Shanghai"

_SHORT_ID_BYTES = 6
_SHORT_ID_TRIES = 5
_DEFAULT_START = (9, 0)
_DEFAULT_DURATION_MIN = 120
_HHMM_RE = re.compile(r"(\d{1,2}):(\d{2})")

_BUDGET_LABELS = (
    ("transport", "交通"),
    ("hotel", "住宿"),
    ("tickets", "门票"),
    ("food", "餐饮"),
    ("city_transport", "市内交通"),
    ("shopping", "购物"),
    ("reserve", "备用金"),
)

_PNG_VIEWPORT = {"width": 750, "height": 1334}


def to_ics(session: PlanSession) -> str:
    """生成 iCalendar 文本；每个 itinerary item 一个 VEVENT，时区固定 Asia/Shanghai。"""
    session_id = str(_field(session, "session_id", "") or "")
    base = _parse_date((_field(session, "user_data", {}) or {}).get("dep_date"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CloudTrip//Plan Export//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for entry in _itinerary(session):
        day = _to_int(_field(entry, "day"), 0)
        if day <= 0:
            continue
        day_date = _day_date(entry, base, day)
        items = [item for item in (_field(entry, "items", []) or []) if item is not None]
        for index, item in enumerate(items, start=1):
            start, end = _item_span(day_date, item)
            name = str(_field(item, "name", "") or "")
            summary = name or f"{day_date.isoformat()} 行程"
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{session_id}-{day}-{index}@cloudtrip",
                    f"DTSTAMP:{stamp}",
                    f"DTSTART;TZID={ICS_TZID}:{start.strftime('%Y%m%dT%H%M%S')}",
                    f"DTEND;TZID={ICS_TZID}:{end.strftime('%Y%m%dT%H%M%S')}",
                    f"SUMMARY:{_ics_escape(summary)}",
                    f"LOCATION:{_ics_escape(name)}",
                    "END:VEVENT",
                ]
            )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def to_pdf(session: PlanSession, map_png: bytes | None = None) -> bytes:
    """用 reportlab 生成 PDF 行程单；无地图图片时跳过图片区。"""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    font_name = "STSong-Light"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))

    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CNTitle",
        parent=base_styles["Title"],
        fontName=font_name,
        fontSize=20,
        leading=26,
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        "CNHeading",
        parent=base_styles["Heading2"],
        fontName=font_name,
        fontSize=13,
        leading=18,
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "CNBody",
        parent=base_styles["BodyText"],
        fontName=font_name,
        fontSize=10.5,
        leading=15,
    )
    small_style = ParagraphStyle(
        "CNSmall",
        parent=body_style,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#555555"),
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="云旅 AI 行程单",
    )

    story: list[Any] = [Paragraph("云旅 AI 行程单", title_style), Spacer(1, 6)]
    story.extend(Paragraph(html_module.escape(line), body_style) for line in _overview_lines(session))

    if map_png:
        image = _map_flowable(map_png, doc.width)
        if image is not None:
            story.extend([Spacer(1, 8), image])

    base = _parse_date((_field(session, "user_data", {}) or {}).get("dep_date"))
    for entry in _itinerary(session):
        day = _to_int(_field(entry, "day"), 0)
        title = str(_field(entry, "title", "") or (f"第 {day} 天" if day else "日程"))
        story.append(Paragraph(html_module.escape(title), heading_style))
        items = [item for item in (_field(entry, "items", []) or []) if item is not None]
        if not items:
            story.append(Paragraph("暂无安排", small_style))
        for item in items:
            story.append(Paragraph(html_module.escape(_item_label(item)), body_style))
            note = str(_field(item, "tip", "") or _field(item, "note", "") or "")
            if note:
                story.append(Paragraph(html_module.escape(note), small_style))

    budget_rows = _budget_rows(session)
    if budget_rows:
        story.append(Paragraph("预算明细", heading_style))
        data = [["分项", "金额（元）"]]
        data.extend([label, f"{value:.2f}"] for label, value in budget_rows)
        table = Table(data, colWidths=[70 * mm, 40 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c7d2fe")),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ]
            )
        )
        story.append(table)

    doc.build(story)
    return buffer.getvalue()


def to_png(session: PlanSession) -> bytes:
    """用 Playwright 渲染内置 HTML 模板后整页截图。"""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError("playwright_unavailable") from exc

    document = _render_html(session)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport=_PNG_VIEWPORT)
                page.set_content(document, wait_until="load")
                return page.screenshot(full_page=True)
            finally:
                browser.close()
    except RuntimeError:
        raise
    except Exception as exc:
        log_event(logger, "export_png_failed", outcome="error", error=str(exc))
        raise RuntimeError("playwright_unavailable") from exc


_SHARE_DDL = (
    "CREATE TABLE IF NOT EXISTS share_link ("
    "short_id TEXT PRIMARY KEY, "
    "session_json TEXT NOT NULL, "
    "created_at TEXT NOT NULL, "
    "session_id TEXT NOT NULL UNIQUE)"
)


def _ensure_share_table(conn: sqlite3.Connection) -> None:
    """幂等建表：确保不经 FastAPI 启动钩子（如 CLI 直接调用）时也能写分享。"""
    conn.execute(_SHARE_DDL)


def save_share(session: PlanSession) -> str:
    """以 session_id 为唯一键保存只读分享，重复调用返回既有 short_id。"""
    session_id = str(_field(session, "session_id", "") or "")
    if not session_id:
        raise ValueError("session_id_required")
    payload = _dump_session(session)
    conn = connect()
    try:
        _ensure_share_table(conn)
        with transaction(conn):
            existing = _select_short_id(conn, session_id)
            if existing is not None:
                return existing
            for _ in range(_SHORT_ID_TRIES):
                short_id = secrets.token_urlsafe(_SHORT_ID_BYTES)
                try:
                    conn.execute(
                        "INSERT INTO share_link"
                        "(short_id, session_json, created_at, session_id) "
                        "VALUES (?, ?, ?, ?)",
                        (short_id, payload, _now_iso(), session_id),
                    )
                except sqlite3.IntegrityError:
                    duplicate = _select_short_id(conn, session_id)
                    if duplicate is not None:
                        return duplicate
                    continue
                log_event(logger, "share_saved", session_id=session_id, outcome="ok")
                return short_id
            raise RuntimeError("short_id_conflict")
    finally:
        conn.close()


def load_share(short_id: str) -> PlanSession:
    """按 short_id 读取分享快照。"""
    conn = connect()
    try:
        _ensure_share_table(conn)
        row = conn.execute(
            "SELECT session_json FROM share_link WHERE short_id = ?",
            (short_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise KeyError("share_not_found")

    from services.plan_service import PlanSession as SessionModel

    return SessionModel.model_validate_json(str(row["session_json"]))


def _ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _day_date(entry: Any, base: date | None, day: int) -> date:
    explicit = _parse_date(_field(entry, "date"))
    if explicit is not None:
        return explicit
    return (base or date.today()) + timedelta(days=max(day, 1) - 1)


def _parse_hhmm(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = _HHMM_RE.search(value)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def _item_span(day_date: date, item: Any) -> tuple[datetime, datetime]:
    start_hm = _parse_hhmm(_field(item, "start")) or _DEFAULT_START
    start = datetime.combine(day_date, time(start_hm[0], start_hm[1]), tzinfo=TZ)
    end_hm = _parse_hhmm(_field(item, "end"))
    if end_hm is not None:
        end = datetime.combine(day_date, time(end_hm[0], end_hm[1]), tzinfo=TZ)
        if end <= start:
            end += timedelta(days=1)
        return start, end
    duration = _to_int(_field(item, "duration_min"), _DEFAULT_DURATION_MIN)
    return start, start + timedelta(minutes=max(duration, 15))


def _item_label(item: Any) -> str:
    name = str(_field(item, "name", "") or "未命名安排")
    start = str(_field(item, "start", "") or "")
    end = str(_field(item, "end", "") or "")
    if start and end:
        return f"{start}-{end}  {name}"
    if start:
        return f"{start}  {name}"
    return name


def _itinerary(session: Any) -> list[Any]:
    entries = _field(session, "itinerary", []) or []
    return [entry for entry in entries if entry is not None]


def _overview_lines(session: Any) -> list[str]:
    user_data = _field(session, "user_data", {}) or {}
    departure = str(user_data.get("departure") or "")
    destination = str(
        user_data.get("destination") or user_data.get("dest") or "未指定目的地"
    )
    route = f"{departure} → {destination}" if departure else destination

    lines = [f"路线：{route}"]
    dates = _date_range(user_data)
    if dates:
        lines.append(f"日期：{dates}")
    days = user_data.get("days")
    if days:
        lines.append(f"天数：{days} 天")
    people = user_data.get("people")
    if people:
        lines.append(f"人数：{people} 人")
    return lines


def _date_range(user_data: dict) -> str:
    dep_date = str(user_data.get("dep_date") or "")
    return_date = str(user_data.get("return_date") or "")
    if dep_date and return_date:
        return f"{dep_date} 至 {return_date}"
    return dep_date


def _budget_rows(session: Any) -> list[tuple[str, float]]:
    budget = _field(session, "budget", None)
    if budget is None:
        return []
    if not isinstance(budget, dict):
        as_dict = getattr(budget, "model_dump", None)
        budget = as_dict() if callable(as_dict) else dict(budget)

    rows = [(label, _to_float(budget.get(key))) for key, label in _BUDGET_LABELS]
    rows.append(("合计", _to_float(budget.get("grand_total"))))
    rows.append(("人均", _to_float(budget.get("per_person"))))
    return rows


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _map_flowable(png: bytes, max_width: float) -> Any:
    from reportlab.platypus import Image

    try:
        image = Image(BytesIO(png))
    except Exception:
        return None
    width = getattr(image, "imageWidth", 0) or 0
    height = getattr(image, "imageHeight", 0) or 0
    if width <= 0 or height <= 0:
        return None
    image.drawWidth = max_width
    image.drawHeight = max_width * height / width
    return image


def _render_html(session: Any) -> str:
    overview = "".join(
        f"<p>{html_module.escape(line)}</p>" for line in _overview_lines(session)
    )

    blocks: list[str] = []
    for entry in _itinerary(session):
        day = _to_int(_field(entry, "day"), 0)
        title = str(_field(entry, "title", "") or (f"第 {day} 天" if day else "日程"))
        items = [item for item in (_field(entry, "items", []) or []) if item is not None]
        entries: list[str] = []
        for item in items:
            note = str(_field(item, "tip", "") or _field(item, "note", "") or "")
            note_html = (
                f'<span class="note">{html_module.escape(note)}</span>' if note else ""
            )
            entries.append(
                f'<li><span class="name">{html_module.escape(_item_label(item))}</span>'
                f"{note_html}</li>"
            )
        if not entries:
            entries.append('<li class="empty">暂无安排</li>')
        blocks.append(
            f'<section class="card"><h2>{html_module.escape(title)}</h2>'
            f'<ul>{"".join(entries)}</ul></section>'
        )

    budget_rows = _budget_rows(session)
    if budget_rows:
        rows = "".join(
            f"<tr><td>{html_module.escape(label)}</td><td>{value:.2f}</td></tr>"
            for label, value in budget_rows
        )
        blocks.append(
            '<section class="card"><h2>预算明细</h2>'
            f'<table><tbody>{rows}</tbody></table></section>'
        )

    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<title>云旅 AI 行程单</title><style>"
        "*{box-sizing:border-box;}"
        "body{margin:0;padding:24px;background:#f5f7fb;color:#1f2937;"
        "font-family:\"Microsoft YaHei\",\"PingFang SC\",sans-serif;}"
        "h1{font-size:30px;margin:0 0 8px;color:#1d4ed8;}"
        "h2{font-size:20px;margin:0 0 10px;color:#1f2937;}"
        ".overview{background:#fff;border-radius:14px;padding:16px 20px;margin-bottom:16px;"
        "box-shadow:0 2px 10px rgba(15,23,42,.08);}"
        ".overview p{margin:4px 0;font-size:16px;color:#475569;}"
        ".card{background:#fff;border-radius:14px;padding:18px 20px;margin-bottom:16px;"
        "box-shadow:0 2px 10px rgba(15,23,42,.08);}"
        "ul{list-style:none;margin:0;padding:0;}"
        "li{padding:10px 0;border-bottom:1px solid #e2e8f0;display:flex;flex-direction:column;gap:4px;}"
        "li:last-child{border-bottom:none;}"
        ".name{font-size:17px;color:#1e293b;}"
        ".note{font-size:14px;color:#64748b;}"
        ".empty{color:#94a3b8;font-size:15px;}"
        "table{width:100%;border-collapse:collapse;font-size:16px;}"
        "td{padding:8px 4px;border-bottom:1px solid #e2e8f0;}"
        "td:last-child{text-align:right;color:#1d4ed8;font-weight:600;}"
        "</style></head><body>"
        "<h1>云旅 AI 行程单</h1>"
        f'<div class="overview">{overview}</div>'
        f'{"".join(blocks)}'
        "</body></html>"
    )


def _dump_session(session: Any) -> str:
    dump = getattr(session, "model_dump_json", None)
    if callable(dump):
        return dump()
    return json.dumps(session, ensure_ascii=False)


def _now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _select_short_id(conn: sqlite3.Connection, session_id: str) -> str | None:
    row = conn.execute(
        "SELECT short_id FROM share_link WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return str(row["short_id"])