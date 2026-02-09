"""DB models: User, List, ListItem, Event, AuditLog. Minimal PII (phone truncated)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def _truncate_phone(phone: str, visible: int = 4) -> str:
    """Truncate phone for storage: 5511999999999 -> 55119***9999."""
    if not phone or len(phone) <= visible * 2:
        return phone[:visible] + "***" if len(phone) > visible else phone
    return phone[:visible] + "***" + phone[-visible:]


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_hash = Column(String(64), unique=True, nullable=False, index=True)  # hash(phone) for lookup
    phone_truncated = Column(String(32), nullable=False)  # 55119***9999
    preferred_name = Column(String(128), nullable=True)  # como o cliente gostaria de ser chamado (perguntado via Xiaomi)
    language = Column(String(8), nullable=True)  # pt-BR, pt-PT, es, en (None = infer from phone)
    timezone = Column(String(64), nullable=True)  # IANA e.g. Europe/Lisbon, America/Sao_Paulo (None = infer from phone)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lists = relationship("List", back_populates="user", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="user", cascade="all, delete-orphan")


class List(Base):
    __tablename__ = "lists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)  # e.g. "mercado", "pendentes"
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="lists")
    items = relationship("ListItem", back_populates="list_ref", cascade="all, delete-orphan", order_by="ListItem.id")


class ListItem(Base):
    __tablename__ = "list_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    list_id = Column(Integer, ForeignKey("lists.id"), nullable=False, index=True)
    text = Column(String(512), nullable=False)
    done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    list_ref = relationship("List", back_populates="items")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tipo = Column(String(64), nullable=False)  # "lembrete", "filme", "livro", "musica", "evento"
    payload = Column(JSON, nullable=False)  # {"nome": "...", "data": "...", ...}
    data_at = Column(DateTime, nullable=True)  # quando ocorre
    recorrente = Column(String(128), nullable=True)  # cron expr or "every N seconds"
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted = Column(Boolean, default=False)

    user = relationship("User", back_populates="events")


class ReminderHistory(Base):
    """Histórico de pedidos e lembretes entregues para o cliente poder rever («foi este o pedido», «foi esta a lembrança»)."""
    __tablename__ = "reminder_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(16), nullable=False)  # 'scheduled' = pedido agendado, 'delivered' = lembrança enviada
    message = Column(Text, nullable=False)     # texto do pedido ou da mensagem enviada
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    action = Column(String(64), nullable=False)  # list_add, list_remove, event_add, etc.
    resource = Column(String(128), nullable=True)  # list name, event id
    created_at = Column(DateTime, default=datetime.utcnow)
