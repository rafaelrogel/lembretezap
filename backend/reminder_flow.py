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
    r"\b(?![2][0][2-9][0-9])\d{4}\b", # 1200 (evita anos 2020-2099)
    r"\d{1,2}\s*(?:am|pm)\b",
    r"\d{1,2}:\d{2}\s*(?:am|pm)\b",  # 3:25 PM, 10:30 AM
)

_HOUR_RE = re.compile("|".join(_HOUR_PATTERNS), re.I)

# Padrões que indicam data explícita (dd/mm, dd-mm, dd de mês, dd mês)
_EXPLICIT_DATE_PATTERNS = (
    r"\d{1,2}\s*/\s*\d{1,2}",                   # 10/03, 10/03/2026
    r"\d{1,2}\s*-\s*\d{1,2}",                   # 10-03, 10-03-2026
    r"\d{1,2}\s+de\s+(?:janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)",  # 10 de março
    r"\d{1,2}\s+(?:janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)",  # 10 março
    r"\d{1,2}\s+de\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)",
    r"\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)",
    r"\d{1,2}\s+de\s+(?:enero|febrero|marzo|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)",
    r"\d{1,2}\s+(?:enero|febrero|marzo|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)",
)
_EXPLICIT_DATE_RE = re.compile("|".join(_EXPLICIT_DATE_PATTERNS), re.I)

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
    True se o texto tem hora explícita (10h, às 14h) mas NÃO palavra de data
    NEM data explícita (dd/mm, dd-mm, dd de mês).
    """
    if not text or len(text.strip()) < 5:
        return False
    t = text.strip().lower()
    if not _HOUR_RE.search(t):
        return False
    # Explicit date format (10/03/2026, 10-03, 10 de março) → not vague
    if _EXPLICIT_DATE_RE.search(t):
        return False
    words = set(re.findall(r"\b\w+\b", t))
    return not bool(words & _DATE_WORDS)


def has_reminder_intent(text: str) -> bool:
    """True se parece pedido de lembrete/agendamento."""
    if not text or len(text.strip()) < 3:
        return False
    tl = text.strip().lower()
    
    # Se o utilizador está apenas a pedir para ver/listar lembretes ou agenda,
    # NÃO é um intent de criação com tempo vago. Devemos ignorar para deixar o router ou o agente processar.
    query_verbs = (
        # PT
        "liste", "listar", "mostre", "mostrar", "mostra", "quais", "ver", "cancelar", "apagar", "remover", "como", "esta", "está", "agenda", "agendas",
        # EN
        "list", "show", "what", "which", "view", "cancel", "delete", "remove", "how", "is", "are", "agenda",
        # ES
        "listar", "muestra", "mostrar", "cuales", "cuáles", "ver", "cancelar", "borrar", "eliminar", "como", "esta", "está", "agenda"
    )
    words = tl.split()
    if any(q in words for q in query_verbs):
        return False
        
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
    try:
        from backend.recurring_event_flow import has_recurrence_indicator
        if has_recurrence_indicator(text):
            return False, "", ""
    except Exception:
        pass
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
    try:
        from backend.recurring_event_flow import has_recurrence_indicator
        if has_recurrence_indicator(text):
            return False, "", 0, 0
    except Exception:
        pass
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


# Word-to-number map for written-out hours (PT/ES/EN)
_WORD_TO_HOUR: dict[str, int] = {
    # Portuguese
    "uma": 1, "duas": 2, "três": 3, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
    "quinze": 15, "dezesseis": 16, "dezasseis": 16, "dezessete": 17, "dezassete": 17,
    "dezoito": 18, "dezenove": 19, "dezanove": 19, "vinte": 20,
    "vinte e uma": 21, "vinte e duas": 22, "vinte e três": 23, "vinte e tres": 23,
    # Spanish
    "uno": 1, "dos": 2, "cuatro": 4, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciséis": 16, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veinte": 20, "veintiuna": 21, "veintidós": 22, "veintidos": 22,
    "veintitrés": 23, "veintitres": 23,
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20,
}

def _parse_written_time(text: str) -> tuple[int, int] | None:
    """Parse written-out time: 'duas da tarde', 'quatorze horas', 'meio-dia', 'three thirty pm', etc."""
    t = text.strip().lower()
    # meio-dia / mediodía / noon
    if re.search(r"\b(meio[\s-]?dia|mediod[ií]a|noon)\b", t):
        return (12, 0)
    # meia-noite / medianoche / midnight
    if re.search(r"\b(meia[\s-]?noite|medianoche|midnight)\b", t):
        return (0, 0)

    # Extract minute modifiers FIRST (before hour lookup consumes "quinze" etc.)
    minute = 0
    t_for_hour = t
    if re.search(r"\b(e\s+meia|y\s+media|thirty|half)\b", t):
        minute = 30
        t_for_hour = re.sub(r"\b(e\s+meia|y\s+media|thirty|half)\b", "", t).strip()
    elif re.search(r"\b(e\s+quarenta\s+e\s+cinco|forty[\s-]?five)\b", t):
        minute = 45
        t_for_hour = re.sub(r"\b(e\s+quarenta\s+e\s+cinco|forty[\s-]?five)\b", "", t).strip()
    elif re.search(r"\be\s+quinze\b", t):
        minute = 15
        t_for_hour = re.sub(r"\be\s+quinze\b", "", t).strip()
    elif re.search(r"\b(y\s+cuarto|fifteen|quarter)\b", t):
        minute = 15
        t_for_hour = re.sub(r"\b(y\s+cuarto|fifteen|quarter)\b", "", t).strip()

    # Try to find a written hour word (sort by length desc so "vinte e três" matches before "três")
    found_hour = None
    for word, h in sorted(_WORD_TO_HOUR.items(), key=lambda x: -len(x[0])):
        if word in t_for_hour:
            found_hour = h
            break
    if found_hour is None:
        return None

    # AM/PM: "da tarde/noite" → PM, "da manhã/madrugada" → AM
    if found_hour <= 12:
        if re.search(r"\b(da\s+tarde|da\s+noite|de\s+la\s+tarde|de\s+la\s+noche|p\.?m\.?)\b", t):
            if found_hour < 12:
                found_hour += 12
        elif re.search(r"\b(da\s+manh[ãa]|da\s+madrugada|de\s+la\s+ma[ñn]ana|a\.?m\.?)\b", t):
            if found_hour == 12:
                found_hour = 0

    if 0 <= found_hour <= 23 and 0 <= minute <= 59:
        return (found_hour, minute)
    return None


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
    # 1) Numeric patterns first
    for pattern, extractor in _TIME_RESPONSE_PATTERNS:
        m = re.search(pattern, t, re.I)
        if m:
            try:
                h, mn = extractor(m)
                if 0 <= h <= 23 and 0 <= mn <= 59:
                    return h, mn
            except (ValueError, IndexError, AttributeError):
                pass
    # 2) Written-out time ("duas da tarde", "quatorze horas", "meio-dia")
    return _parse_written_time(t)


# Parsing de antecedência (30 min, 1 hora)
_ADVANCE_PATTERNS = (
    (r"(\d+)\s*min(?:uto?s?)?", lambda m: int(m.group(1)) * 60),
    (r"(\d+)\s*h(?:ora?s?)?", lambda m: int(m.group(1)) * 3600),
    (r"meia\s*hora", lambda m: 1800),
    (r"30\s*min", lambda m: 1800),
    (r"1\s*hora", lambda m: 3600),
    (r"1\s*hr", lambda m: 3600),
)


def parse_advance_seconds(text: str) -> int | None:
    """Extrai segundos de antecedência. Retorna None se inválido."""
    if not text or not text.strip():
        return None
    t = text.strip().lower()
    # Remover "antes" ou "before" ou "atrás" para simplificar o match
    t = re.sub(r"\b(antes|before|atrás|atras)\b", "", t).strip()
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
    has_date_word = bool(words & _DATE_WORDS)
    has_explicit_date = bool(_EXPLICIT_DATE_RE.search(text.strip()))
    return has_date_word or has_explicit_date


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
            return int(delta)
    except Exception:
        pass
    return None
