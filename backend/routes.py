"""Rotas da API: users, lists, events, audit. Todas exigem API key quando API_SECRET_KEY está definido."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from backend.auth import require_api_key
from backend.database import get_db
from backend.models_db import User, List, ListItem, Event, AuditLog
from backend.rate_limit import is_rest_rate_limited
from backend.sanitize import clamp_limit

router = APIRouter()


def _rate_limit_rest(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Dependency: rejects request if REST rate limit exceeded."""
    if is_rest_rate_limited(x_api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


# --- Schemas ---
class UserOut(BaseModel):
    id: int
    phone_truncated: str


class ListItemOut(BaseModel):
    id: int
    text: str
    done: bool


class ListOut(BaseModel):
    id: int
    name: str
    items: list[ListItemOut]


class EventOut(BaseModel):
    id: int
    tipo: str
    payload: dict


# --- Rotas protegidas (requerem X-API-Key quando API_SECRET_KEY está definido) ---
@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
    __: None = Depends(_rate_limit_rest),
) -> list[UserOut]:
    users = db.query(User).all()
    return [UserOut(id=u.id, phone_truncated=u.phone_truncated) for u in users]


@router.get("/users/{user_id}/lists", response_model=list[ListOut])
def list_user_lists(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
    __: None = Depends(_rate_limit_rest),
) -> list[ListOut]:
    lists = (
        db.query(List)
        .options(selectinload(List.items))
        .filter(List.user_id == user_id)
        .all()
    )
    return [
        ListOut(
            id=lst.id,
            name=lst.name,
            items=[ListItemOut(id=i.id, text=i.text, done=i.done) for i in lst.items],
        )
        for lst in lists
    ]


@router.get("/users/{user_id}/events", response_model=list[EventOut])
def list_user_events(
    user_id: int,
    tipo: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
    __: None = Depends(_rate_limit_rest),
) -> list[EventOut]:
    q = db.query(Event).filter(Event.user_id == user_id, Event.deleted == False)
    if tipo:
        q = q.filter(Event.tipo == tipo)
    events = q.order_by(Event.created_at.desc()).limit(100).all()
    return [EventOut(id=e.id, tipo=e.tipo, payload=e.payload) for e in events]


@router.get("/audit", response_model=list[dict])
def audit_log(
    limit: int = 100,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
    __: None = Depends(_rate_limit_rest),
) -> list[dict]:
    limit = clamp_limit(limit, default=100, maximum=500)
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {"id": a.id, "user_id": a.user_id, "action": a.action, "resource": a.resource, "created_at": str(a.created_at)}
        for a in logs
    ]
