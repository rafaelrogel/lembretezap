"""Handlers de configuração do utilizador: /tz, /lang, /quiet, /reset."""

import re

from backend.handler_context import HandlerContext


async def handle_tz(ctx: HandlerContext, content: str) -> str | None:
    """/tz Cidade, /fuso ou /timezone IANA."""
    from backend.database import SessionLocal
    from backend.user_store import get_user_language, get_user_timezone
    from backend.locale import (
        SETTINGS_TZ_USAGE, SETTINGS_TZ_NOT_FOUND, SETTINGS_TZ_SET,
        SETTINGS_TZ_INVALID, SETTINGS_TZ_ERROR,
    )
    def _lang():
        try:
            db = SessionLocal()
            try:
                return get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            finally:
                db.close()
        except Exception:
            return "pt-BR"
    
    # Se for apenas /tz ou /fuso ou /timezone, mostrar o atual
    if re.match(r"^/(tz|fuso|timezone)\s*$", content.strip(), re.I):
        try:
            db = SessionLocal()
            try:
                lg = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
                tz_current = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale)
                if tz_current:
                    from backend.timezone import phone_to_default_timezone
                    def_tz = phone_to_default_timezone(ctx.chat_id)
                    from backend.locale import SETTINGS_TZ_CURRENT, SETTINGS_TZ_DEFAULT_HINT, SETTINGS_TZ_CHANGE_HINT
                    res = SETTINGS_TZ_CURRENT.get(lg, SETTINGS_TZ_CURRENT["en"]).format(tz=tz_current)
                    if def_tz and def_tz != tz_current:
                        res += SETTINGS_TZ_DEFAULT_HINT.get(lg, SETTINGS_TZ_DEFAULT_HINT["en"]).format(tz=def_tz)
                    return res + SETTINGS_TZ_CHANGE_HINT.get(lg, SETTINGS_TZ_CHANGE_HINT["en"])
            finally:
                db.close()
        except Exception:
            pass
        return None

    m = re.match(r"^/(tz|fuso|timezone)\s+(.+)$", content.strip(), re.I)
    if not m:
        return None
    raw = m.group(1).strip()
    if not raw:
        lg = _lang()
        return SETTINGS_TZ_USAGE.get(lg, SETTINGS_TZ_USAGE["en"])
    from backend.timezone import city_to_iana, is_valid_iana
    tz_iana = None
    if "/" in raw:
        tz_iana = raw if is_valid_iana(raw) else None
    else:
        tz_iana = city_to_iana(raw)
        if not tz_iana:
            tz_iana = city_to_iana(raw.replace(" ", ""))
    if not tz_iana:
        lg = _lang()
        return SETTINGS_TZ_NOT_FOUND.get(lg, SETTINGS_TZ_NOT_FOUND["en"]).format(city=raw)
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_timezone
        db = SessionLocal()
        try:
            lg = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            if set_user_timezone(db, ctx.chat_id, tz_iana):
                return SETTINGS_TZ_SET.get(lg, SETTINGS_TZ_SET["en"]).format(tz=tz_iana)
            return SETTINGS_TZ_INVALID.get(lg, SETTINGS_TZ_INVALID["en"])
        finally:
            db.close()
    except Exception as e:
        lg = _lang()
        return SETTINGS_TZ_ERROR.get(lg, SETTINGS_TZ_ERROR["en"]).format(error=e)
    return None


async def handle_lang(ctx: HandlerContext, content: str) -> str | None:
    """/lang pt-pt | pt-br | es | en."""
    from backend.database import SessionLocal
    from backend.user_store import get_user_language
    from backend.locale import SETTINGS_LANG_USAGE, SETTINGS_LANG_SET, SETTINGS_LANG_ERROR
    m = re.match(r"^/lang\s+(\S+)\s*$", content.strip(), re.I)
    if not m:
        return None
    lang = m.group(1).strip().lower()
    mapping = {"pt-pt": "pt-PT", "ptpt": "pt-PT", "ptbr": "pt-BR", "pt-br": "pt-BR", "es": "es", "en": "en"}
    code = mapping.get(lang) or (lang if lang in ("pt-PT", "pt-BR", "es", "en") else None)
    if not code:
        try:
            db = SessionLocal()
            try:
                lg = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            finally:
                db.close()
        except Exception:
            lg = "pt-BR"
        return SETTINGS_LANG_USAGE.get(lg, SETTINGS_LANG_USAGE["en"])
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_language
        db = SessionLocal()
        try:
            set_user_language(db, ctx.chat_id, code)
            return SETTINGS_LANG_SET.get(code, SETTINGS_LANG_SET["en"]).format(lang=code)
        finally:
            db.close()
    except Exception:
        try:
            db2 = SessionLocal()
            try:
                lg = get_user_language(db2, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            finally:
                db2.close()
        except Exception:
            lg = "pt-BR"
        return SETTINGS_LANG_ERROR.get(lg, SETTINGS_LANG_ERROR["en"])
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
    """/quiet 22:00-08:00, /silencio ou /silent off. Aceita NL: silêncio, quiet, parar horário silencioso."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip()
    t_lower = t.lower()
    is_nl_off = _is_nl_quiet_off(t)
    if not re.match(r"^/(quiet|silencio|silent)", t_lower) and not is_nl_off:
        return None
    from backend.locale import QUIET_OFF_SUCCESS, QUIET_OFF_ERROR, QUIET_USAGE, QUIET_TIME_FORMAT, QUIET_SAVE_ERROR
    _qlang = "pt-BR"
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_user_language
        _qdb = SessionLocal()
        try:
            _qlang = get_user_language(_qdb, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
        finally:
            _qdb.close()
    except Exception:
        pass
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
                    return QUIET_OFF_SUCCESS.get(_qlang, QUIET_OFF_SUCCESS["en"])
            finally:
                db.close()
        except Exception:
            pass
        return QUIET_OFF_ERROR.get(_qlang, QUIET_OFF_ERROR["en"])
    parts = re.split(r"[\s\-–—]+", rest, maxsplit=1)
    if len(parts) < 2:
        return QUIET_USAGE.get(_qlang, QUIET_USAGE["en"])
    start_hhmm, end_hhmm = parts[0].strip(), parts[1].strip()
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_quiet, _parse_time_hhmm
        if _parse_time_hhmm(start_hhmm) is None or _parse_time_hhmm(end_hhmm) is None:
            return QUIET_TIME_FORMAT.get(_qlang, QUIET_TIME_FORMAT["en"])
        db = SessionLocal()
        try:
            if set_user_quiet(db, ctx.chat_id, start_hhmm, end_hhmm):
                from backend.locale import QUIET_STATUS
                return QUIET_STATUS.get(_qlang, QUIET_STATUS["en"]).format(start=start_hhmm, end=end_hhmm)
        finally:
            db.close()
    except Exception:
        pass
    return QUIET_SAVE_ERROR.get(_qlang, QUIET_SAVE_ERROR["en"])


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
    """/reset, /reiniciar ou /reboot: limpa dados do onboarding. Aceita NL: reiniciar, reset."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    c = content.strip().lower()
    if not (c.startswith("/reset") or c.startswith("/reboot") or c.startswith("/reiniciar")):
        return None
    try:
        from backend.database import SessionLocal
        from backend.user_store import clear_onboarding_data, get_user_language
        from backend.locale import LangCode
        db = SessionLocal()
        try:
            clear_onboarding_data(db, ctx.chat_id)
            lang: LangCode = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
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
        out = out + "\n\n*Hora atual (no seu fuso):* " + time_str
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

    if abs(offset) > 60:
        from backend.locale import SERVER_CLOCK_SKEW_WARNING
        res.append("\n" + SERVER_CLOCK_SKEW_WARNING.get(user_lang, SERVER_CLOCK_SKEW_WARNING["en"]))
    
    return "\n".join(res)


# ---------------------------------------------------------------------------
# /nuke, /bomba — apaga TUDO do zero (com confirmação engraçada)
# ---------------------------------------------------------------------------

_NUKE_CONFIRM_MSGS = {
    "pt-PT": (
        "💣 *AQUI É TIRO, PORRADA E BOMBA!* 💥\n\n"
        "Vais apagar *tudo* — listas, lembretes, eventos, memória da conversa... TUDO.\n"
        "Esta ação é irreversível, como uma bomba: depois de explodir, não há marcha atrás! 💨\n\n"
        "Tens mesmo a certeza? Responde *1* para *BOOM 💥* ou *2* para te esquivares."
    ),
    "pt-BR": (
        "💣 *AQUI É TIRO, PORRADA E BOMBA!* 💥\n\n"
        "Você vai apagar *tudo* — listas, lembretes, eventos, memória da conversa... TUDO.\n"
        "Esta ação não tem volta, é como uma bomba: detonou, acabou! 💨\n\n"
        "Tem certeza mesmo? Responda *1* para *BOOM 💥* ou *2* para se esquivar."
    ),
    "es": (
        "💣 *¡AQUÍ ES A LO BESTIA!* 💥\n\n"
        "Vas a borrar *todo* — listas, recordatorios, eventos, memoria de la conversación... ¡TODO!\n"
        "Esta acción no tiene vuelta atrás, ¡es como una bomba: bang y se acabó! 💨\n\n"
        "¿Estás seguro? Responde *1* para *BOOM 💥* o *2* para esquivarte."
    ),
    "en": (
        "💣 *THIS IS A FULL NUKE!* 💥\n\n"
        "You're about to erase *everything* — lists, reminders, events, conversation memory... ALL of it.\n"
        "There's no undo. Think of it like a bomb: once it goes off, it's gone! 💨\n\n"
        "Are you absolutely sure? Reply *1* for *BOOM 💥* or *2* to dodge the blast."
    ),
}

_NUKE_CANCELLED_MSGS = {
    "pt-PT": "💨 Ufa! Bomba desarmada. Nenhum dado foi apagado.",
    "pt-BR": "💨 Ufa! Bomba desarmada. Nenhum dado foi apagado.",
    "es": "💨 ¡Uf! Bomba desactivada. No se borró nada.",
    "en": "💨 Phew! Bomb defused. Nothing was deleted.",
}

_NUKE_DONE_MSGS = {
    "pt-PT": (
        "💥 *BOOM!* Tudo apagado.\n\n"
        "Listas, lembretes, eventos, memória da conversa — tudo evaporou como fumo de bomba. 💨\n"
        "Começas do zero! Envia uma mensagem para recomeçar o onboarding. 😊"
    ),
    "pt-BR": (
        "💥 *BOOM!* Tudo apagado.\n\n"
        "Listas, lembretes, eventos, memória da conversa — tudo evaporou como fumaça de bomba. 💨\n"
        "Começa do zero! Envie uma mensagem para reiniciar o onboarding. 😊"
    ),
    "es": (
        "💥 *¡BOOM!* Todo borrado.\n\n"
        "Listas, recordatorios, eventos, memoria de la conversación — todo evaporado. 💨\n"
        "¡Empezamos de cero! Envía un mensaje para reiniciar. 😊"
    ),
    "en": (
        "💥 *BOOM!* Everything's gone.\n\n"
        "Lists, reminders, events, conversation memory — all vaporized. 💨\n"
        "Fresh start! Send a message to restart onboarding. 😊"
    ),
}


async def handle_nuke(ctx: HandlerContext, content: str) -> str | None:
    """/nuke, /bomba: apaga TUDO com confirmação engraçada em 4 idiomas."""
    import re
    c = content.strip().lower()
    if not re.match(r"^/(nuke|bomba|bomb)\s*$", c, re.I):
        return None

    try:
        from backend.database import SessionLocal
        from backend.user_store import get_user_language
        from backend.locale import resolve_response_language
        db = SessionLocal()
        try:
            lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            lang = resolve_response_language(lang, ctx.chat_id, ctx.phone_for_locale)
        finally:
            db.close()
    except Exception:
        lang = "pt-BR"

    from backend.confirmations import set_pending
    set_pending(ctx.channel, ctx.chat_id, "nuke_all", {"lang": lang})
    return _NUKE_CONFIRM_MSGS.get(lang, _NUKE_CONFIRM_MSGS["pt-BR"])

