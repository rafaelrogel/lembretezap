import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from zapista.agent.tools.base import Tool

class EventTool(Tool):
    """
    Ferramenta para adicionar, listar ou remover compromissos da agenda do utilizador.
    Eventos e Agenda são sinónimos.
    
    Ação `add`: requer `event_text` e opcionalmente `date_time_iso` (ex: 2026-03-12T10:00:00).
    Ação `list`: lista eventos.
    Ação `remove`: requer `event_id`.
    """

    name = "event"
    description = (
        "Adiciona, lista ou remove eventos/compromissos na agenda do utilizador. "
        "Ações válidas: 'add', 'list', 'remove'. "
        "Para 'add': fornece 'event_text' e opcionalmente 'date_time_iso'. "
        "Para 'remove': fornece 'event_id'."
    )
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "remove"],
                "description": "Ação a executar.",
            },
            "event_text": {
                "type": "string",
                "description": "(add) Nome/texto do evento ou compromisso.",
            },
            "date_time_iso": {
                "type": "string",
                "description": "(add) Data/hora do evento no formato ISO, e.g., '2026-03-12T10:00:00'.",
            },
            "event_id": {
                "type": "integer",
                "description": "(remove) ID do evento a remover.",
            },
        },
        "required": ["action"],
    }

    def __init__(self, db_session_factory: Any, **kwargs):
        super().__init__(**kwargs)
        self.db_session_factory = db_session_factory
        self.chat_id: str | None = None
        self.phone: str | None = None
    
    def set_context(self, chat_id: str, phone: str | None = None) -> None:
        """Sets the user context for the session."""
        self.chat_id = chat_id
        self.phone = phone

    async def execute(self, **kwargs) -> str:
        if not self.chat_id:
            return "Erro: Contexto (chat_id) não definido na EventTool."
            
        action = kwargs.get("action")
        
        from backend.user_store import get_or_create_user, get_user_timezone
        
        db = self.db_session_factory()
        try:
            user = get_or_create_user(db, self.chat_id, phone=self.phone)
            tz_str = get_user_timezone(db, self.chat_id, self.phone) or "UTC"
            try:
                tz = ZoneInfo(tz_str)
            except Exception:
                tz = ZoneInfo("UTC")

            if action == "add":
                event_text = kwargs.get("event_text")
                if not event_text:
                    return "Erro: 'event_text' é obrigatório para a ação 'add'."
                
                date_time_iso = kwargs.get("date_time_iso")
                data_at = None
                if date_time_iso:
                    # Support Python <= 3.10 where fromisoformat requires time segment
                    if "T" not in date_time_iso.upper() and len(date_time_iso.strip()) <= 10:
                        date_time_iso = f"{date_time_iso.strip()}T00:00:00"
                        
                    try:
                        dt = datetime.fromisoformat(date_time_iso)
                        if dt.tzinfo is None:
                            # Assume ISO was provided in the user's timezone, convert to UTC
                            dt = dt.replace(tzinfo=tz).astimezone(ZoneInfo("UTC"))
                        data_at = dt.replace(tzinfo=None)
                    except ValueError:
                        return f"Erro: Formato ISO inválido para date_time_iso: {date_time_iso}"

                from backend.models_db import Event
                ev = Event(
                    user_id=user.id,
                    tipo="evento",
                    payload={"nome": event_text},
                    data_at=data_at,
                )
                db.add(ev)
                db.commit()
                db.refresh(ev)
                
                dt_str = "sem data definida"
                if ev.data_at:
                    local_dt = ev.data_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
                    dt_str = local_dt.strftime("%d/%m/%Y às %H:%M")
                
                return f"Evento '{event_text}' adicionado com sucesso à agenda ({dt_str}) [id: E{ev.id}]."

            elif action == "list":
                from backend.models_db import Event
                
                # Fetch undeleted events for this user
                events = db.query(Event).filter(
                    Event.user_id == user.id,
                    Event.tipo == "evento",
                    Event.deleted == False
                ).all()
                
                if not events:
                    return "A agenda está vazia."
                    
                lines = ["📅 Eventos na Agenda:"]
                for ev in events:
                    nome = ev.payload.get("nome", "Evento Desconhecido")
                    if ev.data_at:
                        local_dt = ev.data_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
                        dt_str = local_dt.strftime("%d/%m %H:%M")
                    else:
                        dt_str = "S/ Data"
                    lines.append(f"[id: {ev.id}] {nome} ({dt_str})")
                
                return "\n".join(lines)

            elif action == "remove":
                event_id = kwargs.get("event_id")
                if not event_id:
                    return "Erro: 'event_id' é obrigatório para a ação 'remove'."
                
                from backend.models_db import Event
                
                # We need to extract the raw integer if it came as a string or with an 'E' prefix
                # Because the LLM could send event_id=123 or event_id="123"
                try:
                    ev_id_int = int(str(event_id).replace("E", ""))
                except ValueError:
                    return f"Erro: 'event_id' inválido: {event_id}"

                ev = db.query(Event).filter(
                    Event.id == ev_id_int, 
                    Event.user_id == user.id,
                    Event.deleted == False
                ).first()
                
                if ev:
                    ev.deleted = True
                    db.commit()
                    return f"Evento [id: {event_id}] removido com sucesso."
                return f"Erro: Evento [id: {event_id}] não encontrado na agenda."

            else:
                return f"Erro: Ação '{action}' desconhecida para event tool."
                
        except Exception as e:
            return f"Erro interno ao executar a ferramenta event: {e}"
        finally:
            db.close()
