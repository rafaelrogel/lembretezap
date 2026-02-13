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
    city = Column(String(128), nullable=True)  # cidade do utilizador (onboarding); usada para timezone quando reconhecida
    default_reminder_lead_seconds = Column(Integer, nullable=True)  # aviso X segundos antes do evento (ex.: 86400 = 1 dia)
    extra_reminder_leads = Column(Text, nullable=True)  # JSON array de até 3 ints (ex.: [259200,86400,7200] = 3d, 1d, 2h)
    language = Column(String(8), nullable=True)  # pt-BR, pt-PT, es, en (None = infer from phone)
    timezone = Column(String(64), nullable=True)  # IANA e.g. Europe/Lisbon, America/Sao_Paulo (None = infer from phone)
    quiet_start = Column(String(5), nullable=True)  # HH:MM início do horário silencioso (ex.: 22:00)
    quiet_end = Column(String(5), nullable=True)    # HH:MM fim (ex.: 08:00); janela pode ser overnight
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lists = relationship("List", back_populates="user", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    """Projetos que agrupam listas/tarefas."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class List(Base):
    __tablename__ = "lists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)  # e.g. "mercado", "pendentes"
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)  # agrupa listas em projetos
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="lists")
    items = relationship("ListItem", back_populates="list_ref", cascade="all, delete-orphan", order_by="ListItem.id")


class Habit(Base):
    """Hábitos diários (beber água, academia)."""
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class HabitCheck(Base):
    """Marcação diária de hábito."""
    __tablename__ = "habit_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    habit_id = Column(Integer, ForeignKey("habits.id"), nullable=False, index=True)
    check_date = Column(String(10), nullable=False)  # YYYY-MM-DD em timezone do user
    created_at = Column(DateTime, default=datetime.utcnow)


class Goal(Base):
    """Metas com prazo."""
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    done = Column(Boolean, default=False)


class Note(Base):
    """Notas rápidas não estruturadas."""
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Bookmark(Base):
    """Bookmarks com contexto, tags e categoria geradas por IA (Mimo)."""
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    context = Column(Text, nullable=True)  # última mensagem do assistente (opcional)
    tags_json = Column(Text, nullable=False)  # ["receita", "lasanha", "espinafres"]
    category = Column(String(64), nullable=True)  # receita | ideia | link | tarefa | outro
    created_at = Column(DateTime, default=datetime.utcnow)


class ListTemplate(Base):
    """Modelos de listas frequentes."""
    __tablename__ = "list_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    items_json = Column(Text, nullable=False)  # JSON array ["item1", "item2"]
    created_at = Column(DateTime, default=datetime.utcnow)


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
    """Histórico de pedidos e lembretes para o cliente rever (agendados, enviados, falhados, cancelados)."""
    __tablename__ = "reminder_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(16), nullable=False)  # 'scheduled' | 'delivered' (legado); preferir status
    message = Column(Text, nullable=False)     # texto do pedido ou da mensagem enviada
    created_at = Column(DateTime, default=datetime.utcnow)

    # Campos expandidos: correlação com job e auditoria (evita "sumiu", "cadê a mensagem?")
    job_id = Column(String(64), nullable=True, index=True)   # ID do job cron; permite update_on_delivery
    schedule_at = Column(DateTime, nullable=True)          # quando agendado para disparar
    channel = Column(String(32), nullable=True)              # whatsapp, cli, etc.
    recipient = Column(String(256), nullable=True)           # JID/chat_id do destinatário
    status = Column(String(16), nullable=True)               # scheduled | sent | failed | canceled | expired
    delivered_at = Column(DateTime, nullable=True)          # quando foi entregue (se status=sent)
    provider_error = Column(String(256), nullable=True)     # erro do gateway se status=failed


class SentReminderMapping(Base):
    """Mapeia mensagem WhatsApp (chat_id, message_id) → job_id para reações (emoji = feito)."""
    __tablename__ = "sent_reminder_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(256), nullable=False, index=True)
    message_id = Column(String(64), nullable=False, index=True)
    job_id = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class HouseChoreTask(Base):
    """Tarefa de limpeza: frequency weekly | bi-weekly, weekday, time."""
    __tablename__ = "house_chore_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    catalog_slug = Column(String(64), nullable=False)  # slug do catálogo ou custom
    custom_name = Column(String(128), nullable=True)   # se null, usa catalog
    frequency = Column(String(16), nullable=False)    # weekly | bi-weekly
    weekday = Column(Integer, nullable=False)        # 0=seg..6=dom (ISO: 1=seg, 7=dom — usamos 0–6)
    time_hhmm = Column(String(5), nullable=False)     # HH:MM
    rotation_enabled = Column(Boolean, default=False)
    last_person_idx = Column(Integer, default=-1)      # -1 = ainda não rodou; 0,1,2... = índice em ChorePerson
    created_at = Column(DateTime, default=datetime.utcnow)


class HouseChorePerson(Base):
    """Pessoa na rotação de tarefas (flatmates, família)."""
    __tablename__ = "house_chore_persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(64), nullable=False)
    order_idx = Column(Integer, default=0)  # ordem na rotação
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    action = Column(String(64), nullable=False)  # list_add, list_remove, list_feito, event_add, etc.
    resource = Column(String(128), nullable=True)  # list name, event id
    payload_json = Column(Text, nullable=True)  # JSON com detalhes para recuperação (ex: {"item_text": "pão"})
    created_at = Column(DateTime, default=datetime.utcnow)
