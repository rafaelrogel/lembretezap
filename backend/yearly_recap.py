"""
Recap de Ano Novo (1º de janeiro): mensagem de parceria (DeepSeek) + análise do ano (Mimo).

Envia a cada utilizador com sessão ativa: agradecimento, estatísticas do ano (lembretes,
mensagens, listas), benefícios e tempo de organização poupado.
"""

from datetime import datetime
from typing import Any

from loguru import logger

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models_db import ReminderHistory, List, ListItem
from backend.user_store import get_or_create_user, get_user_language, get_user_preferred_name


def get_user_year_stats(db: Session, chat_id: str, year: int) -> dict[str, Any]:
    """
    Estatísticas do utilizador no ano (para recap).
    Retorna: reminders_created, reminders_received, list_items_added, e contagens por tipo.
    """
    user = get_or_create_user(db, chat_id)
    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)

    # Lembretes: agendados (criados pelo user) e entregues (recebidos)
    scheduled = (
        db.query(func.count(ReminderHistory.id))
        .filter(
            ReminderHistory.user_id == user.id,
            ReminderHistory.kind == "scheduled",
            ReminderHistory.created_at >= start,
            ReminderHistory.created_at < end,
        )
        .scalar() or 0
    )
    delivered = (
        db.query(func.count(ReminderHistory.id))
        .filter(
            ReminderHistory.user_id == user.id,
            ReminderHistory.kind == "delivered",
            ReminderHistory.created_at >= start,
            ReminderHistory.created_at < end,
        )
        .scalar() or 0
    )

    # Itens adicionados às listas no ano (ListItem.created_at)
    list_items = (
        db.query(func.count(ListItem.id))
        .join(List, ListItem.list_id == List.id)
        .filter(
            List.user_id == user.id,
            ListItem.created_at >= start,
            ListItem.created_at < end,
        )
        .scalar() or 0
    )

    return {
        "year": year,
        "reminders_created": scheduled,
        "reminders_received": delivered,
        "list_items_added": list_items,
    }


def get_session_message_counts_for_year(session_messages: list[dict], year: int) -> tuple[int, int]:
    """
    Conta mensagens do utilizador e do assistente no ano.
    session_messages: lista de dicts com role, content, timestamp (opcional).
    Retorna (user_count, assistant_count).
    """
    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)
    user_count = 0
    assistant_count = 0
    for m in session_messages:
        ts = m.get("timestamp")
        if not ts:
            continue
        try:
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                dt = ts
            if start <= dt < end:
                role = (m.get("role") or "").strip().lower()
                if role == "user":
                    user_count += 1
                elif role in ("assistant", "system"):
                    assistant_count += 1
        except Exception:
            continue
    return user_count, assistant_count


def estimate_time_saved_minutes(stats: dict[str, Any]) -> int:
    """
    Estima tempo de organização poupado (minutos): lembretes evitam esquecer,
    listas evitam tempo a planear. Valores por unidade são arbitrários mas razoáveis.
    """
    m = 0
    m += (stats.get("reminders_created") or 0) * 2   # ~2 min por lembrete não esquecido
    m += (stats.get("reminders_received") or 0) * 1   # 1 min por lembrança recebida (ação)
    m += (stats.get("list_items_added") or 0) * 1    # ~1 min por item listado
    msgs_user = stats.get("messages_sent_by_user") or 0
    m += msgs_user * 0.5  # meio minuto por mensagem (organização via chat)
    return max(0, m)


async def build_recap_message(
    *,
    deepseek_provider: Any,
    deepseek_model: str,
    mimo_provider: Any,
    mimo_model: str,
    user_lang: str,
    preferred_name: str | None,
    stats: dict[str, Any],
    year: int,
) -> str:
    """
    Constrói a mensagem de recap: parte emocional (DeepSeek) + análise do ano (Mimo).
    """
    name = (preferred_name or "").strip() or "utilizador"
    lang_instruction = {
        "pt-PT": "em português de Portugal",
        "pt-BR": "em português do Brasil",
        "es": "en español",
        "en": "in English",
    }.get(user_lang, "in the user's language")

    # Parte 1: DeepSeek — mensagem variada, tocante e criativa (não usar texto genérico)
    deepseek_prompt = (
        f"Write a short, warm and CREATIVE New Year message (2-3 sentences) to a user named «{name}». "
        "Say how happy we are to have them as a friend and user, that we want to make their life easier "
        "all year long, and that we hope our partnership lasts many, many years. "
        "Be genuine, touching and VARIED — avoid generic phrases; surprise them with a fresh wording. "
        "Include 1-2 emojis that fit the mood (e.g. 🎉 ✨ 🤝 💙 🌟). No bullet points. "
        f"Reply only with the message text, {lang_instruction}."
    )
    part1 = ""
    try:
        r = await deepseek_provider.chat(
            messages=[{"role": "user", "content": deepseek_prompt}],
            model=deepseek_model,
            max_tokens=196,
            temperature=0.85,
        )
        part1 = (r.content or "").strip()
    except Exception:
        part1 = f"Feliz Ano Novo, {name}! 💙 Estamos muito contentes por teres estado connosco. Que a nossa parceria dure muitos anos! ✨"

    # Parte 2: Mimo — recap analítico
    time_saved = estimate_time_saved_minutes(stats)
    stats_text = (
        f"Ano: {year}. Lembretes criados (agendados): {stats.get('reminders_created', 0)}. "
        f"Lembretes recebidos (entregues): {stats.get('reminders_received', 0)}. "
        f"Mensagens enviadas pelo utilizador: {stats.get('messages_sent_by_user', 0)}. "
        f"Mensagens enviadas por nós (respostas): {stats.get('messages_from_us', 0)}. "
        f"Itens adicionados às listas: {stats.get('list_items_added', 0)}. "
        f"Tempo estimado de organização poupado (minutos): {time_saved}."
    )
    mimo_prompt = (
        "You are writing a private yearly ANALYTICAL recap for the user. Based ONLY on the data below, "
        "write a short, engaging recap (2-4 sentences) that includes: "
        "how many reminders they created and received, how many messages they sent and received from us, "
        "how many list items they added. Mention the benefits (staying organized, not forgetting, saving time). "
        "Include the estimated time saved in a readable form (e.g. 'about X hours' or 'X minutes'). "
        "Add one or two interesting or fun statistics about their usage, just for them. "
        "IMPORTANT: Use EMOJIS throughout the analysis — next to numbers, in the fun facts, and to highlight "
        "benefits (e.g. 📋 for lists, ⏰ for reminders, 💡 for insights, 🎯 for goals, ⏱️ for time saved, "
        "📊 for stats, ✨ for achievements). Make it lively and personal. "
        "Be concise, positive and private. Reply only with the recap text, no preamble. "
        f"Language: {lang_instruction}."
    )
    part2 = ""
    if mimo_provider and mimo_model:
        try:
            r = await mimo_provider.chat(
                messages=[{"role": "user", "content": f"{mimo_prompt}\n\nData:\n{stats_text}"}],
                model=mimo_model,
                max_tokens=315,
                temperature=0.5,
            )
            part2 = (r.content or "").strip()
        except Exception:
            pass
    if not part2:
        part2 = (
            f"📊 No {year}: {stats.get('reminders_created', 0)} lembretes criados ⏰ e {stats.get('reminders_received', 0)} recebidos. "
            f"📋 {stats.get('list_items_added', 0)} itens nas listas. "
            f"⏱️ Tempo de organização poupado: ~{time_saved} min. ✨"
        )

    return (part1 + "\n\n" + part2).strip()


async def run_year_recap(
    *,
    bus: Any,
    session_manager: Any,
    deepseek_provider: Any,
    deepseek_model: str,
    mimo_provider: Any | None,
    mimo_model: str | None,
    default_channel: str = "whatsapp",
) -> tuple[int, int]:
    """
    Envia o recap de ano novo a todos os utilizadores com sessão ativa.
    Usa o ano anterior ao atual (em 1 Jan 2026 envia recap de 2025).
    Retorna (enviados, erros).
    """
    from backend.database import SessionLocal
    from zapista.bus.events import OutboundMessage

    year = datetime.utcnow().year - 1  # ano passado
    sent = 0
    errors = 0

    sessions = session_manager.list_sessions()
    # Opcional: filtrar só sessões com atividade no último ano (updated_at)
    # Por simplicidade enviamos a todas as sessões existentes
    for s in sessions:
        key = s.get("key") or ""
        if ":" not in key:
            continue
        channel, chat_id = key.split(":", 1)
        if not chat_id:
            continue
        # Usar o canal da sessão ou o default
        ch = channel if channel else default_channel

        try:
            db = SessionLocal()
            try:
                user_lang = get_user_language(db, chat_id)
                preferred_name = get_user_preferred_name(db, chat_id)
                stats = get_user_year_stats(db, chat_id, year)
            finally:
                db.close()

            # Contagens de mensagens na sessão
            try:
                session = session_manager.get_or_create(key)
                msgs = getattr(session, "messages", []) or []
                user_msgs, our_msgs = get_session_message_counts_for_year(msgs, year)
                stats["messages_sent_by_user"] = user_msgs
                stats["messages_from_us"] = our_msgs
            except Exception:
                stats["messages_sent_by_user"] = 0
                stats["messages_from_us"] = 0

            content = await build_recap_message(
                deepseek_provider=deepseek_provider,
                deepseek_model=deepseek_model,
                mimo_provider=mimo_provider,
                mimo_model=mimo_model or "",
                user_lang=user_lang,
                preferred_name=preferred_name,
                stats=stats,
                year=year,
            )

            await bus.publish_outbound(OutboundMessage(
                channel=ch,
                chat_id=chat_id,
                content=content,
                metadata={"priority": "high"},
            ))
            sent += 1
        except Exception as e:
            errors += 1
            logger.warning(f"Year recap failed for {key}: {e}")

    return sent, errors
