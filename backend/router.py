"""Lista de handlers e função route() para despacho de mensagens."""

import os
from loguru import logger

from backend.handler_context import HandlerContext
from backend.handlers import (
    handle_pending_confirmation,
    handle_vague_time_reminder,
    handle_recurring_event,
    handle_recurring_prompt,
    handle_lembrete,
    handle_list_or_events_ambiguous,
    handle_list,
    handle_add,
    handle_start,
    handle_help,
    handle_recorrente,
    handle_pendente,
    handle_stop,
)
from backend.integrations import handle_atendimento_request, handle_crypto, handle_sacred_text
from backend.confirm_actions import handle_exportar, handle_deletar_tudo, resolve_confirm
from backend.settings_handlers import handle_tz, handle_lang, handle_quiet, handle_reset
from backend.llm_handlers import handle_resumo_conversa, handle_analytics, handle_rever
from backend.handlers_organizacao import (
    handle_metas,
    handle_meta,
    handle_projetos,
    handle_projeto,
    handle_templates,
    handle_template,
)
from backend.handlers_limpeza import handle_limpeza
from backend.handlers_agenda_remove import handle_agenda_remove
from backend.handlers_pomodoro import handle_pomodoro
from backend.recipe_handler import handle_recipe
from backend.command_i18n import normalize_command
from backend.views import (
    handle_eventos_unificado,
    handle_hoje,
    handle_semana,
    handle_agenda,
    handle_agenda_nl,
    handle_mes,
    handle_timeline,
    handle_stats,
    handle_produtividade,
    handle_revisao,
)

HANDLERS = [
    handle_atendimento_request,
    handle_pending_confirmation,
    handle_vague_time_reminder,
    handle_recurring_event,
    handle_eventos_unificado,
    handle_sacred_text,  # ativo: responde quando cliente pede versículo bíblia/alcorão
    handle_list_or_events_ambiguous,  # "tenho de X, Y" → pergunta lista ou lembretes
    handle_list,  # antes de recurring: "lista mercado", "mostre lista" → list_show
    handle_limpeza,  # antes de recurring: "preciso limpar a casa" → fluxo limpeza
    handle_pomodoro,  # /pomodoro — timer 25 min foco
    handle_quiet,  # /quiet e NL "parar horário silencioso" — antes do fluxo de lembrete
    handle_recipe,  # receita/ingredientes via Perplexity (rápido, fallback agent)
    handle_recurring_prompt,
    handle_lembrete,
    handle_add,
    handle_start,
    handle_help,
    handle_recorrente,
    handle_pendente,
    handle_hoje,
    handle_semana,
    handle_agenda,
    handle_agenda_nl,  # "minha agenda", "o que tenho hoje" (texto/áudio)
    handle_agenda_remove,  # "remover a consulta", "já fiz a reunião" → remove da agenda
    handle_mes,
    handle_timeline,
    handle_stats,
    handle_produtividade,
    handle_revisao,
    handle_metas,
    handle_meta,
    handle_projetos,
    handle_projeto,
    handle_templates,
    handle_template,
    handle_crypto,
    handle_tz,
    handle_lang,
    handle_resumo_conversa,
    handle_analytics,
    handle_rever,
    handle_stop,
    handle_reset,
    handle_exportar,
    handle_deletar_tudo,
]


async def route(ctx: HandlerContext, content: str) -> str | None:
    """Despacha mensagem para o handler adequado. Retorna texto ou None (fallback LLM)."""
    # #region agent log
    import json as _json, os as _os
    _log_path = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "nanobot", ".cursor", "debug.log"))
    try: open(_log_path, "a", encoding="utf-8").write(_json.dumps({"location": "router.route.entry", "message": "route", "data": {"content_preview": (content or "")[:120]}, "timestamp": __import__("time").time() * 1000, "hypothesisId": "H2"}) + "\n"); pass
    except Exception: pass
    # #endregion
    if not content or not content.strip():
        return None
    content = normalize_command(content.strip())
    text = content
    # #region agent log
    try: open(_log_path, "a", encoding="utf-8").write(_json.dumps({"location": "router.route.after_normalize", "message": "route", "data": {"content_normalized": content[:120]}, "timestamp": __import__("time").time() * 1000, "hypothesisId": "H2"}) + "\n"); pass
    except Exception: pass
    # #endregion

    reply = await resolve_confirm(ctx, text)
    if reply is not None:
        return reply

    strict = os.environ.get("STRICT_HANDLERS", "").strip().lower() in ("1", "true", "yes")
    for h in HANDLERS:
        try:
            out = await h(ctx, content)
            if out is not None:
                # #region agent log
                try: open(_log_path, "a", encoding="utf-8").write(_json.dumps({"location": "router.route.handler_return", "message": "route", "data": {"handler": h.__name__, "out_preview": (out or "")[:80]}, "timestamp": __import__("time").time() * 1000, "hypothesisId": "H3"}) + "\n"); pass
                except Exception: pass
                # #endregion
                return out
        except Exception as e:
            if strict:
                raise
            logger.exception(
                "handler_failed",
                handler=h.__name__,
                chat_id=ctx.chat_id[:20] if ctx.chat_id else "",
                content_preview=(content or "")[:80],
                error=str(e),
            )
            continue
    return None
