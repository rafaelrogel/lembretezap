"""Handlers para /limpeza — tarefas de limpeza da casa com rotação."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from backend.database import SessionLocal
from backend.user_store import get_or_create_user, get_user_timezone, get_user_language
from backend.models_db import HouseChoreTask, HouseChorePerson
import backend.locale as locale
from backend.house_chores_catalog import (
    CHORE_CATALOG,
    get_chore_name,
    list_catalog_by_category,
    CATEGORY_NAMES,
)

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

# Linguagem natural: limpar casa, banheiro, quarto, etc. — ativa fluxo de limpeza
_LIMPEZA_NL_PATTERNS = (
    r"preciso\s+limpar", r"quero\s+limpar", r"precisamos\s+limpar",
    r"limpar\s+(?:a\s+)?casa", r"limpar\s+(?:o\s+)?banheiro", r"limpar\s+(?:o\s+)?quarto",
    r"limpar\s+(?:a\s+)?sala", r"limpar\s+(?:a\s+)?cozinha", r"limpar\s+quintal",
    r"limpar\s+(?:a\s+)?varanda", r"limpar\s+janelas", r"limpar\s+espelhos",
    r"arrumar\s+(?:a\s+)?casa", r"aspirar\s+(?:a\s+)?casa", r"varrer\s+(?:a\s+)?casa",
    r"tarefas\s+de\s+limpeza", r"limpeza\s+(?:da\s+)?casa", r"limpeza\s+dom[eé]stica",
    r"divis[aã]o\s+(?:das\s+)?tarefas", r"rotacionar\s+tarefas",
)
def _is_limpeza_nl_intent(content: str) -> bool:
    """True se a mensagem indica intenção de limpeza da casa (sem /limpeza)."""
    t = (content or "").strip().lower()
    if not t or len(t) < 6 or t.startswith("/"):
        return False
    
    # Se a frase já contém detalhes ou frequência, não travar no intro,
    # deixar ir para o LLM que consegue processar o pedido específico.
    # Suporte para 4 idiomas: PT, EN, ES
    # Frequências e termos recorrentes (PT, EN, ES) para evitar capturar lembretes 
    # específicos no fluxo genérico de introdução à limpeza.
    frequency_words = (
        "semanal", "weekly", "quinzenal", "bi-weekly", "todo", "toda", "todos", "todas", "sempre",
        "quincenal", "diario", "mensual", "cada", "siempre", "diariamente",
        "every", "each", "always", "daily", "monthly", "yearly", "annually",
        "todas as", "todos os", "cada", "quaisquer", "cualquier", "cualquiera"
    )
    if any(word in t for word in frequency_words):
        return False
        
    return any(re.search(p, t) for p in _LIMPEZA_NL_PATTERNS)


WEEKDAY_MAP = {
    "seg": 0, "segunda": 0, "segunda-feira": 0,
    "ter": 1, "terca": 1, "terça": 1, "terça-feira": 1,
    "qua": 2, "quarta": 2, "quarta-feira": 2,
    "qui": 3, "quinta": 3, "quinta-feira": 3,
    "sex": 4, "sexta": 4, "sexta-feira": 4,
    "sab": 5, "sáb": 5, "sabado": 5, "sábado": 5,
    "dom": 6, "domingo": 6,
}


def _parse_time_hhmm(s: str) -> str | None:
    """Valida HH:MM ou H:MM. Retorna "HH:MM" ou None."""
    s = (s or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if m:
        h, m_ = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= m_ <= 59:
            return f"{h:02d}:{m_:02d}"
    m = re.match(r"^(\d{1,2})h(\d{2})?$", s.replace(" ", ""), re.I)
    if m:
        h, m_ = int(m.group(1)), int(m.group(2) or 0)
        if 0 <= h <= 23 and 0 <= m_ <= 59:
            return f"{h:02d}:{m_:02d}"
    return None




async def handle_limpeza(ctx: "HandlerContext", content: str) -> str | None:
    """
    /limpeza — tarefas de limpeza (weekly/bi-weekly) com rotação.
    Aceita NL: limpeza, "preciso limpar a casa", "limpar banheiro", etc.
    """
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip()
    # Linguagem natural: "preciso limpar a casa", "limpar banheiro", etc.
    if not t.lower().startswith("/limpeza") and _is_limpeza_nl_intent(t):
        db = SessionLocal()
        try:
            user_lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            return locale.LIMPEZA_INTRO.get(user_lang, locale.LIMPEZA_INTRO["en"])
        finally:
            db.close()
    if not t.lower().startswith("/limpeza"):
        return None
    rest = t[8:].strip().lower()
    db = SessionLocal()
    try:
        user_lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
        user = get_or_create_user(db, ctx.chat_id)

        if not rest or rest == "help":
            return locale.LIMPEZA_HELP.get(user_lang, locale.LIMPEZA_HELP["en"])

        if rest == "list":
            tasks = db.query(HouseChoreTask).filter(HouseChoreTask.user_id == user.id).order_by(HouseChoreTask.id).all()
            persons = db.query(HouseChorePerson).filter(HouseChorePerson.user_id == user.id).order_by(HouseChorePerson.order_idx).all()
            lines = [locale.LIMPEZA_LIST_HEADER.get(user_lang, locale.LIMPEZA_LIST_HEADER["en"])]
            if not tasks:
                lines.append(locale.LIMPEZA_NO_TASKS.get(user_lang, locale.LIMPEZA_NO_TASKS["en"]))
            else:
                for tsk in tasks:
                    name = tsk.custom_name or get_chore_name(tsk.catalog_slug)
                    freq = "semanal" if tsk.frequency == "weekly" else "quinzenal"
                    dia = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"][tsk.weekday]
                    rot = " 🔄" if tsk.rotation_enabled else ""
                    lines.append(f"• {name} ({freq}, {dia} {tsk.time_hhmm}){rot}")
            if persons:
                lines.append("")
                lines.append(locale.LIMPEZA_PERSONS_HEADER.get(user_lang, locale.LIMPEZA_PERSONS_HEADER["en"]) + ", ".join(p.name for p in persons))
            return "\n".join(lines)

        if rest == "catálogo" or rest == "catalogo":
            by_cat = list_catalog_by_category()
            lines = [
                locale.LIMPEZA_CATALOG_HEADER.get(user_lang, locale.LIMPEZA_CATALOG_HEADER["en"]),
                locale.LIMPEZA_CATALOG_FOOTER.get(user_lang, locale.LIMPEZA_CATALOG_FOOTER["en"]),
                ""
            ]
            for cat, items in sorted(by_cat.items(), key=lambda x: x[0]):
                cat_name = CATEGORY_NAMES.get(cat, cat)
                lines.append(f"**{cat_name}**")
                for slug, _ in items[:8]:
                    lines.append(f"  • {slug}")
                if len(items) > 8:
                    lines.append(f"  ... e mais {len(items)-8}")
                lines.append("")
            return "\n".join(lines).strip()

        m = re.match(r"^add\s+(\S+)\s+(weekly|bi-weekly|semanal|quinzenal)\s+(\S+)\s+(\S+)$", rest)
        if m:
            slug, freq_raw, dia_raw, time_raw = m.group(1), m.group(2), m.group(3), m.group(4)
            slug_lower = slug.lower().replace("-", "_")
            if slug_lower not in CHORE_CATALOG:
                return locale.LIMPEZA_TASK_NOT_FOUND.get(user_lang, locale.LIMPEZA_TASK_NOT_FOUND["en"]).format(slug=slug)
            freq = "weekly" if freq_raw in ("weekly", "semanal") else "bi-weekly"
            weekday = WEEKDAY_MAP.get(dia_raw.lower(), None)
            if weekday is None:
                return locale.LIMPEZA_DAY_INVALID.get(user_lang, locale.LIMPEZA_DAY_INVALID["en"]).format(day=dia_raw)
            time_hhmm = _parse_time_hhmm(time_raw)
            if not time_hhmm:
                return locale.LIMPEZA_TIME_INVALID.get(user_lang, locale.LIMPEZA_TIME_INVALID["en"]).format(time=time_raw)
            existing = db.query(HouseChoreTask).filter(
                HouseChoreTask.user_id == user.id,
                HouseChoreTask.catalog_slug == slug_lower,
            ).first()
            if existing:
                return locale.LIMPEZA_TASK_EXISTS.get(user_lang, locale.LIMPEZA_TASK_EXISTS["en"]).format(name=get_chore_name(slug_lower))
            db.add(HouseChoreTask(
                user_id=user.id,
                catalog_slug=slug_lower,
                weekday=weekday,
                time_hhmm=time_hhmm,
            ))
            db.commit()
            return locale.LIMPEZA_TASK_ADDED.get(user_lang, locale.LIMPEZA_TASK_ADDED["en"]).format(
                name=get_chore_name(slug_lower),
                freq=freq,
                dia=dia_raw,
                time=time_hhmm
            )

        m = re.match(r"^remove\s+(.+)$", rest)
        if m:
            slug = m.group(1).strip().lower().replace("-", "_")
            task = db.query(HouseChoreTask).filter(
                HouseChoreTask.user_id == user.id,
                HouseChoreTask.catalog_slug == slug,
            ).first()
            if not task:
                return locale.LIMPEZA_TASK_NOT_FOUND.get(user_lang, locale.LIMPEZA_TASK_NOT_FOUND["en"]).format(slug=slug)
            db.delete(task)
            db.commit()
            return locale.LIMPEZA_TASK_REMOVED.get(user_lang, locale.LIMPEZA_TASK_REMOVED["en"])

        m = re.match(r"^rota[cç][aã]o\s+(on|off|sim|n[aã]o)$", rest)
        if m:
            on = m.group(1).lower() in ("on", "sim")
            tasks = db.query(HouseChoreTask).filter(HouseChoreTask.user_id == user.id).all()
            for tsk in tasks:
                tsk.rotation_enabled = on
            db.commit()
            persons_count = db.query(HouseChorePerson).filter(HouseChorePerson.user_id == user.id).count()
            if on and persons_count == 0:
                return locale.LIMPEZA_ROTATION_ON_NO_PEOPLE.get(user_lang, locale.LIMPEZA_ROTATION_ON_NO_PEOPLE["en"])
            status_word = "ativada" if on else "desativada"
            return locale.LIMPEZA_ROTATION_STATUS.get(user_lang, locale.LIMPEZA_ROTATION_STATUS["en"]).format(status=status_word)

        m = re.match(r"^pessoas\s+add\s+(.+)$", rest)
        if m:
            names = [n.strip() for n in m.group(1).split(",") if n.strip()]
            if not names:
                return locale.LIMPEZA_NO_PERSONS.get(user_lang, locale.LIMPEZA_NO_PERSONS["en"])
            max_idx = db.query(HouseChorePerson).filter(HouseChorePerson.user_id == user.id).count()
            for i, name in enumerate(names):
                if len(name) > 60:
                    name = name[:60]
                db.add(HouseChorePerson(user_id=user.id, name=name, order_idx=max_idx + i))
            db.commit()
            return locale.LIMPEZA_PERSONS_ADDED.get(user_lang, locale.LIMPEZA_PERSONS_ADDED["en"]).format(names=", ".join(names))

        if rest == "pessoas":
            persons = db.query(HouseChorePerson).filter(HouseChorePerson.user_id == user.id).order_by(HouseChorePerson.order_idx).all()
            if not persons:
                return locale.LIMPEZA_NO_PERSONS.get(user_lang, locale.LIMPEZA_NO_PERSONS["en"])
            header = locale.LIMPEZA_PERSONS_HEADER.get(user_lang, locale.LIMPEZA_PERSONS_HEADER["en"])
            return header + ", ".join(p.name for p in persons)

        return None
    finally:
        db.close()
