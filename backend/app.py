"""FastAPI app for frontend irmão: CRUD listas/eventos, minimal PII."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import init_db, get_db, SessionLocal
from backend.models_db import User, List, ListItem, Event, AuditLog
from backend.user_store import phone_hash, get_or_create_user

# Token opcional para /health: se definido, só responde 200 com header X-Health-Token correto (uso interno/orquestração)
HEALTH_CHECK_TOKEN = os.environ.get("HEALTH_CHECK_TOKEN", "").strip() or None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    # shutdown


app = FastAPI(title="WhatsApp AI Organizer API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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


# --- Routes ---
@app.get("/health")
def health(x_health_token: str | None = Header(None, alias="X-Health-Token")):
    """Health check. Se HEALTH_CHECK_TOKEN estiver definido, exige header X-Health-Token (acesso interno)."""
    if HEALTH_CHECK_TOKEN and x_health_token != HEALTH_CHECK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"status": "ok"}


@app.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [UserOut(id=u.id, phone_truncated=u.phone_truncated) for u in users]


@app.get("/users/{user_id}/lists", response_model=list[ListOut])
def list_user_lists(user_id: int, db: Session = Depends(get_db)):
    lists = db.query(List).filter(List.user_id == user_id).all()
    result = []
    for lst in lists:
        items = db.query(ListItem).filter(ListItem.list_id == lst.id).all()
        result.append(ListOut(
            id=lst.id,
            name=lst.name,
            items=[ListItemOut(id=i.id, text=i.text, done=i.done) for i in items],
        ))
    return result


@app.get("/users/{user_id}/events", response_model=list[EventOut])
def list_user_events(user_id: int, tipo: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Event).filter(Event.user_id == user_id, Event.deleted == False)
    if tipo:
        q = q.filter(Event.tipo == tipo)
    events = q.order_by(Event.created_at.desc()).limit(100).all()
    return [EventOut(id=e.id, tipo=e.tipo, payload=e.payload) for e in events]


@app.get("/audit", response_model=list[dict])
def audit_log(limit: int = 100, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {"id": a.id, "user_id": a.user_id, "action": a.action, "resource": a.resource, "created_at": str(a.created_at)}
        for a in logs
    ]
