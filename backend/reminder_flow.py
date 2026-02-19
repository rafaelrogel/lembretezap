"""Fluxo de clarificação quando o utilizador indica evento com data/hora incompleta.

Caso 1 - Data sem hora: "tenho consulta amanhã" → "A que horas é a sua consulta?"
Caso 2 - Hora sem data: "médico às 10h" → "Que dia é a consulta? Amanhã? Hoje?"

Depois: pedir antecedência ou só na hora; se antecedência, quanto tempo antes.
"""

import re
from typing import Any

from backend.guardrails import is_vague_reminder_message
from backend.reminder_keywords import ALL_REMINDER_KEYWORDS

# Palavras de data SEM hora explícita (quando sozinhas = tempo vago)
_DATE_WORDS = {
    "amanhã", "amanha", "hoje", "depois", "tomorrow", "today",
    "segunda", "terça", "terca", "quarta", "quinta", "sexta",
    "sábado", "sabado", "domingo", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday",
}
# Padrões que indicam hora explícita (se presentes, não é tempo vago)
_HOUR_PATTERNS = (
    r"\d{1,2}\s*h(?:oras?)?\b",
    r"\d{1,2}:\d{2}",
    r"\d{1,2}h\d{0,2}\b",  # 10h, 10h00
    r"às?\s*\d{1,2}(?:[:h]\d{2})?",
    r"as\s*\d{1,2}(?:[:h]\d{2})?",
    r"(?:às?|as)\s*\d{4}\b",
    r"\b\d{2}h\d{2}?\b", # 12h, 12h00
    r"\b\d{4}\b",        # 1200
    r"\d{1,2}\s*(?:am|pm)\b",
    r"\d{1,2}:\d{2}\s*(?:am|pm)\b",  # 3:25 PM, 10:30 AM
)

_HOUR_RE = re.compile("|".join(_HOUR_PATTERNS), re.I)

# Indicadores de pedido de lembrete/evento (conteúdo concreto) vindo de reminder_keywords.py
_REMINDER_HINTS = (
    "ir ", "tenho ", "preciso ", "consulta", "reunião", "reuniao",
    "médico", "medico", "dentista", "farmacia", "farmácia",
    "appointment", "meeting",
) + tuple(ALL_REMINDER_KEYWORDS)

FLOW_KEY = "pending_reminder_flow"
STAGE_NEED_TIME = "need_time"
STAGE_NEED_DATE = "need_date"
STAGE_NEED_ADVANCE_PREFERENCE = "need_advance_preference"
STAGE_NEED_ADVANCE_AMOUNT = "need_advance_amount"

MAX_RETRIES = 3  # Insistir até 3x em respostas inválidas

# Variantes: vague_time = temos data, falta hora | vague_date = temos hora, falta data
FLOW_VARIANT_VAGUE_TIME = "vague_time"
FLOW_VARIANT_VAGUE_DATE = "vague_date"


def has_vague_time(text: str) -> bool:
    """
    True se o texto tem palavra de data (amanhã, hoje, segunda...) mas NÃO hora explícita.
    """
    if not text or len(text.strip()) < 5:
        return False
    t = text.strip().lower()
    if _HOUR_RE.search(t):
        return False
    words = set(re.findall(r"\b\w+\b", t))
    return bool(words & _DATE_WORDS)


def has_vague_date(text: str) -> bool:
    """
    True se o texto tem hora explícita (10h, às 14h) mas NÃO palavra de data.
    """
    if not text or len(text.strip()) < 5:
        return False
    t = text.strip().lower()
    if not _HOUR_RE.search(t):
        return False
    words = set(re.findall(r"\b\w+\b", t))
    return not bool(words & _DATE_WORDS)


def has_reminder_intent(text: str) -> bool:
    """True se parece pedido de lembrete/agendamento."""
    if not text or len(text.strip()) < 3:
        return False
    tl = text.strip().lower()
    return any(h in tl for h in _REMINDER_HINTS)


def extract_content_and_date(text: str) -> tuple[str, str]:
    """
    Extrai o conteúdo do evento e a palavra de data.
    Retorna (conteudo, data_label) ex: ("ir ao médico", "amanhã").
    """
    t = text.strip()
    if not t:
        return "", ""
    tl = t.lower()
    content = t
    date_label = ""
    for dw in sorted(_DATE_WORDS, key=len, reverse=True):
        if dw in tl:
            date_label = dw
            # Remover "na segunda", "amanhã" ou só a palavra
            content = re.sub(rf"\b(?:na|no|dia)\s+{re.escape(dw)}\b", "", t, flags=re.I)
            content = re.sub(rf"\b{re.escape(dw)}\b", "", content, flags=re.I).strip()
            content = re.sub(r"\s+", " ", content).strip()
            break
    return content or t, date_label


def _extract_hour_minute(text: str) -> tuple[int, int] | None:
    """Extrai hora e minuto do texto. Retorna (h, m) ou None."""
    for pattern, extractor in _TIME_RESPONSE_PATTERNS:
        m = re.search(pattern, text.strip(), re.I)
        if m:
            try:
                h, mn = extractor(m)
                if 0 <= h <= 23 and 0 <= mn <= 59:
                    return h, mn
            except (ValueError, IndexError, AttributeError):
                pass
    return None


def extract_content_and_hour(text: str) -> tuple[str, int, int]:
    """
    Extrai conteúdo e hora quando temos hora mas não data.
    Retorna (conteudo, hour, minute) ex: ("ir ao médico", 10, 0).
    """
    t = text.strip()
    if not t:
        return "", 0, 0
    parsed = _extract_hour_minute(t)
    if not parsed:
        return t, 0, 0
    hour, minute = parsed
    # Remover padrões de hora para obter o conteúdo
    content = re.sub(_HOUR_RE, " ", t).strip()
    content = re.sub(r"\bàs?\s*", "", content, flags=re.I)
    content = re.sub(r"\bas\s+", "", content, flags=re.I)
    content = re.sub(r"\s+", " ", content).strip()
    return content or t, hour, minute


def is_vague_time_reminder(text: str) -> tuple[bool, str, str]:
    """
    Detecta se é pedido de lembrete com conteúdo concreto mas tempo vago.
    Retorna (ok, content, date_label). ok=True quando devemos iniciar o fluxo.
    """
    if not text or len(text.strip()) < 5:
        return False, "", ""
    if is_vague_reminder_message(text):
        return False, "", ""
    if not has_vague_time(text):
        return False, "", ""
    if not has_reminder_intent(text):
        return False, "", ""
    content, date_label = extract_content_and_date(text)
    if not content or len(content.strip()) < 2:
        return False, "", ""
    return True, content.strip(), date_label


def is_vague_date_reminder(text: str) -> tuple[bool, str, int, int]:
    """
    Detecta se é pedido de lembrete com conteúdo + hora mas SEM data.
    Retorna (ok, content, hour, minute). ok=True quando devemos iniciar o fluxo.
    Ex.: "médico às 10h", "consulta às 14:30".
    """
    if not text or len(text.strip()) < 5:
        return False, "", 0, 0
    if is_vague_reminder_message(text):
        return False, "", 0, 0
    if not has_vague_date(text):
        return False, "", 0, 0
    if not has_reminder_intent(text):
        return False, "", 0, 0
    content, hour, minute = extract_content_and_hour(text)
    if not content or len(content.strip()) < 2:
        return False, "", 0, 0
    return True, content.strip(), hour, minute


def parse_date_from_response(text: str) -> str | None:
    """
    Extrai palavra de data da resposta ("amanhã", "hoje", "segunda", etc).
    Retorna a label normalizada ou None.
    """
    if not text or not text.strip():
        return None
    t = text.strip().lower()
    words = set(re.findall(r"\b\w+\b", t))
    for dw in _DATE_WORDS:
        if dw in words or dw in t:
            return dw
    # "na segunda", "dia 15" etc
    for dw in ("amanhã", "amanha", "hoje", "segunda", "terça", "terca", "quarta", "quinta", "sexta", "sábado", "sabado", "domingo"):
        if dw in t or f"na {dw}" in t or f"no {dw}" in t:
            return dw
    return None


def _am_pm_to_24(m) -> tuple[int, int]:
    """Converte 3:25 PM -> (15, 25); 12:00 AM -> (0, 0); 12:00 PM -> (12, 0)."""
    h = int(m.group(1))
    mn = int(m.group(2) or 0)
    pm = (m.group(3).lower() == "pm")
    h24 = (h % 12) + (12 if pm else 0)
    return (h24, mn)


# Parsing de hora na resposta do utilizador
_TIME_RESPONSE_PATTERNS = (
    (r"(\d{1,2}):(\d{2})\s*(am|pm)\b", _am_pm_to_24),  # 3:25 PM, 10:30 AM (antes dos outros)
    (r"(\d{1,2})\s*(am|pm)\b", lambda m: ((int(m.group(1)) % 12) + (12 if m.group(2).lower() == "pm" else 0), 0)),
    (r"(?:às?|as)\s*(\d{1,2})(?:[:h])?(\d{2})?\b", lambda m: (int(m.group(1)), int(m.group(2) or 0))),
    (r"(\d{1,2})h(\d{2})\b", lambda m: (int(m.group(1)), int(m.group(2)))),  # 10h00
    (r"(\d{1,2})(?::(\d{2}))?\s*h", lambda m: (int(m.group(1)), int(m.group(2) or 0))),
    (r"^(\d{4})$", lambda m: (int(m.group(1)[:2]), int(m.group(1)[2:]))),    # 1200
    (r"^(\d{1,2})(?::(\d{2}))?\s*$", lambda m: (int(m.group(1)), int(m.group(2) or 0))),
    (r"^(\d{1,2})\s*$", lambda m: (int(m.group(1)), 0)),
    (r"(\d{1,2})\s*horas?", lambda m: (int(m.group(1)), 0)),
)


def parse_time_from_response(text: str) -> tuple[int, int] | None:
    """Extrai hora e minuto da resposta. Retorna (hora, minuto) ou None."""
    if not text or not text.strip():
        return None
    t = text.strip()
    for pattern, extractor in _TIME_RESPONSE_PATTERNS:
        m = re.search(pattern, t, re.I)
        if m:
            try:
                h, mn = extractor(m)
                if 0 <= h <= 23 and 0 <= mn <= 59:
                    return h, mn
            except (ValueError, IndexError, AttributeError):
                pass
    return None


# Parsing de antecedência (30 min, 1 hora)
_ADVANCE_PATTERNS = (
    (r"(\d+)\s*min(?:uto?s?)?", lambda m: int(m.group(1)) * 60),
    (r"(\d+)\s*h(?:ora?s?)?", lambda m: int(m.group(1)) * 3600),
    (r"meia\s*hora", lambda m: 1800),
    (r"30\s*min", lambda m: 1800),
    (r"1\s*hora", lambda m: 3600),
)


def parse_advance_seconds(text: str) -> int | None:
    """Extrai segundos de antecedência. Retorna None se inválido."""
    if not text or not text.strip():
        return None
    t = text.strip().lower()
    for pattern, extractor in _ADVANCE_PATTERNS:
        m = re.search(pattern, t, re.I)
        if m:
            try:
                sec = extractor(m)
                if 60 <= sec <= 86400:  # 1 min a 24h
                    return sec
            except (ValueError, IndexError, AttributeError):
                pass
    return None


def looks_like_advance_preference_yes(text: str) -> bool:
    """Resposta indicando que quer antecedência."""
    t = (text or "").strip().lower()
    if not t or len(t) > 60:
        return False
    return any(
        p in t for p in ("antec", "antes", "com antec", "sim", "quero", "yes", "30", "1 hora", "meia hora")
    ) and not any(p in t for p in ("não", "nao", "só na hora", "só na hora", "apenas na hora", "no", "just in time"))


def looks_like_advance_preference_no(text: str) -> bool:
    """Resposta indicando que NÃO quer antecedência."""
    t = (text or "").strip().lower()
    if not t or len(t) > 80:
        return False
    return any(
        p in t for p in ("apenas na hora", "só na hora", "na hora", "só no momento", "no momento", "nao", "não", "no")
    )


def looks_like_no_reminder_at_all(text: str) -> bool:
    """Resposta indicando que NÃO quer NENHUM lembrete (nem na hora)."""
    t = (text or "").strip().lower()
    if not t or len(t) > 100:
        return False
    no_phrases = (
        "não quero", "nao quero", "não preciso", "nao preciso", "dispensa", "dispenso",
        "não é preciso", "nao e preciso", "não precisa", "nao precisa", "não lembrar", "nao lembrar",
        "não precisa lembrar", "nao precisa lembrar", "sem lembrete", "não quero lembrete",
        "nao quero lembrete", "skip", "pular", "nada", "obrigado não", "obrigada não",
        "don't need", "no need", "skip reminder", "no reminder", "don't remind",
        "no hace falta", "no necesito", "no quiero", "dispenso", "saltar",
        "não obrigado", "nao obrigado", "não obrigada", "nao obrigada",
    )
    return any(p in t for p in no_phrases)


def is_consulta_context(content: str) -> bool:
    """True se o conteúdo sugere consulta (médico, dentista, etc.) → usar 'A que horas é a sua consulta?'."""
    if not content:
        return False
    tl = content.lower()
    return any(
        p in tl for p in ("médico", "medico", "consulta", "dentista", "doutor", "dr.", "clínica", "clinic")
    )


def has_full_event_datetime(text: str) -> bool:
    """
    True se a mensagem parece um evento/compromisso com data E hora já indicados
    (ex.: "preciso ir ao médico amanhã às 17h00", "tenho consulta amanhã 10h").
    Retorna False se for recorrência (toda segunda, todo dia, etc.) — esses vão para o fluxo recorrente.
    """
    if not text or len(text.strip()) < 10:
        return False
    try:
        from backend.recurring_event_flow import has_recurrence_indicator
        if has_recurrence_indicator(text):
            return False
    except Exception:
        pass
    if not has_reminder_intent(text):
        return False
    if not _HOUR_RE.search(text.strip()):
        return False
    words = set(re.findall(r"\b\w+\b", text.strip().lower()))
    return bool(words & _DATE_WORDS)


def parse_full_event_datetime(
    text: str, tz_iana: str = "UTC"
) -> tuple[str, int, Any] | None:
    """
    Extrai (content, in_seconds, data_at) de uma mensagem com evento + data + hora.
    data_at = datetime no fuso tz_iana (para registar na agenda).
    Retorna None se não conseguir parsear.
    """
    if not has_full_event_datetime(text):
        return None
    t = text.strip()
    tl = t.lower()
    # Extrair hora e minuto (ex.: às 17h00, 17:00, 17h)
    hour, minute = 0, 0
    for pattern, extractor in _TIME_RESPONSE_PATTERNS:
        m = re.search(pattern, t, re.I)
        if m:
            try:
                h, mn = extractor(m)
                if 0 <= h <= 23 and 0 <= mn <= 59:
                    hour, minute = h, mn
                    break
            except (ValueError, IndexError, AttributeError):
                pass
    # Extrair data (amanhã, hoje, segunda...)
    date_label = ""
    for dw in sorted(_DATE_WORDS, key=len, reverse=True):
        if dw in tl:
            date_label = dw
            break
    if not date_label:
        return None
    # Conteúdo: remover data e hora do texto
    content = re.sub(_HOUR_RE, " ", t)
    for dw in (date_label, "às", "as", "à", "a"):
        content = re.sub(rf"\b{re.escape(dw)}\b", "", content, flags=re.I)
    content = re.sub(r"\s+", " ", content).strip()
    if not content or len(content) < 2:
        return None
    in_sec = compute_in_seconds_from_date_hour(date_label, hour, minute, tz_iana)
    if not in_sec or in_sec <= 0:
        return None
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    try:
        z = ZoneInfo(tz_iana)
        try:
            from zapista.clock_drift import get_effective_time
            _now_ts = get_effective_time()
        except Exception:
            _now_ts = __import__("time").time()
        now = datetime.fromtimestamp(_now_ts, tz=timezone.utc).astimezone(z)
        today = now.date()
        dl = date_label.lower().strip()
        target_date = today
        if dl in ("amanhã", "amanha", "tomorrow"):
            target_date = today + timedelta(days=1)
        elif dl in ("hoje", "today"):
            target_date = today
        elif dl in ("segunda", "terça", "terca", "quarta", "quinta", "sexta", "sábado", "sabado", "domingo"):
            from backend.time_parse import DIAS_SEMANA
            dow_target = DIAS_SEMANA.get(dl)
            if dow_target is not None:
                today_cron = (now.weekday() + 1) % 7
                diff = (dow_target - today_cron) % 7
                if diff == 0 and (now.hour > hour or (now.hour == hour and now.minute >= minute)):
                    diff = 7
                target_date = today + timedelta(days=diff)
        data_at = datetime(
            target_date.year, target_date.month, target_date.day,
            hour, minute, 0, 0, tzinfo=z
        )
        return (content, in_sec, data_at)
    except Exception:
        return None


def compute_in_seconds_from_date_hour(
    date_label: str, hour: int, minute: int, tz_iana: str = "UTC"
) -> int | None:
    """
    Calcula in_seconds para «date_label» às hour:minute no fuso tz_iana.
    date_label: "amanhã", "hoje", "segunda", etc.
    Usa tempo efectivo (clock_drift) para coincidir com o executor do cron.
    """
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    try:
        z = ZoneInfo(tz_iana)
        try:
            from zapista.clock_drift import get_effective_time
            _now_ts = get_effective_time()
        except Exception:
            _now_ts = __import__("time").time()
        now = datetime.fromtimestamp(_now_ts, tz=timezone.utc).astimezone(z)
        today = now.date()

        # #region agent log
        try:
            import json as _j
            _log_path = r"C:\Users\rafae\.nanobot\.cursor\debug.log"
            open(_log_path, "a", encoding="utf-8").write(_j.dumps({"location": "reminder_flow.compute_in_seconds.entry", "message": "compute_in_seconds", "data": {"tz_iana": tz_iana, "date_label": date_label, "hour": hour, "minute": minute, "now_str": now.isoformat()[:25]}, "timestamp": __import__("time").time() * 1000, "hypothesisId": "H3"}) + "\n")
        except Exception:
            pass
        # #endregion

        target_date = today
        dl = date_label.lower().strip()

        if dl in ("amanhã", "amanha", "tomorrow"):
            target_date = today + timedelta(days=1)
        elif dl in ("hoje", "today"):
            target_date = today
        elif dl in ("segunda", "terça", "terca", "quarta", "quinta", "sexta", "sábado", "sabado", "domingo"):
            from backend.time_parse import DIAS_SEMANA
            dow_target = DIAS_SEMANA.get(dl)
            if dow_target is not None:
                today_cron = (now.weekday() + 1) % 7  # Python: 0=Mon -> cron 1
                diff = (dow_target - today_cron) % 7
                if diff == 0 and (now.hour > hour or (now.hour == hour and now.minute >= minute)):
                    diff = 7
                target_date = today + timedelta(days=diff)
        else:
            return None

        target = datetime(
            target_date.year, target_date.month, target_date.day,
            hour, minute, 0, 0, tzinfo=z
        )
        delta = (target - now).total_seconds()
        if delta > 0 and delta <= 86400 * 365:
            # #region agent log
            try:
                import json as _j
                _log_path = r"C:\Users\rafae\.nanobot\.cursor\debug.log"
                open(_log_path, "a", encoding="utf-8").write(_j.dumps({"location": "reminder_flow.compute_in_seconds.exit", "message": "computed delta", "data": {"target_str": target.isoformat()[:25], "delta_sec": int(delta), "tz_iana": tz_iana}, "timestamp": __import__("time").time() * 1000, "hypothesisId": "H3"}) + "\n")
            except Exception:
                pass
            # #endregion
            return int(delta)
    except Exception:
        pass
    return None
