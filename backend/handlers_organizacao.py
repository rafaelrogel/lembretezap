"""Handlers de organização pessoal: hábitos, metas, notas, projetos, templates."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from backend.database import SessionLocal
from backend.user_store import get_or_create_user, get_user_timezone, get_user_language
from backend.models_db import Habit, HabitCheck, Goal, Note, Project, List, ListItem, ListTemplate
from backend.streak import get_habit_streak, generate_streak_message, _default_streak_message
from backend.bookmark import generate_tags_and_category
from backend.sanitize import sanitize_string, MAX_LIST_NAME_LEN, MAX_ITEM_TEXT_LEN

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def _get_today_local(chat_id: str) -> str:
    """Data de hoje em timezone do user (YYYY-MM-DD)."""
    db = SessionLocal()
    try:
        tz_iana = get_user_timezone(db, chat_id)
        try:
            tz = ZoneInfo(tz_iana)
        except Exception:
            tz = ZoneInfo("UTC")
        return datetime.now(tz).strftime("%Y-%m-%d")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Hábitos
# ---------------------------------------------------------------------------

async def handle_habito(ctx: "HandlerContext", content: str) -> str | None:
    """/habito add Nome | /habito check Nome | /habito hoje | /habitos"""
    t = content.strip()
    if not t.lower().startswith("/habito"):
        return None
    rest = t[7:].strip()
    rest_lower = rest.lower()
    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)

        m = re.match(r"^add\s+(.+)$", rest, re.I)
        if m:
            name = sanitize_string(m.group(1).strip(), MAX_ITEM_TEXT_LEN)
            if not name:
                return "Use: /habito add Nome (ex: /habito add beber água)"
            existing = db.query(Habit).filter(Habit.user_id == user.id, Habit.name == name).first()
            if existing:
                return f"Hábito «{name}» já existe."
            db.add(Habit(user_id=user.id, name=name))
            db.commit()
            return f"✅ Hábito adicionado: {name}"

        m = re.match(r"^check\s+(.+)$", rest, re.I)
        if m:
            name = sanitize_string(m.group(1).strip(), MAX_ITEM_TEXT_LEN)
            habit = db.query(Habit).filter(Habit.user_id == user.id, Habit.name == name).first()
            if not habit:
                return f"Hábito «{name}» não encontrado. Use /habitos para listar."
            today = _get_today_local(ctx.chat_id)
            if db.query(HabitCheck).filter(HabitCheck.habit_id == habit.id, HabitCheck.check_date == today).first():
                return f"✅ {name} já marcado hoje."
            db.add(HabitCheck(habit_id=habit.id, check_date=today))
            db.commit()
            base_msg = f"✅ {name} marcado! 💪"
            streak = get_habit_streak(db, habit.id, today)
            if streak >= 2 and (ctx.scope_provider or ctx.main_provider) and (ctx.scope_model or ctx.main_model):
                user_lang = "pt-BR"
                try:
                    user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
                except Exception:
                    pass
                msg = await generate_streak_message(
                    ctx.scope_provider or ctx.main_provider,
                    ctx.scope_model or ctx.main_model or "",
                    name, streak, user_lang
                )
                if msg:
                    return f"{base_msg}\n\n{msg}"
                return f"{base_msg}\n\n{_default_streak_message(name, streak, user_lang)}"
            return base_msg

        if not rest or rest_lower in ("hoje", "ho") or rest_lower == "list":
            habits = db.query(Habit).filter(Habit.user_id == user.id).all()
            if not habits:
                return "Nenhum hábito. Use /habito add Nome para criar."
            if rest_lower == "list":
                return "📋 Hábitos: " + ", ".join(h.name for h in habits)
            today = _get_today_local(ctx.chat_id)
            lines = ["📋 **Hábitos hoje**"]
            for h in habits:
                c = db.query(HabitCheck).filter(HabitCheck.habit_id == h.id, HabitCheck.check_date == today).first()
                lines.append(f"{'✅' if c else '⬜'} {h.name}")
            return "\n".join(lines)

        return "Use: /habito add Nome | /habito check Nome | /habito hoje | /habitos"
    finally:
        db.close()


async def handle_habitos(ctx: "HandlerContext", content: str) -> str | None:
    """/habitos - atalho para listar hábitos."""
    if not content.strip().lower().startswith("/habitos"):
        return None
    return await handle_habito(ctx, "/habito list")


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
    """/meta add Nome até DD/MM | /metas"""
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
    """/metas - atalho."""
    if not content.strip().lower().startswith("/metas"):
        return None
    return await handle_meta(ctx, "/meta " + content.strip()[6:])


# ---------------------------------------------------------------------------
# Notas
# ---------------------------------------------------------------------------

async def handle_nota(ctx: "HandlerContext", content: str) -> str | None:
    """/nota texto | /notas [N]"""
    t = content.strip()
    if not t.lower().startswith("/nota"):
        return None
    rest = t[5:].strip()
    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)

        if not rest or rest.lower() == "s":
            notes = db.query(Note).filter(Note.user_id == user.id).order_by(Note.created_at.desc()).limit(10).all()
            if not notes:
                return "Nenhuma nota. Use /nota texto para anotar."
            lines = ["📝 **Notas recentes**"]
            for n in notes[:5]:
                prev = (n.text[:60] + "…") if len(n.text) > 60 else n.text
                lines.append(f"• {prev}")
            return "\n".join(lines)

        text = sanitize_string(rest, 2000, allow_newline=True)
        if not text:
            return "Use: /nota texto (ex: /nota ideia para o projeto)"
        db.add(Note(user_id=user.id, text=text))
        db.commit()
        return "✅ Nota guardada."
    finally:
        db.close()


async def handle_notas(ctx: "HandlerContext", content: str) -> str | None:
    """/notas - listar notas."""
    if not content.strip().lower().startswith("/notas"):
        return None
    return await handle_nota(ctx, "/nota " + content.strip()[6:])


# ---------------------------------------------------------------------------
# Projetos
# ---------------------------------------------------------------------------

async def handle_projeto(ctx: "HandlerContext", content: str) -> str | None:
    """/projeto add Nome | /projeto Nome add item | /projeto Nome | /projetos"""
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

        items = db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.done == False).order_by(ListItem.id).all()
        if not items:
            return f"Projeto «{proj_name}»: sem tarefas. Use /projeto {proj_name} add item"
        lines = [f"📁 **{proj_name}**"]
        for i in items:
            lines.append(f"{i.id}. {i.text}")
        return "\n".join(lines)
    finally:
        db.close()


async def handle_projetos(ctx: "HandlerContext", content: str) -> str | None:
    """/projetos - listar projetos."""
    if not content.strip().lower().startswith("/projetos"):
        return None
    return await handle_projeto(ctx, "/projeto " + content.strip()[9:])


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

async def handle_template(ctx: "HandlerContext", content: str) -> str | None:
    """/template add Nome item1, item2 | /template Nome usar | /templates"""
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
    """/templates - listar templates."""
    if not content.strip().lower().startswith("/templates"):
        return None
    return await handle_template(ctx, "/template " + content.strip()[10:])


# ---------------------------------------------------------------------------
# Bookmarks (Mimo: tags, categoria, busca semântica)
# ---------------------------------------------------------------------------

def _get_last_user_message(session_manager, session_key: str) -> str | None:
    """Última mensagem do user no histórico (excluindo a atual)."""
    if not session_manager:
        return None
    try:
        session = session_manager.get_or_create(session_key)
        msgs = getattr(session, "messages", []) or []
        for m in reversed(msgs):
            if (m.get("role") or "").strip().lower() == "user":
                c = (m.get("content") or "").strip()
                if c and not c.lower().startswith(("/save", "/bookmark", "/find", "/bookmarks")):
                    return c
    except Exception:
        pass
    return None


async def handle_save(ctx: "HandlerContext", content: str) -> str | None:
    """/save [descrição] ou /bookmark — guarda com tags e categoria geradas por Mimo."""
    t = content.strip()
    if not t.lower().startswith("/save") and not t.lower().startswith("/bookmark"):
        return None
    if t.lower().startswith("/bookmarks"):
        return None  # /bookmarks é outro handler
    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)
        user_lang = "pt-BR"
        try:
            from backend.user_store import get_user_language
            user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
        except Exception:
            pass

        content_to_save: str | None = None
        context: str | None = None

        if t.lower().startswith("/save"):
            rest = t[5:].strip()
            if rest:
                content_to_save = rest
            else:
                session_key = f"{ctx.channel}:{ctx.chat_id}"
                content_to_save = _get_last_user_message(ctx.session_manager, session_key)
        else:
            session_key = f"{ctx.channel}:{ctx.chat_id}"
            content_to_save = _get_last_user_message(ctx.session_manager, session_key)

        if not content_to_save or not content_to_save.strip():
            return "Use /save descrição (ex: /save receita lasanha espinafres) ou /bookmark (guarda a tua última mensagem)."

        if ctx.scope_provider and ctx.scope_model:
            session_key = f"{ctx.channel}:{ctx.chat_id}"
            try:
                session = ctx.session_manager.get_or_create(session_key) if ctx.session_manager else None
                if session and session.messages:
                    for m in reversed(session.messages):
                        if (m.get("role") or "").strip().lower() == "assistant":
                            context = (m.get("content") or "")[:300]
                            break
            except Exception:
                pass
            tags, category = await generate_tags_and_category(
                ctx.scope_provider, ctx.scope_model or "",
                content_to_save, context, user_lang,
            )
        else:
            tags, category = [], "outro"

        from backend.bookmark import save_bookmark
        b = save_bookmark(db, user.id, content_to_save, context, tags, category)
        tags_str = ", ".join(tags[:5]) if tags else ""
        return f"✅ Bookmark guardado.\n📌 «{content_to_save[:80]}{'…' if len(content_to_save) > 80 else ''}»\nTags: {tags_str or '-'} | Categoria: {category}"
    except ValueError as e:
        return str(e)
    finally:
        db.close()


async def handle_bookmark(ctx: "HandlerContext", content: str) -> str | None:
    """/bookmark — atalho para guardar última mensagem."""
    if not content.strip().lower().startswith("/bookmark") or content.strip().lower().startswith("/bookmarks"):
        return None
    return await handle_save(ctx, content)


async def handle_find(ctx: "HandlerContext", content: str) -> str | None:
    """/find "query" — busca semântica nos bookmarks (Mimo)."""
    t = content.strip()
    if not t.lower().startswith("/find"):
        return None
    rest = t[5:].strip().strip('"\'')
    if not rest:
        return "Use: /find \"aquela receita\" ou /find ideia app"
    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)
        from backend.bookmark import list_bookmarks, find_matching_bookmarks

        bookmarks = list_bookmarks(db, user.id)
        if not bookmarks:
            if ctx.main_provider and ctx.main_model:
                try:
                    from backend.locale import phone_to_default_language
                    user_lang = phone_to_default_language(ctx.chat_id)
                    from backend.user_store import get_user_language
                    user_lang = get_user_language(db, ctx.chat_id) or user_lang
                    if user_lang == "pt-BR":
                        return "Ainda não tens bookmarks. Usa /save ou /bookmark para guardar algo."
                    if user_lang == "en":
                        return "You have no bookmarks yet. Use /save or /bookmark to save something."
                    return "Ainda não tens bookmarks. Usa /save ou /bookmark para guardar algo."
                except Exception:
                    pass
            return "Ainda não tens bookmarks. Usa /save ou /bookmark para guardar algo."

        bk_list = []
        for b in bookmarks:
            try:
                tags = json.loads(b.tags_json) if b.tags_json else []
                bk_list.append({
                    "id": b.id,
                    "content": b.content,
                    "tags": ",".join(tags),
                    "category": b.category or "",
                })
            except Exception:
                bk_list.append({"id": b.id, "content": b.content, "tags": "", "category": b.category or ""})

        user_lang = "pt-BR"
        try:
            from backend.user_store import get_user_language
            user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
        except Exception:
            pass

        matched_ids: list[int] = []
        if ctx.scope_provider and ctx.scope_model:
            matched_ids = await find_matching_bookmarks(
                ctx.scope_provider, ctx.scope_model or "",
                rest, bk_list, user_lang,
            )

        if matched_ids:
            id_to_bk = {b.id: b for b in bookmarks}
            matched = [id_to_bk[i] for i in matched_ids if i in id_to_bk]
        else:
            query_lower = rest.lower()
            def _tags_list(bk):
                try:
                    return json.loads(bk.tags_json) if bk.tags_json else []
                except Exception:
                    return []
            matched = [b for b in bookmarks if query_lower in (b.content or "").lower()
                       or any(query_lower in t.lower() for t in _tags_list(b))]
            if not matched:
                if user_lang in ("pt-BR", "pt-PT"):
                    return f"Não encontrei bookmarks para «{rest[:50]}». Tenta /bookmarks para ver o que tens."
                if user_lang == "en":
                    return f"No bookmarks found for «{rest[:50]}». Try /bookmarks to see what you have."
                return f"Não encontrei bookmarks para «{rest[:50]}»."

        lines = ["📌 Encontrei:"]
        for b in matched[:5]:
            prev = (b.content[:70] + "…") if len(b.content) > 70 else b.content
            tags = []
            try:
                tags = json.loads(b.tags_json) if b.tags_json else []
            except Exception:
                pass
            tags_str = ", ".join(tags[:3]) if tags else ""
            lines.append(f"• «{prev}»" + (f" ({tags_str})" if tags_str else ""))
        return "\n".join(lines)
    finally:
        db.close()


async def handle_bookmarks(ctx: "HandlerContext", content: str) -> str | None:
    """/bookmarks — lista todos os bookmarks."""
    if not content.strip().lower().startswith("/bookmarks"):
        return None
    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)
        from backend.bookmark import list_bookmarks
        bks = list_bookmarks(db, user.id, limit=15)
        if not bks:
            return "Nenhum bookmark. Usa /save ou /bookmark para guardar."
        lines = ["📌 **Bookmarks**"]
        for b in bks:
            prev = (b.content[:50] + "…") if len(b.content) > 50 else b.content
            try:
                tags = json.loads(b.tags_json) if b.tags_json else []
                tags_str = ", ".join(tags[:2]) if tags else ""
            except Exception:
                tags_str = ""
            cat = f" | {b.category}" if b.category else ""
            lines.append(f"• {prev} {f'({tags_str})' if tags_str else ''}{cat}")
        return "\n".join(lines)
    finally:
        db.close()
