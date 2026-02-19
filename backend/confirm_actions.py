"""Ações perigosas com confirmação (1=sim 2=não): exportar, deletar_tudo."""

from backend.handler_context import HandlerContext, _reply_confirm_prompt


async def handle_exportar(ctx: HandlerContext, content: str) -> str | None:
    """/exportar: confirma? 1=sim 2=não. Aceita NL: exportar, export."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/exportar"):
        return None
    from backend.confirmations import set_pending
    set_pending(ctx.channel, ctx.chat_id, "exportar", {})
    return _reply_confirm_prompt("📤 Queres exportar todas as tuas listas e lembretes?")


async def handle_deletar_tudo(ctx: HandlerContext, content: str) -> str | None:
    """/deletar_tudo: confirma? 1=sim 2=não. Aceita NL: apagar tudo, deletar tudo."""
    import re
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    if not re.match(r"^/deletar[_\s]?tudo\s*$", content.strip(), re.I):
        return None
    from backend.confirmations import set_pending
    set_pending(ctx.channel, ctx.chat_id, "deletar_tudo", {})
    return _reply_confirm_prompt(
        "⚠️ Apagar TODOS os dados? (listas, lembretes, eventos) — Esta ação não tem volta."
    )


def _is_recipe_list_confirm(content: str) -> bool:
    """True se o user confirma criar lista de compras (sim, faça isso, pode, etc.)."""
    import unicodedata
    t = (content or "").strip().lower()
    if not t or len(t) > 60:
        return False
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")  # remove acentos para match
    affirms = (
        "sim", "s", "yes", "y", "pode", "faca isso", "faz isso",
        "quero", "pode ser", "bora", "claro", "ok", "beleza", "vale", "valeu",
        "do it", "please", "quero sim", "pode criar", "cria", "criar",
        "faz", "pode fazer", "faz a lista", "faca a lista",
    )
    t_norm = t.rstrip(".!?")
    return t in affirms or t_norm in affirms


def _is_recipe_list_cancel(content: str) -> bool:
    """True se o user cancela (não, cancelar, etc.)."""
    t = (content or "").strip().lower()
    return t in ("não", "nao", "n", "no", "cancelar", "cancel", "nope")


def _parse_list_or_events_choice(content: str) -> str | None:
    """Retorna 'lista', 'lembretes', 'os dois' ou None."""
    t = (content or "").strip().lower()
    if not t or len(t) > 50:
        return None
    if t in ("lista", "list", "lista de afazeres", "to-do", "afazeres", "todo"):
        return "lista"
    if t in ("lembretes", "lembrete", "eventos", "evento", "reminders", "reminder"):
        return "lembretes"
    if t in ("os dois", "ambos", "os dois quero", "lista e lembretes"):
        return "os dois"
    if "lista" in t and "lembrete" not in t and "evento" not in t:
        return "lista"
    if ("lembrete" in t or "evento" in t) and "lista" not in t:
        return "lembretes"
    if "os dois" in t or ("lista" in t and ("lembrete" in t or "evento" in t)):
        return "os dois"
    return None


async def resolve_confirm(ctx: HandlerContext, content: str) -> str | None:
    """Resolve confirmação pendente (1=sim 2=não). Chamado primeiro no router."""
    from backend.confirmations import get_pending, clear_pending, is_confirm_reply, is_confirm_yes, is_confirm_no
    pending = get_pending(ctx.channel, ctx.chat_id)

    # Lista vs lembretes (resposta a "lista / lembretes / os dois?")
    if pending and pending.get("action") == "list_or_events_choice":
        choice = _parse_list_or_events_choice(content)
        if choice:
            clear_pending(ctx.channel, ctx.chat_id)
            items = (pending.get("payload") or {}).get("items") or []
            if choice == "lista":
                if items and ctx.list_tool:
                    ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
                    for it in items:
                        await ctx.list_tool.execute(action="add", list_name="hoje", item_text=it)
                    return f"✅ Lista *hoje* criada com {len(items)} afazeres. Usa /list hoje para ver."
                return "Nenhum item para adicionar."
            if choice == "lembretes":
                return (
                    "Para lembretes, podes usar /lembrete para cada atividade com horário. "
                    "Ex.: /lembrete ir à escola amanhã 8h. Ou diz-me quando queres ser lembrado e eu ajudo."
                )
            if choice == "os dois":
                if items and ctx.list_tool:
                    ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
                    for it in items:
                        await ctx.list_tool.execute(action="add", list_name="hoje", item_text=it)
                    return (
                        f"✅ Lista *hoje* criada com {len(items)} itens. "
                        "Para lembretes: usa /lembrete para cada um (ex.: /lembrete ir à escola amanhã 8h) ou diz quando queres ser lembrado."
                    )
                return "Nenhum item para adicionar."
        return None

    if pending and pending.get("action") == "create_shopping_list_from_recipe":
        if _is_recipe_list_confirm(content) or is_confirm_yes(content):
            clear_pending(ctx.channel, ctx.chat_id)
            payload = pending.get("payload") or {}
            ingredients = payload.get("ingredients") or []
            list_name = payload.get("list_name") or "compras_receita"
            if ingredients and ctx.list_tool:
                ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
                for item in ingredients:
                    await ctx.list_tool.execute(action="add", list_name=list_name, item_text=item)
                lines = [f"Lista criada! 🛒 *{list_name}* com {len(ingredients)} itens baseados na receita:"]
                for i, it in enumerate(ingredients[:15], 1):
                    lines.append(f"{i}. {it}")
                if len(ingredients) > 15:
                    lines.append(f"  _+{len(ingredients) - 15} mais_")
                return "\n".join(lines)
            try:
                from backend.user_store import get_user_language
                from backend.database import SessionLocal
                db = SessionLocal()
                try:
                    lang = get_user_language(db, ctx.chat_id) or "pt-BR"
                    msg = "Não consegui extrair os ingredientes. Tenta de novo com outra receita." if lang in ("pt-BR", "pt-PT", "es") else "Could not extract ingredients. Try again with another recipe."
                    return msg
                finally:
                    db.close()
            except Exception:
                pass
            return "Não consegui extrair os ingredientes. Tenta de novo com outra receita."
        if _is_recipe_list_cancel(content) or is_confirm_no(content):
            clear_pending(ctx.channel, ctx.chat_id)
            return "Ok, lista de compras cancelada."
    # Data no passado: agendar para o ano que vem se confirmar
    if pending and pending.get("action") == "date_past_next_year":
        if is_confirm_no(content):
            clear_pending(ctx.channel, ctx.chat_id)
            return "Ok, não agendei. Quando quiseres, diz a data e hora de novo."
        if is_confirm_yes(content):
            clear_pending(ctx.channel, ctx.chat_id)
            payload = pending.get("payload") or {}
            in_sec = payload.get("in_seconds")
            msg_text = (payload.get("message") or "").strip()
            if in_sec and in_sec > 0 and msg_text and ctx.cron_tool:
                ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
                result = await ctx.cron_tool.execute(
                    action="add",
                    message=msg_text,
                    in_seconds=in_sec,
                    has_deadline=bool(payload.get("has_deadline")),
                )
                from backend.locale import REMINDER_DATE_PAST_SCHEDULED
                try:
                    from backend.user_store import get_user_language
                    from backend.database import SessionLocal
                    db = SessionLocal()
                    try:
                        lang = get_user_language(db, ctx.chat_id) or "pt-BR"
                        scheduled_msg = REMINDER_DATE_PAST_SCHEDULED.get(lang, REMINDER_DATE_PAST_SCHEDULED["pt-BR"])
                    finally:
                        db.close()
                    return f"{scheduled_msg}\n\n{result}" if result else scheduled_msg
                except Exception:
                    return result or REMINDER_DATE_PAST_SCHEDULED.get("pt-BR", "Registado para o ano que vem. ✨")
            return "Não consegui agendar. Tenta de novo com a data e hora."
        return None

    if not is_confirm_reply(content):
        return None
    if not pending:
        return None
    clear_pending(ctx.channel, ctx.chat_id)
    action = pending.get("action")
    if action == "exportar":
        if is_confirm_no(content):
            return "❌ Exportação cancelada."
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_or_create_user
            from backend.models_db import List, ListItem
            db = SessionLocal()
            try:
                user = get_or_create_user(db, ctx.chat_id)
                lists = db.query(List).filter(List.user_id == user.id).all()
                lines = []
                for lst in lists:
                    items = db.query(ListItem).filter(ListItem.list_id == lst.id).all()
                    lines.append(f"[{lst.name}]")
                    for i in items:
                        lines.append(f"  - {i.text}" + (" (feito)" if i.done else ""))
                return "📤 Exportação:\n" + "\n".join(lines) if lines else "📭 Nada para exportar."
            finally:
                db.close()
        except Exception as e:
            return f"Erro ao exportar: {e}"
    if action == "deletar_tudo":
        if is_confirm_no(content):
            return "✅ Cancelado. Nenhum dado foi apagado."
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_or_create_user
            from backend.models_db import List, ListItem, Event
            db = SessionLocal()
            try:
                user = get_or_create_user(db, ctx.chat_id)
                for lst in db.query(List).filter(List.user_id == user.id).all():
                    db.query(ListItem).filter(ListItem.list_id == lst.id).delete()
                    db.delete(lst)
                db.query(Event).filter(Event.user_id == user.id).delete()
                db.commit()
                return "🗑️ Todos os teus dados foram apagados."
            finally:
                db.close()
        except Exception as e:
            return f"Erro ao apagar: {e}"
    if action == "completion_confirmation":
        payload = pending.get("payload") or {}
        job_id = payload.get("job_id")
        completed_job_id = payload.get("completed_job_id") or job_id
        if is_confirm_no(content):
            return "Ok, o lembrete mantém-se. Reage com 👍 quando terminares."
        if is_confirm_yes(content):
            if ctx.cron_service and job_id:
                ctx.cron_service.remove_job_and_deadline_followups(job_id)
                ctx.cron_service.trigger_dependents(completed_job_id)
                return "✅ Marcado como feito!"
            return "Ocorreu um erro. Tenta reagir com 👍 novamente ao lembrete."
        return None

    if action == "nuke_all":
        lang = (pending.get("payload") or {}).get("lang", "pt-BR")
        from backend.settings_handlers import _NUKE_CANCELLED_MSGS, _NUKE_DONE_MSGS
        if is_confirm_no(content):
            return _NUKE_CANCELLED_MSGS.get(lang, _NUKE_CANCELLED_MSGS["pt-BR"])
        # Apaga tudo!
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_or_create_user, clear_onboarding_data
            from backend.models_db import List, ListItem, Event

            db = SessionLocal()
            try:
                user = get_or_create_user(db, ctx.chat_id)
                # 1. Apagar itens e listas
                for lst in db.query(List).filter(List.user_id == user.id).all():
                    db.query(ListItem).filter(ListItem.list_id == lst.id).delete()
                    db.delete(lst)
                # 2. Apagar eventos
                db.query(Event).filter(Event.user_id == user.id).delete()
                # 3. Limpar dados de onboarding (nome, cidade, tz voltará ao padrão)
                clear_onboarding_data(db, ctx.chat_id)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            return f"Erro ao apagar dados: {exc}"

        # 4. Apagar cron jobs do utilizador
        if ctx.cron_service:
            try:
                jobs = ctx.cron_service.list_jobs(include_disabled=True)
                for job in jobs:
                    if getattr(job, "to", None) == ctx.chat_id or getattr(job, "channel", None) and getattr(job, "to", None) == ctx.chat_id:
                        ctx.cron_service.remove_job(job.id)
            except Exception:
                pass

        # 5. Limpar sessão/memória da conversa
        if ctx.session_manager:
            try:
                key = f"{ctx.channel}:{ctx.chat_id}"
                session = ctx.session_manager.get_or_create(key)
                # Limpar metadata de onboarding e fluxos
                session.metadata.clear()
                ctx.session_manager.save(session)
            except Exception:
                pass

        return _NUKE_DONE_MSGS.get(lang, _NUKE_DONE_MSGS["pt-BR"])

    return None
