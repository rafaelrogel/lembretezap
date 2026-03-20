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
    handle_feito,
    handle_remove,
    handle_hora_data,
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
from backend.settings_handlers import handle_tz, handle_lang, handle_quiet, handle_reset, handle_nuke
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
from backend.search_handler import handle_curated_search
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


# ---------------------------------------------------------------------------
# Lista mestre de Handlers (por ordem de prioridade)
# ---------------------------------------------------------------------------
HANDLERS = [
    handle_atendimento_request,
    handle_pending_confirmation,
    handle_curated_search,  # Busca filmes/livros/música — antes de list
    handle_list,  # primeiro: "cria lista de X", "mostre lista" → evita cair no LLM com histórico de erro
    handle_list_or_events_ambiguous,  # "tenho de X, Y" → pergunta lista ou lembretes
    handle_vague_time_reminder,
    handle_recurring_event,
    handle_eventos_unificado,
    handle_sacred_text,  # ativo: responde quando cliente pede versículo bíblia/alcorão
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
    handle_feito,
    handle_remove,
    handle_hora_data,
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
    handle_nuke,
]


async def route(ctx: HandlerContext, content: str) -> str | None:
    """Despacha mensagem para o handler adequado. Retorna texto ou None (fallback LLM)."""
    from backend.command_nl import normalize_nl_to_command
    if not content or not content.strip():
        return None
    # Se o utilizador usou /ayuda, reforçar idioma espanhol para lembretes e respostas seguintes
    if content.strip().lower().startswith("/ayuda"):
        try:
            from backend.database import SessionLocal
            from backend.user_store import set_user_language
            db = SessionLocal()
            try:
                set_user_language(db, ctx.chat_id, "es")
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Set language from /ayuda: {e}")

    content_norm = normalize_nl_to_command(content)
    content_norm = normalize_command(content_norm.strip())
    text = content_norm

    reply = await resolve_confirm(ctx, text)
    if reply is not None:
        return reply

    strict = os.environ.get("STRICT_HANDLERS", "").strip().lower() in ("1", "true", "yes")
    
    # Tentativa 1: Tratar o bloco inteiro como um só comando (comportamento original)
    for h in HANDLERS:
        try:
            out = await h(ctx, content_norm)
            if out is not None:
                return out
        except Exception as e:
            if strict: raise
            logger.debug(f"Handler {h.__name__} failed for full block: {e}")

    # Tentativa 2: Se tem múltiplas linhas, tentar processar cada uma como comando/NL separado (Batch Handling)
    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    if len(lines) > 1:
        results = []
        for line in lines:
            line_norm = normalize_nl_to_command(line)
            line_norm = normalize_command(line_norm.strip())
            for h in HANDLERS:
                try:
                    out = await h(ctx, line_norm)
                    if out is not None:
                        if isinstance(out, list):
                            results.extend(out)
                        else:
                            results.append(out)
                        break
                except Exception:
                    continue
        if results:
            # Se conseguimos processar algum comando do batch, devolvemos a junção
            # (Se algum falhou, o LLM não será chamado para o resto, mas o utilizador já teve feedback)
            return results if len(results) > 1 else results[0]

    return None
