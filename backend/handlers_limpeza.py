"""Handlers para /limpeza — tarefas de limpeza da casa com rotação."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from backend.database import SessionLocal
from backend.user_store import get_or_create_user, get_user_timezone
from backend.models_db import HouseChoreTask, HouseChorePerson
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


def _get_limpeza_intro(lang: str = "pt-BR") -> str:
    """Mensagem de boas-vindas ao fluxo de limpeza (linguagem natural)."""
    if "pt-PT" in (lang or ""):
        return (
            "🧹 **Limpeza da casa**\n\n"
            "Posso ajudar a organizar as tarefas de limpeza com rotação entre pessoas. "
            "Por exemplo: cozinha semanalmente, banheiro quinzenalmente.\n\n"
            "**Como configurar:**\n"
            "• /limpeza add cozinha weekly sábado 9h — adiciona tarefa semanal\n"
            "• /limpeza add banheiro bi-weekly sábado 9h — quinzenal\n"
            "• /limpeza pessoas add João, Maria — define quem participa da rotação\n"
            "• /limpeza rotação on — ativa rotação entre as pessoas\n"
            "• /limpeza catálogo — ver todas as tarefas disponíveis\n\n"
            "Moras com alguém? Queres dividir e rotacionar as tarefas?"
        )
    return (
        "🧹 **Limpeza da casa**\n\n"
        "Posso ajudar a organizar as tarefas de limpeza com rotação entre pessoas. "
        "Por exemplo: cozinha semanalmente, banheiro quinzenalmente.\n\n"
        "**Como configurar:**\n"
        "• /limpeza add cozinha weekly sábado 9h — adiciona tarefa semanal\n"
        "• /limpeza add banheiro bi-weekly sábado 9h — quinzenal\n"
        "• /limpeza pessoas add João, Maria — define quem participa da rotação\n"
        "• /limpeza rotação on — ativa rotação entre as pessoas\n"
        "• /limpeza catálogo — ver todas as tarefas disponíveis\n\n"
        "Mora com alguém? Quer dividir e rotacionar as tarefas?"
    )


async def handle_limpeza(ctx: "HandlerContext", content: str) -> str | None:
    """
    /limpeza — tarefas de limpeza (weekly/bi-weekly) com rotação.
    Aceita NL: limpeza, «preciso limpar a casa», «limpar banheiro», etc.
    """
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip()
    # Linguagem natural: «preciso limpar a casa», «limpar banheiro», etc.
    if not t.lower().startswith("/limpeza") and _is_limpeza_nl_intent(t):
        try:
            from backend.user_store import get_user_language
            db = SessionLocal()
            try:
                user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
            finally:
                db.close()
        except Exception:
            user_lang = "pt-BR"
        return _get_limpeza_intro(user_lang)
    if not t.lower().startswith("/limpeza"):
        return None
    rest = t[8:].strip().lower()
    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)

        if not rest or rest == "help":
            return (
                "🧹 **Limpeza da casa**\n"
                "• /limpeza add cozinha weekly sábado 9h — adiciona tarefa semanal\n"
                "• /limpeza add banheiro bi-weekly sábado 9h — quinzenal\n"
                "• /limpeza pessoas add João, Maria — define quem participa da rotação\n"
                "• /limpeza rotação on — ativa rotação entre pessoas\n"
                "• /limpeza list — ver tarefas e pessoas\n"
                "• /limpeza remove cozinha — remove tarefa\n"
                "• /limpeza catálogo — ver tarefas disponíveis"
            )

        if rest == "list":
            tasks = db.query(HouseChoreTask).filter(HouseChoreTask.user_id == user.id).order_by(HouseChoreTask.id).all()
            persons = db.query(HouseChorePerson).filter(HouseChorePerson.user_id == user.id).order_by(HouseChorePerson.order_idx).all()
            lines = ["🧹 **Tarefas de limpeza**"]
            if not tasks:
                lines.append("Nenhuma tarefa. Use /limpeza add cozinha weekly sábado 9h")
            else:
                for tsk in tasks:
                    name = tsk.custom_name or get_chore_name(tsk.catalog_slug)
                    freq = "semanal" if tsk.frequency == "weekly" else "quinzenal"
                    dia = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"][tsk.weekday]
                    rot = " 🔄" if tsk.rotation_enabled else ""
                    lines.append(f"• {name} ({freq}, {dia} {tsk.time_hhmm}){rot}")
            if persons:
                lines.append("")
                lines.append("**Pessoas na rotação:** " + ", ".join(p.name for p in persons))
            return "\n".join(lines)

        if rest == "catálogo" or rest == "catalogo":
            by_cat = list_catalog_by_category()
            lines = ["🧹 **Catálogo de tarefas**", "Use: /limpeza add slug frequency dia hora", ""]
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
                return f"Tarefa «{slug}» não encontrada. Use /limpeza catálogo."
            freq = "weekly" if freq_raw in ("weekly", "semanal") else "bi-weekly"
            weekday = WEEKDAY_MAP.get(dia_raw.lower(), None)
            if weekday is None:
                return f"Dia «{dia_raw}» inválido. Ex.: segunda, sábado."
            time_hhmm = _parse_time_hhmm(time_raw)
            if not time_hhmm:
                return f"Hora «{time_raw}» inválida. Use 9h ou 09:00."
            existing = db.query(HouseChoreTask).filter(
                HouseChoreTask.user_id == user.id,
                HouseChoreTask.catalog_slug == slug_lower,
            ).first()
            if existing:
                return f"Tarefa «{get_chore_name(slug_lower)}» já existe."
            db.add(HouseChoreTask(
                user_id=user.id,
                catalog_slug=slug_lower,
                frequency=freq,
                weekday=weekday,
                time_hhmm=time_hhmm,
            ))
            db.commit()
            return f"✅ {get_chore_name(slug_lower)} adicionada ({freq}, {dia_raw} {time_hhmm})"

        m = re.match(r"^remove\s+(.+)$", rest)
        if m:
            slug = m.group(1).strip().lower().replace("-", "_")
            task = db.query(HouseChoreTask).filter(
                HouseChoreTask.user_id == user.id,
                HouseChoreTask.catalog_slug == slug,
            ).first()
            if not task:
                return f"Tarefa «{slug}» não encontrada."
            db.delete(task)
            db.commit()
            return f"✅ Tarefa removida."

        m = re.match(r"^rota[cç][aã]o\s+(on|off|sim|n[aã]o)$", rest)
        if m:
            on = m.group(1).lower() in ("on", "sim")
            tasks = db.query(HouseChoreTask).filter(HouseChoreTask.user_id == user.id).all()
            for tsk in tasks:
                tsk.rotation_enabled = on
            db.commit()
            persons = db.query(HouseChorePerson).filter(HouseChorePerson.user_id == user.id).count()
            if on and persons == 0:
                return "✅ Rotação ativada. Adicione pessoas: /limpeza pessoas add João, Maria"
            return f"✅ Rotação {'ativada' if on else 'desativada'}."

        m = re.match(r"^pessoas\s+add\s+(.+)$", rest)
        if m:
            names = [n.strip() for n in m.group(1).split(",") if n.strip()]
            if not names:
                return "Use: /limpeza pessoas add João, Maria, Pedro"
            max_idx = db.query(HouseChorePerson).filter(HouseChorePerson.user_id == user.id).count()
            for i, name in enumerate(names):
                if len(name) > 60:
                    name = name[:60]
                db.add(HouseChorePerson(user_id=user.id, name=name, order_idx=max_idx + i))
            db.commit()
            return f"✅ Pessoas adicionadas: {', '.join(names)}"

        if rest == "pessoas":
            persons = db.query(HouseChorePerson).filter(HouseChorePerson.user_id == user.id).order_by(HouseChorePerson.order_idx).all()
            if not persons:
                return "Nenhuma pessoa. Use /limpeza pessoas add João, Maria"
            return "**Pessoas na rotação:** " + ", ".join(p.name for p in persons)

        return None
    finally:
        db.close()
