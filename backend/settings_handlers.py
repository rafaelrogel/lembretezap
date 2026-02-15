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
        return f"🌍 Cidade «{raw}» não reconhecida. Tenta: /tz Lisboa, /tz São Paulo ou /tz Europe/Lisbon (IANA)."
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
    """/quiet 22:00-08:00 ou /quiet off. Aceita linguagem natural: parar horário silencioso, desativar quiet."""
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


async def handle_reset(ctx: HandlerContext, content: str) -> str | None:
    """/reset: limpa dados do onboarding (nome, cidade) para refazer o cadastro."""
    if not content.strip().lower().startswith("/reset"):
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
        "pt-PT": "Cadastro apagado. Na próxima mensagem, recomeço o onboarding (nome, cidade). Respeitamos LGPD: só o essencial. 😊",
        "pt-BR": "Cadastro apagado. Na próxima mensagem, recomeço o cadastro (nome, cidade). Respeitamos LGPD: só o essencial. 😊",
        "es": "Registro borrado. En el próximo mensaje, reinicio (nombre, ciudad). Respetamos RGPD. 😊",
        "en": "Registration cleared. Next message, I'll restart (name, city). We respect GDPR. 😊",
    }
    if ctx.session_manager:
        try:
            key = f"{ctx.channel}:{ctx.chat_id}"
            session = ctx.session_manager.get_or_create(key)
            for k in ("pending_preferred_name", "pending_language_choice", "pending_city",
                      "onboarding_intro_sent", "onboarding_language_asked"):
                session.metadata.pop(k, None)
            ctx.session_manager.save(session)
        except Exception:
            pass
    return msgs.get(lang, msgs["pt-BR"])
