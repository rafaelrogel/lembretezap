"""Lista de handlers e função route() para despacho de mensagens."""

import os
from loguru import logger

from backend.handler_context import HandlerContext
from backend.handlers import (
    handle_atendimento_request,
    handle_pending_confirmation,
    handle_eventos_unificado,
    handle_recurring_prompt,
    handle_lembrete,
    handle_list,
    handle_feito,
    handle_add,
    handle_done,
    handle_start,
    handle_help,
    handle_recorrente,
    handle_pendente,
    handle_tz,
    handle_lang,
    handle_quiet,
    handle_stop,
    handle_reset,
    handle_exportar,
    handle_deletar_tudo,
    _resolve_confirm,
)
from backend.integrations import handle_crypto, handle_sacred_text
from backend.llm_handlers import handle_resumo_conversa, handle_analytics, handle_rever
from backend.handlers_organizacao import (
    handle_habitos,
    handle_habito,
    handle_metas,
    handle_meta,
    handle_notas,
    handle_nota,
    handle_projetos,
    handle_projeto,
    handle_templates,
    handle_template,
    handle_bookmarks,
    handle_bookmark,
    handle_save,
    handle_find,
)
from backend.handlers_limpeza import handle_limpeza
from backend.views import (
    handle_hoje,
    handle_semana,
    handle_mes,
    handle_timeline,
    handle_stats,
    handle_produtividade,
    handle_revisao,
)

HANDLERS = [
    handle_atendimento_request,
    handle_pending_confirmation,
    handle_eventos_unificado,
    handle_recurring_prompt,
    handle_lembrete,
    handle_list,
    handle_feito,
    handle_add,
    handle_done,
    handle_start,
    handle_help,
    handle_recorrente,
    handle_pendente,
    handle_hoje,
    handle_semana,
    handle_mes,
    handle_timeline,
    handle_stats,
    handle_produtividade,
    handle_revisao,
    handle_habitos,
    handle_habito,
    handle_metas,
    handle_meta,
    handle_notas,
    handle_nota,
    handle_projetos,
    handle_projeto,
    handle_templates,
    handle_template,
    handle_bookmarks,
    handle_bookmark,
    handle_save,
    handle_find,
    handle_limpeza,
    handle_sacred_text,
    handle_crypto,
    handle_tz,
    handle_lang,
    handle_resumo_conversa,
    handle_analytics,
    handle_rever,
    handle_quiet,
    handle_stop,
    handle_reset,
    handle_exportar,
    handle_deletar_tudo,
]


async def route(ctx: HandlerContext, content: str) -> str | None:
    """Despacha mensagem para o handler adequado. Retorna texto ou None (fallback LLM)."""
    if not content or not content.strip():
        return None
    text = content.strip()

    reply = await _resolve_confirm(ctx, text)
    if reply is not None:
        return reply

    strict = os.environ.get("STRICT_HANDLERS", "").strip().lower() in ("1", "true", "yes")
    for h in HANDLERS:
        try:
            out = await h(ctx, content)
            if out is not None:
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
