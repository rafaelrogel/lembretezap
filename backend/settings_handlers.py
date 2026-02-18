"""Handlers de configuração do utilizador: /tz, /lang, /quiet, /reset."""

import re

from backend.handler_context import HandlerContext


async def handle_tz(ctx: HandlerContext, content: str) -> str | None:
    """/tz Cidade ou /tz IANA (ex: /tz Lisboa, /tz Europe/Lisbon)."""
    m = re.match(r"^/tz\s+(.+)$", content.strip(), re.I)
    if not m:
        return None
    raw = m.group(1).strip()
    if not raw:
        return "🌍 Use: /tz Cidade (ex: /tz Lisboa) ou /tz Europe/Lisbon"
    from backend.timezone import city_to_iana, is_valid_iana
    tz_iana = None
    if "/" in raw:
        tz_iana = raw if is_valid_iana(raw) else None
    else:
        tz_iana = city_to_iana(raw)
        if not tz_iana:
            tz_iana = city_to_iana(raw.replace(" ", ""))
    if not tz_iana:
        return f"🌍 Cidade \"{raw}\" não reconhecida. Tenta: /tz Lisboa, /tz São Paulo ou /tz Europe/Lisbon (IANA)."
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_timezone
        db = SessionLocal()
        try:
            if set_user_timezone(db, ctx.chat_id, tz_iana):
                return f"✅ Timezone definido: {tz_iana}. As horas dos lembretes passam a ser mostradas no teu fuso."
            return "❌ Timezone inválido."
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao gravar timezone: {e}"
    return None


async def handle_lang(ctx: HandlerContext, content: str) -> str | None:
    """/lang pt-pt | pt-br | es | en."""
    m = re.match(r"^/lang\s+(\S+)\s*$", content.strip(), re.I)
    if not m:
        return None
    lang = m.group(1).strip().lower()
    mapping = {"pt-pt": "pt-PT", "ptpt": "pt-PT", "ptbr": "pt-BR", "pt-br": "pt-BR", "es": "es", "en": "en"}
    code = mapping.get(lang) or (lang if lang in ("pt-PT", "pt-BR", "es", "en") else None)
    if not code:
        return "🌐 Idiomas disponíveis: /lang pt-pt | pt-br | es | en"
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_language
        db = SessionLocal()
        try:
            set_user_language(db, ctx.chat_id, code)
            return f"✅ Idioma definido: {code}."
        finally:
            db.close()
    except Exception:
        return "❌ Erro ao gravar idioma."
    return None


def _is_nl_quiet_off(content: str) -> bool:
    """True se a mensagem pede para parar/desativar o horário silencioso (texto ou áudio)."""
    t = (content or "").strip().lower()
    if not t or len(t) > 80:
        return False
    if "quiet" in t and ("off" in t or "parar" in t or "desativar" in t or "desligar" in t):
        return True
    if "horário silencioso" in t or "horario silencioso" in t:
        if any(p in t for p in ("parar", "desativar", "desligar", "desliga", "off", "remover", "não quero")):
            return True
    if t in ("parar silencioso", "desativar silencioso", "quiet off"):
        return True
    return False


async def handle_quiet(ctx: HandlerContext, content: str) -> str | None:
    """/quiet 22:00-08:00 ou /quiet off. Aceita NL: silêncio, quiet, parar horário silencioso."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip()
    t_lower = t.lower()
    is_nl_off = _is_nl_quiet_off(t)
    if not t_lower.startswith("/quiet") and not is_nl_off:
        return None
    if is_nl_off:
        rest = ""
    else:
        rest = t[6:].strip()  # após "/quiet"
    if is_nl_off or not rest or rest.lower() in ("off", "desligar", "não", "nao"):
        try:
            from backend.database import SessionLocal
            from backend.user_store import set_user_quiet
            db = SessionLocal()
            try:
                if set_user_quiet(db, ctx.chat_id, None, None):
                    return "🔔 Horário silencioso desativado. Voltaste a receber notificações a qualquer hora."
            finally:
                db.close()
        except Exception:
            pass
        return "❌ Erro ao desativar."
    parts = re.split(r"[\s\-–—]+", rest, maxsplit=1)
    if len(parts) < 2:
        return "🔇 Usa: /quiet 22:00-08:00 (não notificar entre 22h e 8h) ou /quiet off para desativar."
    start_hhmm, end_hhmm = parts[0].strip(), parts[1].strip()
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_quiet, _parse_time_hhmm
        if _parse_time_hhmm(start_hhmm) is None or _parse_time_hhmm(end_hhmm) is None:
            return "🕐 Horas em HH:MM (ex.: 22:00, 08:00)."
        db = SessionLocal()
        try:
            if set_user_quiet(db, ctx.chat_id, start_hhmm, end_hhmm):
                return f"🔇 Horário silencioso ativo: {start_hhmm}–{end_hhmm}. Não receberás lembretes nessa janela."
        finally:
            db.close()
    except Exception:
        pass
    return "❌ Erro ao guardar. Usa /quiet 22:00-08:00."


def _format_current_time_for_user(chat_id: str, lang: str) -> str:
    """Hora actual no fuso do utilizador (usa get_effective_time para corrigir relógio do servidor)."""
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        from backend.timezone import phone_to_default_timezone
        try:
            from zapista.clock_drift import get_effective_time
            effective_ts = get_effective_time()
        except Exception:
            import time
            effective_ts = time.time()
        tz_iana = phone_to_default_timezone(chat_id) or "UTC"
        z = ZoneInfo(tz_iana)
        dt = datetime.fromtimestamp(effective_ts, tz=timezone.utc).astimezone(z)
        return dt.strftime("%H:%M (%d/%m/%Y)")
    except Exception:
        return ""


async def handle_reset(ctx: HandlerContext, content: str) -> str | None:
    """/reset: limpa dados do onboarding. Aceita NL: reiniciar, reset."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    c = content.strip().lower()
    if not (c.startswith("/reset") or c.startswith("/reboot")):
        return None
    try:
        from backend.database import SessionLocal
        from backend.user_store import clear_onboarding_data, get_user_language
        from backend.locale import LangCode
        db = SessionLocal()
        try:
            clear_onboarding_data(db, ctx.chat_id)
            lang: LangCode = get_user_language(db, ctx.chat_id) or "pt-BR"
        finally:
            db.close()
    except Exception:
        lang = "pt-BR"
    msgs = {
        "pt-PT": "Cadastro apagado e conversa reiniciada. Na próxima mensagem, pergunto de novo onde estás (cidade ou hora) para acertar o fuso. /tz ou /fuso para mudar depois. LGPD: só o essencial. 😊\n\nSe no futuro as respostas parecerem estranhas por causa do histórico, usa /reset ou /reiniciar para limpar a conversa.",
        "pt-BR": "Cadastro apagado e conversa reiniciada. Na próxima mensagem, pergunto de novo onde você está (cidade ou hora) para acertar o fuso. /tz ou /fuso para mudar depois. LGPD: só o essencial. 😊\n\nSe no futuro as respostas parecerem estranhas por causa do histórico, use /reset ou /reiniciar para limpar a conversa.",
        "es": "Registro borrado y conversación reiniciada. En el próximo mensaje, pregunto de nuevo dónde estás (ciudad u hora) para el huso. /tz o /fuso para cambiar después. RGPD. 😊\n\nSi en el futuro las respuestas parecen raras por el historial, usa /reset o /reiniciar para limpiar la conversa.",
        "en": "Registration cleared and conversation reset. Next message, I'll ask again where you are (city or time) to set your timezone. /tz or /fuso to change later. GDPR. 😊\n\nIf answers ever seem off due to conversation history, use /reset or /reiniciar to clear the chat.",
    }
    out = msgs.get(lang, msgs["pt-BR"])
    time_str = _format_current_time_for_user(ctx.chat_id, lang)
    if time_str:
        hint_clock = {
            "pt-PT": "Se a hora estiver errada, no servidor define a variável CLOCK_OFFSET_SECONDS (segundos a somar ao relógio do servidor).",
            "pt-BR": "Se a hora estiver errada, no servidor defina a variável CLOCK_OFFSET_SECONDS (segundos a somar ao relógio do servidor).",
            "es": "Si la hora es incorrecta, en el servidor define la variable CLOCK_OFFSET_SECONDS (segundos a sumar al reloj del servidor).",
            "en": "If the time is wrong, on the server set CLOCK_OFFSET_SECONDS (seconds to add to server clock).",
        }
        out = out + "\n\n*Hora atual (no teu fuso):* " + time_str + "\n\n" + hint_clock.get(lang, hint_clock["en"])
    if ctx.session_manager:
        try:
            key = f"{ctx.channel}:{ctx.chat_id}"
            session = ctx.session_manager.get_or_create(key)
            for k in (
                "pending_preferred_name", "pending_language_choice", "pending_city",
                "onboarding_intro_sent", "onboarding_language_asked",
                "pending_timezone", "pending_time_confirm",
                "proposed_tz_iana", "proposed_date_str", "proposed_time_str",
                "onboarding_nudge_count", "nudge_append_done",
            ):
                session.metadata.pop(k, None)
            ctx.session_manager.save(session)
        except Exception:
            pass
    return out
