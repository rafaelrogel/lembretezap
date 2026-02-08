"""Rotas da API: users, lists, events, audit. Todas exigem API key quando API_SECRET_KEY está definido."""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth import require_api_key
from backend.database import get_db
from backend.models_db import User, List, ListItem, Event, AuditLog
from backend.sanitize import clamp_limit

router = APIRouter()


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
) -> list[UserOut]:
    users = db.query(User).all()
    return [UserOut(id=u.id, phone_truncated=u.phone_truncated) for u in users]


@router.get("/users/{user_id}/lists", response_model=list[ListOut])
def list_user_lists(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> list[ListOut]:
    lists = db.query(List).filter(List.user_id == user_id).all()
    result: list[ListOut] = []
    for lst in lists:
        items = db.query(ListItem).filter(ListItem.list_id == lst.id).all()
        result.append(ListOut(
            id=lst.id,
            name=lst.name,
            items=[ListItemOut(id=i.id, text=i.text, done=i.done) for i in items],
        ))
    return result


@router.get("/users/{user_id}/events", response_model=list[EventOut])
def list_user_events(
    user_id: int,
    tipo: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
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
) -> list[dict]:
    limit = clamp_limit(limit, default=100, maximum=500)
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {"id": a.id, "user_id": a.user_id, "action": a.action, "resource": a.resource, "created_at": str(a.created_at)}
        for a in logs
    ]
