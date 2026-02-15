"""Handler para anexos .ics: parse com icalendar, criação de Event (e opcionalmente lembrete cron)."""

from datetime import date, datetime, time
from typing import Any

from loguru import logger

# Limite de eventos por .ics e tamanho máximo do conteúdo
MAX_EVENTS_PER_ICS = 50
MAX_ICS_BYTES = 500 * 1024  # 500 KB


def _normalize_ics_content(raw: str) -> str:
    """
    Normaliza o conteúdo .ics para aumentar a taxa de sucesso do parse:
    - Remove BOM UTF-8
    - Normaliza fins de linha para \\n
    - Desdobra linhas (RFC 5545: linha continua com \\n + espaço)
    - Remove bytes nulos
    """
    if not raw:
        return raw
    # BOM UTF-8
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    # Fins de linha: CRLF e CR -> LF
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Desdobrar linhas continuadas (ex.: "DTSTART;TZID=...\n :20260217T120000" -> uma só linha)
    while "\n " in raw:
        raw = raw.replace("\n ", " ")
    # Bytes nulos (podem vir de ficheiros mal formados)
    raw = raw.replace("\x00", "")
    return raw.strip()


def _try_decode_utf8_from_latin1(s: str) -> str | None:
    """
    Se o ficheiro foi interpretado como Latin-1 mas era UTF-8,
    re-encodar como Latin-1 e decodificar como UTF-8.
    Retorna None se não fizer sentido (ex.: caracteres fora de range Latin-1).
    """
    try:
        return s.encode("latin-1").decode("utf-8", errors="strict")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return None


def _to_datetime(dt: date | datetime) -> datetime:
    """Converte date ou datetime para datetime (date -> 00:00:00)."""
    if isinstance(dt, datetime):
        return dt
    if isinstance(dt, date):
        return datetime.combine(dt, time.min)
    return datetime.min


def _get_dt_from_vevent(component: Any, key: str) -> datetime | None:
    """
    Extrai datetime de DTSTART ou DTEND de um VEVENT, tratando TZID e formatos
    que a icalendar por vezes devolve (naive, ou .dt com estrutura inesperada).
    """
    val = component.get(key)
    if val is None:
        return None
    dt: datetime | None = None
    dt_raw = getattr(val, "dt", None)
    if isinstance(dt_raw, datetime):
        dt = dt_raw
    elif isinstance(dt_raw, date) and not isinstance(dt_raw, datetime):
        dt = datetime.combine(dt_raw, time.min)
    elif isinstance(dt_raw, (list, tuple)) and len(dt_raw) >= 1:
        first = dt_raw[0]
        if isinstance(first, datetime):
            dt = first
        elif isinstance(first, date):
            dt = datetime.combine(first, time.min)

    if dt is None:
        # Fallback: icalendar pode devolver valor em formato que não é date/datetime
        # (ex.: DTSTART;TZID=Africa/Abidjan com .dt não resolvido). Parse manual via to_ical() + params.
        try:
            params = getattr(val, "params", None) or {}
            tzid_list = params.get("TZID") if isinstance(params, dict) else None
            tzid = (tzid_list[0] if tzid_list else None) if isinstance(tzid_list, list) else tzid_list
            ical_str = val.to_ical() if hasattr(val, "to_ical") else None
            if isinstance(ical_str, bytes):
                ical_str = ical_str.decode("utf-8", errors="replace")
            if ical_str and isinstance(ical_str, str):
                ical_str = ical_str.strip()
                if "T" in ical_str and len(ical_str) >= 15:
                    dt_naive = datetime.strptime(ical_str[:15], "%Y%m%dT%H%M%S")
                elif len(ical_str) >= 8:
                    dt_naive = datetime.strptime(ical_str[:8], "%Y%m%d")
                else:
                    dt_naive = None
                if dt_naive is not None and tzid:
                    try:
                        from zoneinfo import ZoneInfo
                        z = ZoneInfo(str(tzid))
                        dt = dt_naive.replace(tzinfo=z)
                    except Exception:
                        dt = dt_naive
                elif dt_naive is not None:
                    dt = dt_naive
        except Exception as e:
            logger.debug(f"ics _get_dt_from_vevent fallback failed for {key}: {e}")

    if dt is None:
        return None
    if dt.tzinfo is None:
        try:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return dt


async def handle_ics_payload(
    chat_id: str,
    sender_id: str,
    ics_content: str,
    *,
    db_session_factory: Any = None,
    cron_tool: Any = None,
    cron_channel: str = "whatsapp",
    user_lang: str | None = None,
) -> str:
    """
    Parse do .ics, criação de Event por VEVENT e opcionalmente lembrete (cron).
    Retorna mensagem de resumo para o utilizador (1–2 frases).
    Nunca inclui secrets.
    """
    lang = user_lang or "en"
    if not ics_content or not ics_content.strip():
        return _summary_message(0, [], lang, error="Calendário vazio.")

    raw = _normalize_ics_content(ics_content)
    if not raw:
        return _summary_message(0, [], lang, error="Calendário vazio.")

    if len(raw.encode("utf-8")) > MAX_ICS_BYTES:
        return _summary_message(0, [], lang, error="Ficheiro demasiado grande.")

    try:
        import icalendar
    except ImportError:
        logger.warning("icalendar not installed; pip install icalendar")
        return _summary_message(0, [], lang, error="Suporte a .ics não disponível.")

    cal = None
    parse_error: Exception | None = None
    try:
        cal = icalendar.Calendar.from_ical(raw)
    except Exception as e:
        parse_error = e
        logger.warning(f"ics parse failed: {e}. Preview: {raw[:300]!r}")
        # Fallback: ficheiro pode ter sido interpretado como Latin-1 mas ser UTF-8 (ex.: export do Outlook)
        decoded = _try_decode_utf8_from_latin1(raw)
        if decoded is not None:
            try:
                cal = icalendar.Calendar.from_ical(decoded)
            except Exception as e2:
                parse_error = e2
                logger.debug(f"ics parse (latin1 fallback) failed: {e2}")

    if cal is None:
        err_msg = (
            "Calendário inválido ou encoding incorreto. "
            "Tenta exportar o .ics de novo (UTF-8) ou usar outro ficheiro."
        )
        return _summary_message(0, [], lang, error=err_msg)

    events_created: list[dict[str, Any]] = []
    if not db_session_factory:
        return _summary_message(0, [], lang, error="Base de dados não disponível.")

    db = db_session_factory()
    try:
        from backend.models_db import Event, AuditLog
        from backend.user_store import get_or_create_user, get_user_language
        from backend.sanitize import sanitize_string
        from backend.guardrails import is_absurd_request

        user = get_or_create_user(db, chat_id)
        lang = get_user_language(db, chat_id) or lang
        user_id = user.id
        count = 0
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            if count >= MAX_EVENTS_PER_ICS:
                break
            try:
                summary_val = component.get("SUMMARY") or ""
                if isinstance(summary_val, bytes):
                    summary = summary_val.decode("utf-8", errors="replace").strip() or "Evento"
                else:
                    summary = (summary_val if isinstance(summary_val, str) else str(summary_val)).strip() or "Evento"
                if is_absurd_request(summary):
                    continue
                summary = sanitize_string(summary, 256)[:256]
                dtstart = _get_dt_from_vevent(component, "DTSTART")
                if dtstart is None:
                    continue  # evento sem data de início — ignorar
                dtend = _get_dt_from_vevent(component, "DTEND")
                description = component.get("DESCRIPTION")
                if description:
                    description = (description if isinstance(description, str) else description.decode("utf-8", errors="replace")).strip()[:1024]
                else:
                    description = ""
                location = component.get("LOCATION")
                if location:
                    location = (location if isinstance(location, str) else location.decode("utf-8", errors="replace")).strip()[:256]
                else:
                    location = ""
                url = component.get("URL")
                if url:
                    url = (url if isinstance(url, str) else url.decode("utf-8", errors="replace")).strip()[:512]
                else:
                    url = ""

                payload = {
                    "nome": summary,
                    "data": dtstart.isoformat() if dtstart else "",
                    "data_fim": dtend.isoformat() if dtend else "",
                    "descricao": description,
                    "local": location,
                    "url": url,
                }
                ev = Event(
                    user_id=user_id,
                    tipo="evento",
                    payload=payload,
                    data_at=dtstart,
                    deleted=False,
                )
                db.add(ev)
                db.add(AuditLog(user_id=user_id, action="event_add", resource="ics"))
                db.flush()
                events_created.append({"nome": summary, "data_at": dtstart})
                count += 1

                # Lembrete opcional: 15 min antes (se cron_tool disponível e evento no futuro)
                if cron_tool and dtstart and count <= 10:
                    try:
                        from datetime import timezone
                        now_utc = datetime.now(timezone.utc)
                        if dtstart.tzinfo:
                            dtstart_aware = dtstart
                        else:
                            dtstart_aware = dtstart.replace(tzinfo=timezone.utc)
                        delta = (dtstart_aware - now_utc).total_seconds() - 900  # 15 min antes
                        if 60 < delta < 86400 * 30:  # entre 1 min e 30 dias
                            cron_tool.set_context(cron_channel, chat_id)
                            msg_reminder = f"Lembrete: {summary}"
                            await cron_tool.execute(action="add", message=msg_reminder, in_seconds=int(delta))
                    except Exception as e:
                        logger.debug(f"ics cron reminder failed: {e}")
            except Exception as e:
                logger.debug(f"ics single event failed: {e}")
                continue
        db.commit()
    except Exception as e:
        logger.exception(f"ics_handler failed: {e}")
        if db:
            try:
                db.rollback()
            except Exception:
                pass
        return _summary_message(0, [], lang, error="Erro ao guardar eventos.")
    finally:
        try:
            db.close()
        except Exception:
            pass

    return _summary_message(len(events_created), events_created[:5], lang, with_reminder=bool(cron_tool))


def _summary_message(
    total: int,
    events: list[dict],
    user_lang: str,
    error: str | None = None,
    with_reminder: bool = False,
) -> str:
    """Mensagem de resumo no idioma do utilizador."""
    if error:
        msgs = {
            "pt-PT": error,
            "pt-BR": error,
            "es": error,
            "en": error,
        }
        return msgs.get(user_lang, error)

    if total == 0:
        msgs = {
            "pt-PT": "Nenhum evento encontrado neste calendário.",
            "pt-BR": "Nenhum evento encontrado neste calendário.",
            "es": "No se encontró ningún evento en este calendario.",
            "en": "No events found in this calendar.",
        }
        return msgs.get(user_lang, msgs["en"])

    intro_choices = {
        "pt-PT": f"Encontrados {total} evento(s) no calendário. Registados.",
        "pt-BR": f"Encontrados {total} evento(s) no calendário. Registados.",
        "es": f"Encontrados {total} evento(s) en el calendario. Registrados.",
        "en": f"Found {total} event(s) in the calendar. Registered.",
    }
    intro = intro_choices.get(user_lang, intro_choices["en"])

    lines = [intro]
    for ev in events:
        nome = ev.get("nome", "?")[:40]
        data_at = ev.get("data_at")
        if data_at:
            if isinstance(data_at, datetime):
                data_str = data_at.strftime("%d/%m %H:%M")
            else:
                data_str = str(data_at)[:16]
        else:
            data_str = "—"
        lines.append(f"• «{nome}» {data_str}")
    if with_reminder:
        suffix = {
            "pt-PT": " Vou lembrar-te 15 min antes de cada um.",
            "pt-BR": " Vou te lembrar 15 min antes de cada um.",
            "es": " Te recordaré 15 min antes de cada uno.",
            "en": " I'll remind you 15 min before each.",
        }.get(user_lang, suffix["en"])
        lines[0] = lines[0].rstrip(".") + "." + suffix
    return "\n".join(lines)
