"""Parser de períodos temporais para queries de listagem de lembretes/eventos.

Extrai intervalo de datas de qualificadores como:
  - "para 2027", "in 2027", "año 2027"
  - "esta semana", "this week", "esta semana"
  - "em março", "in march", "en marzo"
  - "próxima semana", "next week", "semana que vem"
  - "este mês", "this month", "este mes"
  - "para hoje", "for today", "para hoy"
  - "para amanhã", "for tomorrow", "para mañana"

Suporta pt-BR, pt-PT, EN, ES.
"""

import re
from datetime import date, timedelta
from typing import Tuple, Optional

# ---------------------------------------------------------------------------
# Mapeamento de nomes de meses → número (1-12) — 4 idiomas
# ---------------------------------------------------------------------------
_MONTH_NAMES: dict[str, int] = {
    # PT
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    # EN
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    # ES
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Year: "para 2027", "de 2027", "em 2027", "ano de 2027", "in 2027", "for 2027",
#        "year 2027", "año 2027", "del 2027"
_RE_YEAR = re.compile(
    r"(?:para\s+o?\s*ano\s+(?:de\s+)?|ano\s+(?:de\s+)?|para\s+|de\s+|em\s+|in\s+|for\s+|year\s+|año\s+(?:de\s+)?|del\s+|at[eé]\s+|until\s+|hasta\s+)"
    r"(\d{4})\b",
    re.I,
)

# Month: "para março", "em março", "de março", "in march", "for march", "en marzo", "para marzo"
_MONTH_PATTERN = "|".join(_MONTH_NAMES.keys())
_RE_MONTH = re.compile(
    r"(?:para\s+|em\s+|de\s+|in\s+|for\s+|en\s+)"
    rf"({_MONTH_PATTERN})"
    r"(?:\s+(?:de\s+)?(\d{4}))?",
    re.I,
)

# This week: "esta semana", "dessa semana", "para esta semana", "this week", "esta semana" (ES)
_RE_THIS_WEEK = re.compile(
    r"(?:para\s+)?(?:esta|dessa|d?esta)\s+semana|this\s+week|\bsemana\b",
    re.I,
)

# This year: "este ano", "esse ano", "deste ano", "este año", "this year"
_RE_THIS_YEAR = re.compile(
    r"(?:para\s+)?(?:d?est[ea]\s+ano|this\s+year|este\s+a[nñ]o|\bano\b|\ba[nñ]o\b|\byear\b)",
    re.I,
)

# Next week: "próxima semana", "proxima semana", "semana que vem", "next week", "próxima semana" (ES)
_RE_NEXT_WEEK = re.compile(
    r"(?:para\s+)?(?:pr[oó]xima\s+semana|semana\s+que\s+vem|next\s+week)",
    re.I,
)

# This month: "este mês", "esse mês", "deste mês", "este mes", "this month"
_RE_THIS_MONTH = re.compile(
    r"(?:para\s+)?(?:d?est[ea]\s+m[eê]s|this\s+month|\bm[eê]s\b|\bmonth\b)",
    re.I,
)

# Next month: "próximo mês", "proximo mes", "mês que vem", "next month", "próximo mes" (ES)
_RE_NEXT_MONTH = re.compile(
    r"(?:para\s+)?(?:pr[oó]ximo\s+m[eê]s|m[eê]s\s+que\s+vem|next\s+month)",
    re.I,
)

# Today: "para hoje", "de hoje", "for today", "today's", "para hoy", "de hoy"
_RE_TODAY = re.compile(
    r"(?:para\s+hoje|de\s+hoje|for\s+today|today'?s?|para\s+hoy|de\s+hoy)",
    re.I,
)

# Tomorrow: "para amanhã", "para amanha", "for tomorrow", "para mañana", "para manana"
_RE_TOMORROW = re.compile(
    r"(?:para\s+amanh[aã]|for\s+tomorrow|para\s+ma[nñ]ana)",
    re.I,
)

# Next N weeks: PT "próximas 2 semanas", EN "next 3 weeks", ES "próximas 2 semanas"
_RE_NEXT_N_WEEKS = re.compile(
    r"(?:"
    r"(?:pr[oó]xim[ao]s?|las?\s+pr[oó]xim[ao]s?)\s+(\d{1,2})\s+semanas?"  # PT/ES: próximas 2 semanas
    r"|(\d{1,2})\s+semanas?\s+(?:que\s+vem|siguientes?)"  # PT: 2 semanas que vem, ES: 2 semanas siguientes
    r"|next\s+(\d{1,2})\s+weeks?"  # EN: next 2 weeks
    r"|(?:for\s+)?(\d{1,2})\s+weeks?"  # EN: for 2 weeks, 2 weeks
    r")",
    re.I,
)

# Next N days: PT "próximos 7 dias", EN "next 10 days", ES "próximos 7 días"
_RE_NEXT_N_DAYS = re.compile(
    r"(?:"
    r"(?:pr[oó]xim[ao]s?|l[ao]s?\s+pr[oó]xim[ao]s?)\s+(\d{1,3})\s+d[ií]as?"  # PT/ES: próximos 7 dias/días
    r"|(\d{1,3})\s+d[ií]as?\s+(?:que\s+vem|siguientes?)"  # PT: 7 dias que vem, ES: 7 días siguientes
    r"|next\s+(\d{1,3})\s+days?"  # EN: next 7 days
    r"|(?:for\s+)?(\d{1,3})\s+days?"  # EN: for 7 days, 7 days
    r")",
    re.I,
)

# Specific date: "17/03", "17-03", "17/03/2026", "dia 17/03", "el día 17/03", "on 17/03"
_RE_SPECIFIC_DATE = re.compile(
    r"(?:"
    r"(?:para\s+)?(?:o\s+|el\s+)?d[ií]a\s+"  # PT/ES: dia/día
    r"|(?:para\s+|for\s+|on\s+)?"  # EN: for/on
    r")?"
    r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?",
    re.I,
)

# Day only: PT "dia 17", EN "on the 17th", ES "el día 17"
# Requires a prefix keyword to avoid matching random numbers
_RE_DAY_ONLY = re.compile(
    r"(?:"
    r"(?:para\s+)?(?:o\s+|el\s+)?d[ií]a\s+"  # PT/ES: dia 17, el día 17
    r"|on\s+(?:the\s+)?"  # EN: on the 17th
    r"|for\s+(?:the\s+)?day\s+"  # EN: for the day 17
    r")"
    r"(\d{1,2})(?:st|nd|rd|th|º|°)?"  # Day number with optional ordinal
    r"(?:\s+(?:de\s+)?(?:est[ea]\s+)?m[eê]s)?",  # Optional "deste mês"
    re.I,
)


def _last_day_of_month(year: int, month: int) -> date:
    """Último dia do mês."""
    if month == 12:
        return date(year + 1, 1, 1) - timedelta(days=1)
    return date(year, month + 1, 1) - timedelta(days=1)


def parse_period(text: str, today: date | None = None) -> Optional[Tuple[date, date]]:
    """Parse temporal qualifier from text and return (start_date, end_date) inclusive, or None.

    Args:
        text: User message (full or partial).
        today: Reference date (default: date.today()).

    Returns:
        (start, end) inclusive date range, or None if no period detected.
    """
    if not text:
        return None
    t = text.strip().lower()
    if today is None:
        today = date.today()

    # Order: most specific first to avoid partial matches

    # Next N weeks: "próximas 2 semanas", "next 2 weeks" (check BEFORE day only)
    m = _RE_NEXT_N_WEEKS.search(t)
    if m:
        # Multiple capture groups - find the one that matched
        weeks = None
        for g in m.groups():
            if g:
                weeks = int(g)
                break
        if weeks and 1 <= weeks <= 52:
            end = today + timedelta(days=weeks * 7)
            return (today, end)

    # Next N days: "próximos 7 dias", "next 7 days" (check BEFORE day only)
    m = _RE_NEXT_N_DAYS.search(t)
    if m:
        # Multiple capture groups - find the one that matched
        days = None
        for g in m.groups():
            if g:
                days = int(g)
                break
        if days and 1 <= days <= 365:
            end = today + timedelta(days=days)
            return (today, end)

    # Specific date: "17/03", "17/03/2026"
    m = _RE_SPECIFIC_DATE.search(t)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year_str = m.group(3)
        if year_str:
            year = int(year_str)
            if year < 100:
                year += 2000
        else:
            year = today.year
            # Se a data já passou este ano, assume próximo ano
            try:
                target = date(year, month, day)
                if target < today:
                    year += 1
            except ValueError:
                pass
        try:
            target = date(year, month, day)
            return (target, target)
        except ValueError:
            pass  # Data inválida, continua

    # Day only: "dia 17" (requires prefix keyword)
    m = _RE_DAY_ONLY.search(t)
    if m:
        day = int(m.group(1))
        if 1 <= day <= 31:
            # Assume mês atual ou próximo
            try:
                target = date(today.year, today.month, day)
                if target < today:
                    # Próximo mês
                    if today.month == 12:
                        target = date(today.year + 1, 1, day)
                    else:
                        target = date(today.year, today.month + 1, day)
                return (target, target)
            except ValueError:
                pass  # Dia inválido para este mês

    # Today
    if _RE_TODAY.search(t):
        return (today, today)

    # Tomorrow
    if _RE_TOMORROW.search(t):
        tmrw = today + timedelta(days=1)
        return (tmrw, tmrw)

    # Next week (before this week — "next" is more specific)
    if _RE_NEXT_WEEK.search(t):
        # Next Monday → Sunday
        days_until_next_monday = (7 - today.weekday()) % 7 or 7
        start = today + timedelta(days=days_until_next_monday)
        end = start + timedelta(days=6)
        return (start, end)

    # This week
    if _RE_THIS_WEEK.search(t):
        start = today - timedelta(days=today.weekday())  # Monday
        end = start + timedelta(days=6)  # Sunday
        return (start, end)

    # This year
    if _RE_THIS_YEAR.search(t):
        return (date(today.year, 1, 1), date(today.year, 12, 31))

    # Next month (before this month)
    if _RE_NEXT_MONTH.search(t):
        if today.month == 12:
            start = date(today.year + 1, 1, 1)
        else:
            start = date(today.year, today.month + 1, 1)
        end = _last_day_of_month(start.year, start.month)
        return (start, end)

    # This month
    if _RE_THIS_MONTH.search(t):
        start = date(today.year, today.month, 1)
        end = _last_day_of_month(today.year, today.month)
        return (start, end)

    # Named month (optionally with year): "em março", "in march 2027"
    m = _RE_MONTH.search(t)
    if m:
        month_name = m.group(1).lower()
        month_num = _MONTH_NAMES.get(month_name)
        if month_num:
            year = int(m.group(2)) if m.group(2) else today.year
            # If the month is strictly in the past this year and no year specified, assume next year.
            # Current month is NOT considered past (user can still be asking about "this March").
            if not m.group(2) and month_num < today.month:
                year = today.year + 1
            start = date(year, month_num, 1)
            end = _last_day_of_month(year, month_num)
            return (start, end)

    # Year: "para 2027"
    m = _RE_YEAR.search(t)
    if m:
        year = int(m.group(1))
        if 2000 <= year <= 2100:  # Sanity check
            return (date(year, 1, 1), date(year, 12, 31))

    return None


def period_label(start: date, end: date, lang: str = "pt-BR") -> str:
    """Generate a human-readable label for a period.

    Args:
        start: Start date.
        end: End date.
        lang: Language code (pt-BR, pt-PT, es, en).

    Returns:
        Label string, e.g., "2027", "esta semana (10/03 – 16/03)", "março 2027".
    """
    # Full year
    if start.month == 1 and start.day == 1 and end.month == 12 and end.day == 31 and start.year == end.year:
        return str(start.year)

    # Single day
    if start == end:
        fmt = "%d/%m/%Y" if lang != "en" else "%Y-%m-%d"
        return start.strftime(fmt)

    # Full month
    if start.day == 1 and end == _last_day_of_month(start.year, start.month) and start.month == end.month:
        _MONTH_LABELS = {
            "pt-BR": ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                       "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
            "pt-PT": ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                       "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
            "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                   "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
            "en": ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"],
        }
        names = _MONTH_LABELS.get(lang, _MONTH_LABELS["en"])
        return f"{names[start.month - 1]} {start.year}"

    # Date range (e.g., week)
    fmt = "%d/%m" if lang != "en" else "%m/%d"
    return f"{start.strftime(fmt)} – {end.strftime(fmt)}"
