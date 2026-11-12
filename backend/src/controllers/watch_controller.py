"""告警确认 + 列表控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, watch_service


def list_alerts(db: Session) -> dict:
    return watch_service.build_watchlist(db)


def ack(db: Session, key: str, payload: dict, actor: dict, request: Request) -> dict:
    saved = watch_service.save_ack(key, actor["email"], payload.get("note", ""))
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="alert.ack",
        entity="alert",
        entity_id=key,
        detail={"note": payload.get("note", "")},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return {"key": key, "acked": True, **saved}
