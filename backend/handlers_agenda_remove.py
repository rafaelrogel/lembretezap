"""Handler: quando o cliente diz que já realizou/concluiu um evento ou pede para remover da agenda."""

import re
from backend.handler_context import HandlerContext
from backend.database import SessionLocal
from backend.user_store import get_or_create_user, get_user_timezone
from backend.models_db import Event
from backend.locale import (
    LangCode,
    get_user_language,
    resolve_response_language,
)
from zoneinfo import ZoneInfo
from datetime import datetime


# Padrões para intenção "remover da agenda" / "já realizei"
_REMOVE_PATTERNS = [
    re.compile(r"^(?:remover?|tirar|apagar)\s+(?:o|a|da\s+agenda)?\s*(.+)$", re.I),
    re.compile(r"^(?:j[aá]\s+fiz|conclu[ií]|realizei|fiz)\s+(?:o|a)?\s*(.+)$", re.I),
    re.compile(r"^(?:quero\s+)?(?:remover?|tirar)\s+(.+?)\s*(?:da\s+agenda)?\s*$", re.I),
    re.compile(r"^(.+?)\s*[-–—]\s*(?:remover?|tirar\s+da\s+agenda)\s*$", re.I),
    re.compile(r"^remove?\s+(.+?)\s*from\s+(?:the\s+)?agenda\s*$", re.I),
    re.compile(r"^(?:done\s+with|completed)\s+(.+)$", re.I),
    re.compile(r"^(?:ya\s+)?(?:hice|realic[eé]|termin[eé])\s+(?:el|la)?\s*(.+)$", re.I),
]


def _extract_event_reference(content: str) -> str | None:
    """Se a mensagem parecer pedido de remoção da agenda, devolve o trecho que referencia o evento."""
    t = (content or "").strip()
    if not t or len(t) > 200:
        return None
    for pat in _REMOVE_PATTERNS:
        m = pat.search(t)
        if m:
            ref = m.group(1).strip()
            # Limpar artigos no início
            ref = re.sub(r"^(?:o\s+|a\s+|os\s+|as\s+|el\s+|la\s+)", "", ref, flags=re.I).strip()
            ref = re.sub(r"\s*(?:da\s+agenda)?\s*$", "", ref, flags=re.I).strip()
            if len(ref) >= 2:
                return ref
    return None


def _events_today_for_user(db, user_id: int, tz) -> list[Event]:
    """Eventos do user com data_at hoje (no timezone do user), não deletados."""
    now = datetime.now(tz)
    today = now.date()
    today_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=tz)
    today_end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=tz)
    events = (
        db.query(Event)
        .filter(
            Event.user_id == user_id,
            Event.deleted == False,
            Event.data_at.isnot(None),
        )
        .all()
    )
    out = []
    for ev in events:
        if not ev.data_at:
            continue
        ev_date = ev.data_at if ev.data_at.tzinfo else ev.data_at.replace(tzinfo=ZoneInfo("UTC"))
        try:
            ev_local = ev_date.astimezone(tz).date()
        except Exception:
            ev_local = ev_date.date()
        if ev_local == today:
            out.append(ev)
    return out


def _event_name(ev: Event) -> str:
    if isinstance(ev.payload, dict):
        return (ev.payload.get("nome") or "").strip()
    return (str(ev.payload) or "").strip()[:100]


def _match_events(ref: str, events: list[Event]) -> list[Event]:
    """Ref = trecho dito pelo user (ex. 'consulta', 'reunião'). Devolve eventos cujo nome contém ref ou ref contém nome."""
    ref_lower = ref.lower().strip()
    if not ref_lower:
        return []
    matched = []
    for ev in events:
        name = _event_name(ev)
        name_lower = name.lower()
        if ref_lower in name_lower or name_lower in ref_lower or ref_lower in name_lower:
            matched.append(ev)
    return matched


# Mensagens localizadas
_MSG_REMOVED: dict[LangCode, str] = {
    "pt-PT": "Removido da agenda: \"{nome}\".",
    "pt-BR": "Removido da agenda: \"{nome}\".",
    "es": "Quitado de la agenda: \"{nombre}\".",
    "en": "Removed from agenda: \"{name}\".",
}

_MSG_WHICH_ONE: dict[LangCode, str] = {
    "pt-PT": "Há vários eventos que podem ser esse. Qual queres remover? (diz o nome completo)\n{lista}",
    "pt-BR": "Há vários eventos que podem ser esse. Qual você quer remover? (diga o nome completo)\n{lista}",
    "es": "Hay varios eventos que podrían ser. ¿Cuál quieres quitar? (di el nombre completo)\n{lista}",
    "en": "There are several events that could match. Which one do you want to remove? (say the full name)\n{lista}",
}

_MSG_NOT_FOUND: dict[LangCode, str] = {
    "pt-PT": "Não encontrei nenhum evento da agenda de hoje com esse nome. Podes dizer de novo ou ver a agenda com /hoje ou /agenda.",
    "pt-BR": "Não encontrei nenhum evento da agenda de hoje com esse nome. Pode dizer de novo ou ver a agenda com /hoje ou /agenda.",
    "es": "No encontré ningún evento de la agenda de hoy con ese nombre. Puedes decir de nuevo o ver la agenda con /hoje o /agenda.",
    "en": "I didn't find any event on today's agenda with that name. You can say it again or check the agenda with /hoje or /agenda.",
}


async def handle_agenda_remove(ctx: HandlerContext, content: str) -> str | None:
    """
    Se o cliente pedir para remover um evento da agenda (ex.: "remover a consulta", "já fiz a reunião"),
    faz soft-delete do evento e confirma. Caso contrário devolve None.
    """
    ref = _extract_event_reference(content)
    if ref is None:
        return None

    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)
        tz_iana = get_user_timezone(db, ctx.chat_id)
        try:
            tz = ZoneInfo(tz_iana)
        except Exception:
            tz = ZoneInfo("UTC")

        events_today = _events_today_for_user(db, user.id, tz)
        matched = _match_events(ref, events_today)

        lang = get_user_language(db, ctx.chat_id) or "pt-BR"
        lang = resolve_response_language(lang, ctx.chat_id, None)
        if lang not in _MSG_REMOVED:
            lang = "en"

        if not matched:
            return _MSG_NOT_FOUND.get(lang, _MSG_NOT_FOUND["en"])

        if len(matched) == 1:
            ev = matched[0]
            ev.deleted = True
            db.commit()
            nome = _event_name(ev)
            return _MSG_REMOVED[lang].format(nome=nome, name=nome, nombre=nome)

        # Vários candidatos: pedir para especificar
        lista = "\n".join(f"• {_event_name(e)}" for e in matched[:10])
        return _MSG_WHICH_ONE[lang].format(lista=lista)
    finally:
        db.close()
