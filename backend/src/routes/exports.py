from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import EXPORT_ROLES
from src.controllers import export_controller
from src.middlewares.rbac import require_roles

router = APIRouter(prefix="/exports", tags=["exports"])


def _csv_response(text: str, filename: str) -> Response:
    return Response(
        content=text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "X-Export-Filename": filename,
        },
    )


@router.get("/schedule.csv")
def export_schedule(
    request: Request,
    run_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*EXPORT_ROLES)),
) -> Response:
    text, filename = export_controller.schedule_csv(db, run_id, actor, request)
    return _csv_response(text, filename)


@router.get("/backfill.csv")
def export_backfill(
    request: Request,
    pipeline: str = Query(...),
    as_of: str | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=7),
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*EXPORT_ROLES)),
) -> Response:
    text, filename = export_controller.backfill_csv(db, pipeline, as_of, days, actor, request)
    return _csv_response(text, filename)
