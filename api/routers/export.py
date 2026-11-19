"""行程导出路由：ICS / PDF / PNG。"""

from __future__ import annotations

from fastapi import APIRouter, Response

from services import plan_service

router = APIRouter(prefix="/api/plan", tags=["export"])


def _attachment(content: bytes | str, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/export.ics")
def export_ics(session_id: str) -> Response:
    from services import export_service

    session = plan_service.get(session_id)
    return _attachment(export_service.to_ics(session), "text/calendar", f"{session_id}.ics")


@router.get("/{session_id}/export.pdf")
def export_pdf(session_id: str) -> Response:
    from services import export_service

    session = plan_service.get(session_id)
    return _attachment(export_service.to_pdf(session), "application/pdf", f"{session_id}.pdf")


@router.get("/{session_id}/export.png")
def export_png(session_id: str) -> Response:
    from services import export_service

    session = plan_service.get(session_id)
    return _attachment(export_service.to_png(session), "image/png", f"{session_id}.png")