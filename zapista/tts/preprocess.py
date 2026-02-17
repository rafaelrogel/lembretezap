"""
Pré-processamento de texto para TTS: remove formatação e normaliza horários.

- Remove wildcards de markdown (*, _) para o TTS ler só as palavras.
- Converte horários (18h, 18:00, 1800, noon, 18h-19h, etc.) para forma falada.
"""

import re


def strip_markdown_for_tts(text: str) -> str:
    """
    Remove caracteres de formatação (*, _) para o TTS não ler "asterisco" ou "sublinhado".
    Mantém apenas o texto, sem alterar espaços entre palavras.
    """
    if not text:
        return text
    # Remove * e _ (usados em *negrito* e _itálico_ no WhatsApp)
    return text.replace("*", "").replace("_", "")


# Padrões de horário (ordem de aplicação importa: 12h e intervalos antes de h/:)
_RE_12H = re.compile(
    r"\b(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)\b",
    re.IGNORECASE,
)  # 6pm, 6 am, 6:30pm, 6:30 p.m.
_RE_NOON_MIDNIGHT = re.compile(
    r"\b(noon|midnight|meio-dia|meia-noite|mediodía|medianoche)\b",
    re.IGNORECASE,
)
_RE_INTERVAL = re.compile(
    r"\b(\d{1,2})(?:\s*[hH:]?\s*\d{0,2})?\s*[-–—]\s*(\d{1,2})(?:\s*[hH:]?\s*\d{0,2})?\b",
    re.IGNORECASE,
)  # 18h-19h, 18-19, 18:00-19:00
_RE_H_MIN_SUFFIX = re.compile(
    r"\b(\d{1,2})\s*[hH]\s*(\d{1,2})\s*(?:m|min)\b",
)  # 18h30m, 18h05min (antes do padrão geral para não sobrar "m")
_RE_H_HMM = re.compile(
    r"\b(\d{1,2})\s*[hH:]\s*(\d{0,2})\s*(?::(\d{2}))?\b"
)  # 18h, 18h00, 18:00, 18:00:00 (segundos ignorados)
_RE_DASH = re.compile(
    r"\b(\d{1,2})-(\d{2})\b"
)  # 18-00, 9-30 (traço; 00-59 no 2º grupo evita 2024-01)
_RE_DOT_H = re.compile(
    r"\b(\d{1,2})\.(\d{2})\s*[hH]\b"
)  # 18.00h, 18.00 h (europeu com h no final)
_RE_DOT = re.compile(
    r"\b(\d{1,2})\.(\d{2})\b"
)  # 18.00, 9.30 (ponto como separador)
_RE_SPACE_HM = re.compile(
    r"\b(\d{1,2})\s+(\d{2})\b"
)  # 18 00, 9 30 (espaço; 2º grupo 00-59)
_RE_4DIGITS = re.compile(
    r"\b(\d{3,4})\b"
)  # 1800, 1830, 930 (hora+minuto; 1900-2099 = ano)

# Frases por idioma: (hora sem minuto, hora e minutos). pt = pt-BR e pt-PT.
_TIME_PHRASES: dict[str, tuple[str, str]] = {
    "pt": ("{h} horas", "{h} horas e {m}"),
    "es": ("{h} horas", "{h} horas y {m}"),
    "en": ("{h} hours", "{h} hours and {m}"),
}

# Meio-dia / meia-noite por locale (para substituir palavra em qualquer idioma)
_NOON_MIDNIGHT_PHRASES: dict[str, tuple[str, str]] = {
    "pt": ("meio-dia", "meia-noite"),
    "es": ("mediodía", "medianoche"),
    "en": ("noon", "midnight"),
}

# Intervalo: "X horas às Y horas" etc.
_INTERVAL_PHRASES: dict[str, str] = {
    "pt": "{h1} horas às {h2} horas",
    "es": "{h1} horas a {h2} horas",
    "en": "{h1} hours to {h2} hours",
}


def _locale_to_time_key(locale: str) -> str:
    """Mapeia locale (pt-BR, pt-PT, es, en) para chave do _TIME_PHRASES."""
    if not locale:
        return "pt"
    base = locale.split("-")[0].lower()
    return "pt" if base in ("pt", "ptbr", "ptpt") else base


def _digits_to_spoken_time(h: int, m: int, locale: str) -> str:
    """Converte hora e minuto para frase falada conforme o locale (pt-BR, pt-PT, es, en)."""
    m = max(0, min(59, m))
    # 24:00 = meia-noite
    if h >= 24 or h < 0:
        h = 0
    key = _locale_to_time_key(locale)
    if h == 0 and m == 0:
        return _NOON_MIDNIGHT_PHRASES.get(key, _NOON_MIDNIGHT_PHRASES["pt"])[1]
    noon_midnight = _NOON_MIDNIGHT_PHRASES.get(key, _NOON_MIDNIGHT_PHRASES["pt"])
    if h == 12 and m == 0:
        return noon_midnight[0]
    h = max(0, min(23, h))
    phrases = _TIME_PHRASES.get(key, _TIME_PHRASES["pt"])
    template = phrases[1] if m else phrases[0]
    return template.format(h=h, m=m)


def _parse_4digit_time(s: str) -> tuple[int, int] | None:
    """Interpreta 1800 -> (18,0), 1830 -> (18,30), 930 -> (9,30), 905 -> (9,5)."""
    if len(s) == 4:
        val = int(s)
        if 1900 <= val <= 2099:
            return None  # provável ano, não horário
        h = int(s[:2])
        m = int(s[2:])
        if h <= 23 and m <= 59:
            return (h, m)
    if len(s) == 3:
        h = int(s[0])
        m = int(s[1:])
        if h <= 9 and m <= 59:
            return (h, m)
    return None


def _12h_to_24h(h: int, am_pm: str) -> int:
    """Converte 12h (1-12) + am/pm para 24h (0-23)."""
    h = max(1, min(12, h))
    is_pm = am_pm.lower().startswith("p")
    if is_pm:
        return 12 if h == 12 else h + 12
    return 0 if h == 12 else h


def _noon_midnight_word_to_phrase(word: str, locale: str) -> str:
    """Substitui palavra noon/midnight/meio-dia/meia-noite/mediodía/medianoche pela frase no locale."""
    key = _locale_to_time_key(locale)
    phrases = _NOON_MIDNIGHT_PHRASES.get(key, _NOON_MIDNIGHT_PHRASES["pt"])
    w = word.lower()
    if w in ("noon", "meio-dia", "mediodía"):
        return phrases[0]
    if w in ("midnight", "meia-noite", "medianoche"):
        return phrases[1]
    return word


def normalize_times_for_tts(text: str, locale: str) -> str:
    """
    Substitui horários por forma falada para o TTS.
    Formatos: 18h, 18h00, 18:00, 18.00, 18-00, 18 00, 18:00:00, 6pm, noon, 18h-19h, 1800, 930.
    locale: pt-BR, pt-PT, es, en.
    """
    if not text or not locale:
        return text

    # 1) 12h (6pm, 6:30pm) primeiro
    def replace_12h(m: re.Match) -> str:
        hour_12 = int(m.group(1))
        min_str = m.group(2)
        minute = int(min_str) if min_str else 0
        if minute <= 59:
            hour_24 = _12h_to_24h(hour_12, m.group(3))
            return _digits_to_spoken_time(hour_24, minute, locale)
        return m.group(0)

    result = _RE_12H.sub(replace_12h, text)

    # 2) Palavras meio-dia / meia-noite (qualquer idioma → frase no locale)
    result = _RE_NOON_MIDNIGHT.sub(
        lambda m: _noon_midnight_word_to_phrase(m.group(0), locale), result
    )

    # 3) Intervalos 18h-19h, 18-19 (só quando o 2º número é 0-23, senão é hora 9-30)
    def replace_interval(m: re.Match) -> str:
        h1 = int(m.group(1))
        h2 = int(m.group(2))
        if h2 > 23:
            return m.group(0)
        h1 = max(0, min(23, h1))
        h2 = max(0, min(23, h2))
        key = _locale_to_time_key(locale)
        tpl = _INTERVAL_PHRASES.get(key, _INTERVAL_PHRASES["pt"])
        return tpl.format(h1=h1, h2=h2)

    result = _RE_INTERVAL.sub(replace_interval, result)

    # 4) 18h30m, 18h05min
    def replace_h_min_suffix(m: re.Match) -> str:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if hour <= 23 and minute <= 59:
            return _digits_to_spoken_time(hour, minute, locale)
        return m.group(0)

    result = _RE_H_MIN_SUFFIX.sub(replace_h_min_suffix, result)

    # 4b) 18.00h, 18.00 h (antes do padrão h/colon para não confundir "0 h" com meia-noite)
    def replace_dot_h(m: re.Match) -> str:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if hour <= 23 and minute <= 59:
            return _digits_to_spoken_time(hour, minute, locale)
        return m.group(0)

    result = _RE_DOT_H.sub(replace_dot_h, result)

    # 5) 18h, 18:00, 18:00:00 (segundos ignorados)
    def replace_h_colon(m: re.Match) -> str:
        hour = int(m.group(1))
        min_str = m.group(2)
        minute = int(min_str) if min_str and min_str.strip() else 0
        if minute <= 59:
            return _digits_to_spoken_time(hour, minute, locale)
        return m.group(0)

    result = _RE_H_HMM.sub(replace_h_colon, result)

    # 6) 18-00, 9-30 (traço; evita 2024-01 exigindo 00-59)
    def replace_dash(m: re.Match) -> str:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if hour <= 23 and minute <= 59:
            return _digits_to_spoken_time(hour, minute, locale)
        return m.group(0)

    result = _RE_DASH.sub(replace_dash, result)

    # 7) 18.00, 9.30
    def replace_dot(m: re.Match) -> str:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if hour <= 23 and minute <= 59:
            return _digits_to_spoken_time(hour, minute, locale)
        return m.group(0)

    result = _RE_DOT.sub(replace_dot, result)

    # 9) 18 00, 9 30 (espaço; só quando 2º grupo 00-59 para não pegar "5 12" como hora)
    def replace_space_hm(m: re.Match) -> str:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if hour <= 23 and minute <= 59:
            return _digits_to_spoken_time(hour, minute, locale)
        return m.group(0)

    result = _RE_SPACE_HM.sub(replace_space_hm, result)

    # 10) 1800, 1830, 930 (4 dígitos; 1900-2099 = ano)
    def replace_4digits(m: re.Match) -> str:
        parsed = _parse_4digit_time(m.group(1))
        if parsed is None:
            return m.group(0)
        h, min_val = parsed
        return _digits_to_spoken_time(h, min_val, locale)

    result = _RE_4DIGITS.sub(replace_4digits, result)
    return result


def prepare_text_for_tts(text: str, locale: str = "pt-BR") -> str:
    """
    Prepara texto para síntese: remove markdown e normaliza horários.
    Deve ser chamado com o locale do áudio (pt-BR, pt-PT, es, en).
    """
    if not text:
        return text
    t = strip_markdown_for_tts(text)
    t = normalize_times_for_tts(t, locale)
    return t
