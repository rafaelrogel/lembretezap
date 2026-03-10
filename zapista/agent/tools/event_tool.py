import json
from datetime import datetime, timedelta, timezone
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
        "Para 'add': fornece 'event_text' e opcionalmente 'date_time_iso' (pode ser apenas a data YYYY-MM-DD se não houver hora). "
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
                "description": "(add) Data/hora do evento no formato ISO. Pode ser completo (e.g., '2026-03-12T10:00:00') ou apenas a data (e.g., '2026-03-12'). Não pergunte a hora se o utilizador der apenas a data.",
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
    
    def set_context(self, channel: str, chat_id: str, phone_for_locale: str | None = None) -> None:
        """Sets the user context for the session."""
        self.chat_id = chat_id
        self.phone = phone_for_locale

    async def execute(self, **kwargs) -> str:
        import logging
        logger = logging.getLogger(__name__)

        if not self.chat_id:
            logger.error("EventTool failed: Contexto (chat_id) não definido.")
            return "Erro: Contexto (chat_id) não definido na EventTool."
            
        action = kwargs.get("action")
        
        from backend.user_store import get_or_create_user, get_user_timezone
        
        db = self.db_session_factory()
        try:
            user = get_or_create_user(db, self.chat_id)
            tz_str = get_user_timezone(db, self.chat_id, self.phone) or "UTC"
            try:
                tz = ZoneInfo(tz_str)
            except Exception:
                tz = ZoneInfo("UTC")

            if action == "add":
                event_text = kwargs.get("event_text")
                if not event_text:
                    logger.error("EventTool add failed: event_text is missing")
                    return "Erro: 'event_text' é obrigatório para a ação 'add'."
                
                date_time_iso = kwargs.get("date_time_iso")
                data_at = None
                if date_time_iso:
                    # Support Python <= 3.10 where fromisoformat requires time segment
                    if "T" not in date_time_iso.upper() and len(date_time_iso.strip()) <= 10:
                        date_time_iso = f"{date_time_iso.strip()}T00:00:00"
                        
                    try:
                        # Validation: do not allow past dates (guardrails)
                        from zapista.clock_drift import get_effective_time
                        effective_ts = get_effective_time()
                        now = datetime.fromtimestamp(effective_ts, tz=timezone.utc)
                        
                        dt = datetime.fromisoformat(date_time_iso)
                        if dt.tzinfo is None:
                            user_tz_str = get_user_timezone(db, self.chat_id) or "UTC"
                            dt = dt.replace(tzinfo=ZoneInfo(user_tz_str))
                        
                        # Compare in UTC
                        dt_utc = dt.astimezone(timezone.utc)
                        
                        logger.info(f"EventTool check: now={now.isoformat()} dt_utc={dt_utc.isoformat()} (date_time_iso={date_time_iso})")
                        
                        # Grace period of 5 minutes (300s)
                        if dt_utc < (now - timedelta(minutes=5)):
                            logger.warning(f"EventTool: blocked past date {dt_utc.isoformat()} (now={now.isoformat()})")
                            from backend.locale import REMINDER_TIME_PAST_TODAY, REMINDER_DATE_PAST_ASK_NEXT_YEAR
                            lang = self._get_user_lang()
                            
                            # If it's the same day, use "time past today" message
                            if dt_utc.date() == now.date():
                                return REMINDER_TIME_PAST_TODAY.get(lang, REMINDER_TIME_PAST_TODAY["pt-BR"])
                            else:
                                return REMINDER_DATE_PAST_ASK_NEXT_YEAR.get(lang, REMINDER_DATE_PAST_ASK_NEXT_YEAR["pt-BR"])

                        # If validation passes, proceed to set data_at
                        data_at = dt.replace(tzinfo=None)
                        logger.info(f"EventTool: validation passed for {dt_utc.isoformat()}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"EventTool: invalid date_time_iso '{date_time_iso}': {e}")
                        # Se o LLM por acaso injetar "nenhum" ou "nao sei", apenas ignoramos e criamos sem hora
                        data_at = None

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
                    logger.error("EventTool remove failed: event_id is missing")
                    return "Erro: 'event_id' é obrigatório para a ação 'remove'."
                
                from backend.models_db import Event
                
                # We need to extract the raw integer if it came as a string or with an 'E' prefix
                # Because the LLM could send event_id=123 or event_id="123"
                try:
                    ev_id_int = int(str(event_id).replace("E", ""))
                except ValueError:
                    logger.error(f"EventTool remove failed: invalid event_id format {event_id}")
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
                logger.error(f"EventTool failed: unknown action {action}")
                return f"Erro: Ação '{action}' desconhecida para event tool."
                
        except Exception as e:
            logger.error(f"EventTool: error in execute: {e}")
            return f"Erro ao processar agenda: {e}"
        finally:
            db.close()

    def _get_user_lang(self) -> str:
        """Idioma do usuário para mensagens (pt-PT, pt-BR, es, en). Uses local DB preference; fallback to pt-BR."""
        if not self.chat_id:
            return "pt-BR"
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_user_language
            from backend.locale import resolve_response_language
            db = SessionLocal()
            try:
                lang = get_user_language(db, self.chat_id) or "pt-BR"
                return resolve_response_language(lang, self.chat_id)
            finally:
                db.close()
        except Exception:
            return "pt-BR"
