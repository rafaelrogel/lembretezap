"""Ações perigosas com confirmação (1=sim 2=não): exportar, deletar_tudo."""

from backend.handler_context import HandlerContext, _reply_confirm_prompt


async def handle_exportar(ctx: HandlerContext, content: str) -> str | None:
    """/exportar: confirma? 1=sim 2=não."""
    if not content.strip().lower().startswith("/exportar"):
        return None
    from backend.confirmations import set_pending
    set_pending(ctx.channel, ctx.chat_id, "exportar", {})
    return _reply_confirm_prompt("📤 Queres exportar todas as tuas listas e lembretes?")


async def handle_deletar_tudo(ctx: HandlerContext, content: str) -> str | None:
    """/deletar_tudo: confirma? 1=sim 2=não."""
    import re
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


async def resolve_confirm(ctx: HandlerContext, content: str) -> str | None:
    """Resolve confirmação pendente (1=sim 2=não). Chamado primeiro no router."""
    from backend.confirmations import get_pending, clear_pending, is_confirm_reply, is_confirm_yes, is_confirm_no
    pending = get_pending(ctx.channel, ctx.chat_id)
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
    return None
