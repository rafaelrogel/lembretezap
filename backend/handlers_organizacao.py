"""Handlers de organização pessoal: hábitos, metas, notas, projetos, templates."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING

from backend.database import SessionLocal
from backend.user_store import get_or_create_user
from backend.models_db import Goal, Project, List, ListItem, ListTemplate
from backend.sanitize import sanitize_string, MAX_LIST_NAME_LEN, MAX_ITEM_TEXT_LEN

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


# ---------------------------------------------------------------------------
# Metas
# ---------------------------------------------------------------------------

def _parse_deadline(text: str):
    """Extrai prazo de 'Nome até DD/MM' ou 'Nome até 31/12/2026'."""
    text = (text or "").strip()
    m = re.search(r"\s+at[eé]\s+(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\s*$", text, re.I)
    if not m:
        return None, text
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else None
    name = text[: m.start()].strip()
    if not year:
        from datetime import datetime
        year = datetime.now().year
    try:
        deadline = datetime(year, month, day)
        return deadline, name
    except Exception:
        return None, text


async def handle_meta(ctx: "HandlerContext", content: str) -> str | None:
    """/meta add Nome até DD/MM | /metas. Aceita NL: meta, metas, objetivo(s)."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip()
    if not t.lower().startswith("/meta"):
        return None
    rest = t[5:].strip()
    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)

        if not rest or rest.lower() == "s":
            goals = db.query(Goal).filter(Goal.user_id == user.id, Goal.done == False).order_by(Goal.deadline).all()
            if not goals:
                return "Nenhuma meta ativa. Use /meta add Nome até DD/MM"
            lines = ["🎯 **Metas**"]
            for g in goals:
                dl = g.deadline.strftime("%d/%m/%Y") if g.deadline else "sem prazo"
                lines.append(f"• {g.name} (até {dl})")
            return "\n".join(lines)

        m = re.match(r"^add\s+(.+)$", rest, re.I)
        if m:
            full = m.group(1).strip()
            deadline, name = _parse_deadline(full)
            name = sanitize_string(name, MAX_ITEM_TEXT_LEN)
            if not name:
                return "Use: /meta add Nome até DD/MM (ex: /meta add correr 10km até 31/12)"
            g = Goal(user_id=user.id, name=name, deadline=deadline)
            db.add(g)
            db.commit()
            dl_str = deadline.strftime("%d/%m/%Y") if deadline else ""
            return f"✅ Meta adicionada: {name}" + (f" (até {dl_str})" if dl_str else "")

        return "Use: /meta add Nome até DD/MM | /metas"
    finally:
        db.close()


async def handle_metas(ctx: "HandlerContext", content: str) -> str | None:
    """/metas - atalho. Aceita NL: metas, objetivos."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/metas"):
        return None
    return await handle_meta(ctx, "/meta " + content.strip()[6:])


# ---------------------------------------------------------------------------
# Projetos
# ---------------------------------------------------------------------------

async def handle_projeto(ctx: "HandlerContext", content: str) -> str | None:
    """/projeto add Nome | /projeto Nome. Aceita NL: projeto, project."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip()
    if not t.lower().startswith("/projeto"):
        return None
    rest = t[8:].strip()
    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)

        if not rest or rest.lower() == "s":
            projects = db.query(Project).filter(Project.user_id == user.id).all()
            if not projects:
                return "Nenhum projeto. Use /projeto add Nome"
            return "📁 Projetos: " + ", ".join(p.name for p in projects)

        m = re.match(r"^add\s+(.+)$", rest, re.I)
        if m:
            name = sanitize_string(m.group(1).strip(), MAX_LIST_NAME_LEN)
            if not name:
                return "Use: /projeto add Nome (ex: /projeto add Casa)"
            existing = db.query(Project).filter(Project.user_id == user.id, Project.name == name).first()
            if existing:
                return f"Projeto «{name}» já existe."
            proj = Project(user_id=user.id, name=name)
            db.add(proj)
            db.flush()
            lst = List(user_id=user.id, name=name, project_id=proj.id)
            db.add(lst)
            db.commit()
            return f"✅ Projeto criado: {name} (usa /list {name} add item para tarefas)"

        # /projeto Nome add item ou /projeto Nome
        parts = rest.split(None, 2)
        proj_name = sanitize_string(parts[0], MAX_LIST_NAME_LEN)
        proj = db.query(Project).filter(Project.user_id == user.id, Project.name == proj_name).first()
        if not proj:
            return f"Projeto «{proj_name}» não encontrado. Use /projetos"
        lst = db.query(List).filter(List.user_id == user.id, List.project_id == proj.id).first()
        if not lst:
            lst = List(user_id=user.id, name=proj_name, project_id=proj.id)
            db.add(lst)
            db.flush()

        if len(parts) >= 3 and parts[1].lower() == "add":
            item_text = sanitize_string(parts[2], MAX_ITEM_TEXT_LEN)
            if not item_text:
                return "Use: /projeto Nome add item"
            item = ListItem(list_id=lst.id, text=item_text)
            db.add(item)
            db.commit()
            return f"✅ Adicionado a «{proj_name}»: {item_text} (id: {item.id})"

        items = (
            db.query(ListItem)
            .filter(ListItem.list_id == lst.id, ListItem.done == False)
            .order_by(ListItem.position, ListItem.id)
            .all()
        )
        if not items:
            return f"Projeto «{proj_name}»: sem tarefas. Use /projeto {proj_name} add item"
        lines = [f"📁 **{proj_name}**"]
        for i in items:
            lines.append(f"{i.id}. {i.text}")
        return "\n".join(lines)
    finally:
        db.close()


async def handle_projetos(ctx: "HandlerContext", content: str) -> str | None:
    """/projetos - listar projetos. Aceita NL: projetos, projects."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/projetos"):
        return None
    return await handle_projeto(ctx, "/projeto " + content.strip()[9:])


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

async def handle_template(ctx: "HandlerContext", content: str) -> str | None:
    """/template add Nome item1, item2 | /template Nome usar. Aceita NL: template, modelo."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip()
    if not t.lower().startswith("/template"):
        return None
    rest = t[9:].strip()
    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)

        if not rest or rest.lower() == "s":
            templates = db.query(ListTemplate).filter(ListTemplate.user_id == user.id).all()
            if not templates:
                return "Nenhum template. Use /template add Nome item1, item2"
            return "📋 Templates: " + ", ".join(t.name for t in templates)

        m = re.match(r"^add\s+(\S+)\s+(.+)$", rest, re.I)
        if m:
            name = sanitize_string(m.group(1), MAX_LIST_NAME_LEN)
            raw_items = m.group(2).strip()
            items = [sanitize_string(x.strip(), MAX_ITEM_TEXT_LEN) for x in re.split(r"[,;]", raw_items) if x.strip()]
            items = items[:50]
            if not name or not items:
                return "Use: /template add Nome item1, item2 (ex: /template add mercado leite, pão, café)"
            existing = db.query(ListTemplate).filter(ListTemplate.user_id == user.id, ListTemplate.name == name).first()
            if existing:
                existing.items_json = json.dumps(items)
                db.commit()
                return f"✅ Template «{name}» atualizado ({len(items)} itens)"
            db.add(ListTemplate(user_id=user.id, name=name, items_json=json.dumps(items)))
            db.commit()
            return f"✅ Template criado: {name} ({len(items)} itens). Use /template {name} usar"

        m = re.match(r"^(\S+)\s+usar\s*$", rest, re.I)
        if m:
            name = sanitize_string(m.group(1), MAX_LIST_NAME_LEN)
            tmpl = db.query(ListTemplate).filter(ListTemplate.user_id == user.id, ListTemplate.name == name).first()
            if not tmpl:
                return f"Template «{name}» não encontrado."
            try:
                items = json.loads(tmpl.items_json)
            except Exception:
                items = []
            lst = db.query(List).filter(List.user_id == user.id, List.name == name).first()
            if not lst:
                lst = List(user_id=user.id, name=name)
                db.add(lst)
                db.flush()
            added = 0
            for item_text in items:
                if item_text:
                    db.add(ListItem(list_id=lst.id, text=item_text))
                    added += 1
            db.commit()
            return f"✅ Lista «{name}» criada com {added} itens."

        return "Use: /template add Nome item1, item2 | /template Nome usar | /templates"
    finally:
        db.close()


async def handle_templates(ctx: "HandlerContext", content: str) -> str | None:
    """/templates - listar templates. Aceita NL: templates, modelos."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/templates"):
        return None
    return await handle_template(ctx, "/template " + content.strip()[10:])


