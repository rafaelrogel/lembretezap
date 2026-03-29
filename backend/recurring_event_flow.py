"""
Fluxo para eventos recorrentes agendados: academia, aulas, cursos, faculdade, artes marciais.

Ex.: "academia segunda e quarta 19h" → detecta, confirma, pergunta até quando, registra.
"""

import re
from typing import Any

from backend.recurring_patterns import is_in_recurring_list, _normalize
from backend.time_parse import DIAS_SEMANA, _AM_PM_MODIFIERS, adjust_am_pm_hour

# Eventos tipicamente recorrentes com horário fixo semanal (academia, aulas, etc.)
SCHEDULED_RECURRING_HINTS = frozenset({
    "academia", "gym", "ginásio", "ginasio",
    "artes marciais", "martial arts", "karatê", "karate", "judô", "judo",
    "jujitsu", "jiu-jitsu", "taekwondo", "boxe", "muay thai",
    "aula", "aulas", "class", "classes", "clase", "clases",
    "faculdade", "universidade", "university", "college",
    "curso", "cursos", "course", "courses",
    "simposio", "simpósio", "symposium", "workshop", "seminário", "seminario",
    "treino", "trainning", "entrenamiento",
    "inglês", "ingles", "english", "idioma", "language",
    "natação", "natacao", "swimming", "yoga", "pilates",
})

FLOW_KEY = "pending_recurring_event_flow"
STAGE_NEED_CONFIRM = "need_confirm"
STAGE_NEED_END_DATE = "need_end_date"
MAX_RETRIES_END_DATE = 3

# Padrão: evento + (segunda e quarta | segunda, quarta | segunda a sexta) + hora
_DAY_NAMES = "|".join(sorted(DIAS_SEMANA.keys(), key=len, reverse=True))
_RE_MULTI_DAY = re.compile(
    rf"((?:{_DAY_NAMES})(?:\s*(?:e|y|and|,)\s*(?:{_DAY_NAMES}))*)\s+"
    r"(?:às?|at|a\s+las?|as?|(?=\d))\s*(\d{1,2})(?::(\d{2}))?\s*" + _AM_PM_MODIFIERS + r"?\s*h?\b",
    re.I,
)
_RE_SINGLE_DAY = re.compile(
    rf"({_DAY_NAMES})\s+(?:às?|at|a\s+las?|as?|(?=\d))\s*(\d{{1,2}})(?::(\d{{2}}))?\s*" + _AM_PM_MODIFIERS + r"?\s*h?\b",
    re.I,
)
_RE_WEEKDAYS = re.compile(
    r"(?:segunda\s+a\s+sexta|lunes\s+a\s+viernes|monday\s+to\s+friday)\s+(?:às?|at|a\s+las?|as?|(?=\d))\s*(\d{1,2})(?::(\d{2}))?\s*" + _AM_PM_MODIFIERS + r"?\s*h?\b",
    re.I,
)
# Recorrência explícita: "toda segunda às 17h", "every day at 8h", "cada lunes a las 8h"
_RE_TODA_SINGLE = re.compile(
    rf"(?:toda?|every|cada)\s+({_DAY_NAMES})\s+(?:às?|at|a\s+las?|as?|(?=\d))\s*(\d{{1,2}})(?::(\d{{2}}))?\s*" + _AM_PM_MODIFIERS + r"?\s*h?\b",
    re.I,
)
_RE_TODA_MULTI = re.compile(
    rf"(?:toda?|every|cada)\s+((?:{_DAY_NAMES})(?:\s*(?:e|y|and|,)\s*(?:{_DAY_NAMES}))*)\s+(?:às?|at|a\s+las?|as?|(?=\d))\s*(\d{{1,2}})(?::(\d{{2}}))?\s*" + _AM_PM_MODIFIERS + r"?\s*h?\b",
    re.I,
)
# Language-specific fragments
# Language-specific fragments
_PAT_EVERY_DAY = r"(?:todo\s+dia|todos\s+os\s+dias|todos\s+los\s+d[íi]as|cada\s+d[íi]a|every\s+day)"
_PAT_AT = r"(?:[àáa]s?|at|@|a\s+las?|a\s+los?)"
_PAT_DAILY = r"(?:diariamente|daily)"

# Daily patterns (Specific hours)
_RE_TODO_DIA_SPECIFIC = re.compile(
    rf"{_PAT_EVERY_DAY}\s+(?:{_PAT_AT}\s+(\d{{1,2}})(?:[:h](\d{{2}}))?\s*" + _AM_PM_MODIFIERS + r"?|(\d{{1,2}}):(\d{{2}})\s*" + _AM_PM_MODIFIERS + r"?|(\d{{1,2}})\s*" + _AM_PM_MODIFIERS + r"?\s*h)\b",
    re.I,
)

# Monthly patterns
# "todo dia 21 às 10h", "every day 21 at 10am"
_RE_TODO_DIA_N_AT = re.compile(
    rf"{_PAT_EVERY_DAY}\s+(\d{{1,2}})(?:\s+{_PAT_AT}\s*|\s+)(\d{{1,2}})(?:[:h](\d{{2}}))?\s*" + _AM_PM_MODIFIERS + r"?\s*h?\b",
    re.I,
)
# "todo dia 21", "every day 21" (Bare number)
_RE_TODO_DIA_N = re.compile(
    rf"{_PAT_EVERY_DAY}\s+(\d{{1,2}})\b",
    re.I,
)

_RE_DIARIAMENTE_SPECIFIC = re.compile(
    rf"{_PAT_DAILY}\s+(?:{_PAT_AT}\s+(\d{{1,2}})(?:[:h](\d{{2}}))?\s*" + _AM_PM_MODIFIERS + r"?|(\d{{1,2}}):(\d{{2}})\s*" + _AM_PM_MODIFIERS + r"?|(\d{{1,2}})\s*" + _AM_PM_MODIFIERS + r"?\s*h)\b",
    re.I,
)

# Indicadores de recorrência (para não tratar como evento único)
RECURRENCE_INDICATORS = re.compile(
    r"\b((?:toda?s?|every|cada|todos?)\s+(?:as?|os?|the|las?|los?)?\s*(?:segunda|lunes|monday|terça|martes|tuesday|terca|quarta|miércoles|miercoles|wednesday|quinta|jueves|thursday|sexta|viernes|friday|sábado|sabado|saturday|domingo|sunday|semana)|"
    r"todo\s+dia|todos\s+os\s+dias|diariamente|semanalmente|mensalmente|toda\s+semana|"
    r"every\s+day|daily|weekly|monthly|every\s+week|"
    r"todos\s+los\s+d[íi]as|cada\s+d[íi]a|mensualmente|cada\s+semana|"
    r"a\s+cada|cada|at\s+every)\b",
    re.I,
)


def has_recurrence_indicator(text: str) -> bool:
    """True se o texto indica recorrência (toda segunda, todo dia, diariamente, etc.)."""
    if not text or len(text.strip()) < 5:
        return False
    return bool(RECURRENCE_INDICATORS.search(text.strip()))


def is_scheduled_recurring_event(text: str) -> bool:
    """True se o texto parece evento/agenda ou lembrete recorrente com horário (parseável)."""
    if not text or len(text.strip()) < 8:
        return False
        
    # Excluir explicitamente se parece agenda pontual (evitar conflito)
    from backend.views.unificado import _is_eventos_unificado_intent
    if _is_eventos_unificado_intent(text):
        return False

    # 1. Indicadores explícitos (toda segunda, todo dia, etc.) -> Confiança Alta
    if has_recurrence_indicator(text) and parse_recurring_schedule(text) is not None:
        return True # EXPLANATION: Explicit recurring keyword + valid schedule.
    
    # 2. Hints de alta confiança (academia, aula) + schedule válido
    t = _normalize(text)
    has_hint = any(h in t for h in {_normalize(x) for x in SCHEDULED_RECURRING_HINTS})
    if has_hint and parse_recurring_schedule(text) is not None:
        return True # EXPLANATION: Domain hint (gym/class) + valid daily/weekly schedule.

    return False


def _clean_content(c: str) -> str:
    """Remove preposições e conectores residuais do final do conteúdo extraído."""
    c = c.strip()
    # Remove "no", "na", "de", "do", "em", "on", "in", "at", "el", "la" etc no final
    c = re.sub(r"\s+(?:no|na|nos|nas|o|a|os|as|de|do|da|dos|das|em|este|nesta|neste|para|às?|at|on|in|cada|toda?|every|el|la|los|las)$", "", c, flags=re.I)
    return c.strip()


def parse_recurring_schedule(text: str) -> tuple[str, str, int, int] | None:
    """
    Extrai evento + cron de «academia segunda e quarta 19h», «preciso ir ao médico toda segunda às 17h», «todo dia às 8h», etc.
    Retorna (event_content, cron_expr, hour, minute) ou None.
    """
    if not text or len(text.strip()) < 8:
        return None
    t = text.strip()
    tl = t.lower()

    # 1. "todo dia às 8h" or "todo dia 8h" or "todo dia 8:30" (Specific Daily Hour)
    m = _RE_TODO_DIA_SPECIFIC.search(tl)
    if m:
        g1, g2, g3, g4, g5, g6, g7, g8 = m.groups()
        if g1:
            hora, minuto, period = int(g1), int(g2 or 0), g3
        elif g4:
            hora, minuto, period = int(g4), int(g5 or 0), g6
        else:
            hora, minuto, period = int(g7), 0, g8
            
        hora = adjust_am_pm_hour(hora, period)
        hora, minuto = min(23, hora), min(59, minuto)
        
        content = _RE_TODO_DIA_SPECIFIC.sub("", t).strip()
        content = re.sub(r"^[:\-–—\s]+", "", content).strip()
        return content, f"{minuto} {hora} * * *", hora, minuto

    # 2. "todo dia 21 às 10h" (Monthly Day + Hour)
    m = _RE_TODO_DIA_N_AT.search(tl)
    if m:
        dia = int(m.group(1))
        if 1 <= dia <= 31:
            hora = int(m.group(2))
            minuto = int(m.group(3) or 0) if m.lastindex >= 3 and m.group(3) else 0
            period = m.group(4) if m.lastindex >= 4 else None
            hora = adjust_am_pm_hour(hora, period)
            hora = min(23, hora)
            content = _RE_TODO_DIA_N_AT.sub("", t).strip()
            content = re.sub(r"^[:\-–—\s]+", "", content).strip()
            return _clean_content(content), f"{minuto} {hora} {dia} * *", hora, minuto

    # 3. "todo dia 21" (Monthly Day, defaults to 9 AM)
    m = _RE_TODO_DIA_N.search(tl)
    if m:
        dia = int(m.group(1))
        if 1 <= dia <= 31:
            content = _RE_TODO_DIA_N.sub("", t).strip()
            content = re.sub(r"^[:\-–—\s]+", "", content).strip()
            return _clean_content(content), f"0 9 {dia} * *", 9, 0

    # 4. "diariamente às 8h"
    m = _RE_DIARIAMENTE_SPECIFIC.search(tl)
    if m:
        g1, g2, g3, g4, g5, g6, g7, g8 = m.groups()
        if g1:
            hora, minuto, period = int(g1), int(g2 or 0), g3
        elif g4:
            hora, minuto, period = int(g4), int(g5 or 0), g6
        else:
            hora, minuto, period = int(g7), 0, g8
            
        hora = adjust_am_pm_hour(hora, period)
        hora, minuto = min(23, hora), min(59, minuto)
        content = _RE_DIARIAMENTE_SPECIFIC.sub("", t).strip()
        content = re.sub(r"^[:\-–—\s]+", "", content).strip()
        return content, f"{minuto} {hora} * * *", hora, minuto

    # "toda segunda às 17h", "preciso ir ao médico toda segunda 17h"
    m = _RE_TODA_SINGLE.search(tl)
    if m:
        dia_raw = (m.group(1) or "").strip().lower()
        hora = int(m.group(2))
        minuto = int(m.group(3) or 0) if m.lastindex >= 3 and m.group(3) else 0
        period = m.group(4) if m.lastindex >= 4 else None
        hora = adjust_am_pm_hour(hora, period)
        hora = min(23, hora)
        dow = DIAS_SEMANA.get(dia_raw)
        if dow is not None:
            cron = f"{minuto} {hora} * * {dow}"
            content = _RE_TODA_SINGLE.sub("", t).strip()
            content = re.sub(r"\s+", " ", content).strip()
            return content, cron, hora, minuto

    # "toda segunda e quarta 19h"
    m = _RE_TODA_MULTI.search(tl)
    if m:
        days_str = m.group(1)
        hora = int(m.group(2))
        minuto = int(m.group(3) or 0) if m.lastindex >= 3 and m.group(3) else 0
        period = m.group(4) if m.lastindex >= 4 else None
        hora = adjust_am_pm_hour(hora, period)
        hora = min(23, hora)
        dow_nums = _parse_day_list(days_str)
        if dow_nums:
            dow_cron = ",".join(str(d) for d in sorted(dow_nums))
            cron = f"{minuto} {hora} * * {dow_cron}"
            content = _RE_TODA_MULTI.sub("", t).strip()
            content = re.sub(r"\s+", " ", content).strip()
            return content, cron, hora, minuto

    # "segunda a sexta 8h" → cron 0 8 * * 1-5
    m = _RE_WEEKDAYS.search(tl)
    if m:
        hora = int(m.group(1))
        minuto = int(m.group(2) or 0) if m.group(2) else 0
        period = m.group(3)
        hora = adjust_am_pm_hour(hora, period)
        hora = min(23, hora)
        content = _RE_WEEKDAYS.sub("", t).strip()
        content = re.sub(r"\s+", " ", content).strip()
        cron = f"{minuto} {hora} * * 1-5"
        return content, cron, hora, minuto

    # "segunda e quarta 19h", "terça, quinta 10h"
    m = _RE_MULTI_DAY.search(tl)
    if m:
        days_str = m.group(1)
        hora = int(m.group(2))
        minuto = int(m.group(3) or 0) if m.group(3) else 0
        period = m.group(4)
        hora = adjust_am_pm_hour(hora, period)
        hora = min(23, hora)
        dow_nums = _parse_day_list(days_str)
        if dow_nums:
            dow_cron = ",".join(str(d) for d in sorted(dow_nums))
            cron = f"{minuto} {hora} * * {dow_cron}"
            content = _RE_MULTI_DAY.sub("", t).strip()
            content = re.sub(r"\s+", " ", content).strip()
            return content, cron, hora, minuto

    # "terça 10h", "segunda 19h"
    m = _RE_SINGLE_DAY.search(tl)
    if m:
        dia_raw = (m.group(1) or "").strip().lower()
        hora = int(m.group(2))
        minuto = int(m.group(3) or 0) if m.group(3) else 0
        period = m.group(4)
        hora = adjust_am_pm_hour(hora, period)
        hora = min(23, max(0, hora))
        dow = DIAS_SEMANA.get(dia_raw)
        if dow is not None:
            cron = f"{minuto} {hora} * * {dow}"
            content = _RE_SINGLE_DAY.sub("", t).strip()
            content = re.sub(r"\s+", " ", content).strip()
            return content, cron, hora, minuto

    # 5. "a cada 2 horas", "cada 30 min", "every 2 hours", "cada dia"
    # Precision fix: Define specific units and use \b to avoid matching "segunda" as "seg"
    units_regex = r"(segundos?|seg\b|seconds?|secs?\b|minutos?|min\b|minutes?|horas?|hrs?\b|hours?|dias?|days?|semanas?|weeks?)"
    cadence_pat = rf"(?:a\s+)?(?:cada|every|cada\s+vez\s+que)\s*(?:(\d+)\s*)?{units_regex}\b"
    m_cadence = re.search(cadence_pat, tl, re.I)
    if m_cadence:
        num = int(m_cadence.group(1)) if m_cadence.group(1) else 1
        unit = m_cadence.group(2).lower()
        if unit.startswith(("min", "minutes")):
            mul = 60
        elif unit.startswith(("hor", "hour", "hr")):
            mul = 3600
        elif unit.startswith(("dia", "day")):
            mul = 86400
        elif unit.startswith(("seman", "week")):
            mul = 86400 * 7
        elif unit.startswith(("seg", "sec")):
            mul = 1
        else:
            mul = 1
        
        every_seconds = num * mul
        content = re.sub(cadence_pat, "", t, flags=re.I).strip()
        content = re.sub(r"^[:\-–—\s]+|[:\-–—\s]+$", "", content).strip()
        return _clean_content(content), f"every:{every_seconds}", 0, 0

    return None


def _parse_day_list(days_str: str) -> list[int]:
    """
    Transforma string de dias («segunda e quarta», «lunes y miércoles», «mon and wed») em lista de DOW.
    Separa por «e», «y», «and» ou vírgulas, respeitando limites de palavra.
    """
    if not days_str:
        return []
    # Usar word boundaries (\b) para não partir palavras como "sEgunda"
    # Separadores: " e ", " y ", " and ", ou vírgula
    parts = re.split(r"\s*(?:\be\b|\by\b|\band\b|,)\s*", days_str.strip(), flags=re.I)
    result = []
    for p in parts:
        # Normalizar: minúsculas, sem espaços e sem o sufixo "-feira" para match universal
        p_clean = p.strip().lower().replace("-feira", "")
        if not p_clean:
            continue
        # Tenta match direto no dicionário global de dias (que inclui PT, EN, ES)
        dow = DIAS_SEMANA.get(p_clean)
        if dow is not None:
            result.append(dow)
    return sorted(set(result))


def format_schedule_for_display(cron_expr: str, lang: str = "pt-BR") -> str:
    """'0 19 * * 1,3' → 'segunda e quarta às 19h'; '0 8 * * *' → 'todo dia às 8h'."""
    parts = (cron_expr or "").strip().split()
    if len(parts) < 5:
        return cron_expr
    try:
        hora = int(parts[1])
        day_of_month = parts[2]
        dow_str = parts[4]
        
        # Monthly: 0 9 21 * *
        if dow_str == "*" and day_of_month != "*":
            if lang == "es":
                return f"todos los días {day_of_month} a las {hora}h"
            if lang == "en":
                return f"every day {day_of_month} at {hora}h"
            return f"todo dia {day_of_month} às {hora}h"

        if dow_str == "*":
            if lang == "es":
                return f"todos los días a las {hora}h"
            if lang == "en":
                return f"every day at {hora}h"
            return f"todo dia às {hora}h"
        
        if "-" in dow_str:
            # 1-5 = segunda a sexta
            if lang == "es":
                return f"de lunes a viernes a las {hora}h"
            if lang == "en":
                return f"monday to friday at {hora}h"
            return f"segunda a sexta às {hora}h"
        
        dows = [int(x) for x in dow_str.split(",")]
        names_pt = {1: "segunda", 2: "terça", 3: "quarta", 4: "quinta", 5: "sexta", 6: "sábado", 0: "domingo"}
        names_es = {1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábado", 0: "domingo"}
        names_en = {1: "monday", 2: "tuesday", 3: "wednesday", 4: "thursday", 5: "friday", 6: "saturday", 0: "sunday"}
        
        names = names_pt
        if lang == "es": names = names_es
        elif lang == "en": names = names_en
        
        labels = [names.get(d, "") for d in dows if d in names]
        if not labels:
            return cron_expr

        at_str = "às"
        and_str = "e"
        if lang == "es":
            at_str = "a las"
            and_str = "y"
        elif lang == "en":
            at_str = "at"
            and_str = "and"

        if len(labels) == 1:
            return f"{labels[0]} {at_str} {hora}h"
        if len(labels) == 2:
            return f"{labels[0]} {and_str} {labels[1]} {at_str} {hora}h"
        return ", ".join(labels[:-1]) + f" {and_str} {labels[-1]} {at_str} {hora}h"
    except (ValueError, IndexError):
        return cron_expr


def parse_end_date_response(text: str) -> str | None:
    """
    Interpreta resposta sobre «até quando» no fluxo de eventos recorrentes.
    Suporta PT-PT, PT-BR, ES, EN.
    Retorna: "indefinido" | "fim_semana" | "fim_mes" | "fim_ano" | "date:YYYY-MM-DD" | "year:YYYY" | None
    """
    if not text or not text.strip():
        return None
    t = text.strip().lower()

    # 1. Indefinido (sem data fim) - Keywords mais precisas
    indefinite_keywords = (
        "indefinido", "para sempre", "sempre", "não tem fim", "sem fim", "até eu remover", "até eu apagar",
        "forever", "no end", "limitless", "always", "until i delete", "until i stop",
        "para siempre", "sin fin", "sin fecha", "hasta que lo borre", "hasta que pare"
    )
    if any(p in t for p in indefinite_keywords):
        return "indefinido"
    
    # 2. Fim de semana
    week_keywords = (
        "fim da semana", "fim semana", "fim de semana", "final da semana", "até sexta", "até domingo",
        "end of week", "end of the week", "until sunday", "this week", "esta semana",
        "fin de semana", "hasta el domingo"
    )
    if any(p in t for p in week_keywords):
        return "fim_semana"

    # 3. Fim do mês
    month_keywords = (
        "fim do mês", "fim mes", "fim de mes", "fim do mes", "final do mês", "final do mes",
        "end of month", "end of the month", "until end of month", "this month", "este mês", "este mes",
        "fin de mes", "hasta fin de mes"
    )
    if any(p in t for p in month_keywords):
        return "fim_mes"

    # 4. Fim do ano
    year_keywords = (
        "fim do ano", "fim ano", "fim de ano", "final do ano", "este ano",
        "end of the year", "end of year", "until the end of the year", "this year",
        "fin de año", "fin de ano", "este año"
    )
    if any(p in t for p in year_keywords):
        return "fim_ano"

    # 5. Datas específicas: "até 31/12", "until 12/31/2026", "hasta el 15 de marzo"
    from backend.time_parse import extract_start_date
    clean_t = re.sub(r"\b(até|until|hasta|el|the|o|a)\s+", "", t, flags=re.I).strip()
    parsed_date = extract_start_date(clean_t)
    if parsed_date:
        return f"date:{parsed_date}"

    # 6. Anos específicos: "até o fim de 2028", "until end of 2030", "fim de 2028"
    m_year = re.search(r"(?:fim\s+de|end\s+of|fin\s+de|final\s+de)\s*(?:ano\s+)?(20\d{2})\b", t)
    if not m_year:
        m_year = re.search(r"\b(20\d{2})\b", t)
    if m_year:
        return f"year:{m_year.group(1)}"

    return None


def looks_like_confirm_yes(text: str) -> bool:
    """Resposta afirmativa para confirmação."""
    t = (text or "").strip().lower()
    if not t or len(t) > 30:
        return False
    return any(
        p in t for p in ("sim", "s", "quero", "yes", "pode", "regista", "registre", "faz", "claro", "ok")
    )


def looks_like_confirm_no(text: str) -> bool:
    """Resposta negativa."""
    t = (text or "").strip().lower()
    if not t or len(t) > 30:
        return False
    return any(p in t for p in ("não", "nao", "no", "n", "dispenso", "cancelar"))


def compute_end_date_ms(end_type: str, tz_iana: str = "UTC") -> int | None:
    """Calcula not_after_ms para fim_semana, fim_mes, fim_ano."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        from zapista.clock_drift import get_effective_time
        _now_ts = get_effective_time()
    except Exception:
        _now_ts = __import__("time").time()

    try:
        z = ZoneInfo(tz_iana)
        from datetime import timezone
        now = datetime.fromtimestamp(_now_ts, tz=timezone.utc).astimezone(z)

        if end_type == "fim_semana":
            # Próximo domingo 23:59
            # Se for hoje (domigo), desloca para o próximo domingo (+7 dias)
            days_until_sun = (6 - now.weekday()) % 7
            if days_until_sun == 0:
                days_until_sun = 7
            from datetime import timedelta
            end = now.replace(hour=23, minute=59, second=59, microsecond=0)
            end = end + timedelta(days=days_until_sun)
            return int(end.timestamp() * 1000)
        if end_type == "fim_mes":
            from calendar import monthrange
            _, last = monthrange(now.year, now.month)
            end = now.replace(day=last, hour=23, minute=59, second=59, microsecond=0)
            return int(end.timestamp() * 1000)
        if end_type == "fim_ano":
            end = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=0)
            return int(end.timestamp() * 1000)
        
        if end_type.startswith("year:"):
            target_year = int(end_type.split(":")[1])
            end = now.replace(year=target_year, month=12, day=31, hour=23, minute=59, second=59, microsecond=0)
            return int(end.timestamp() * 1000)

        if end_type.startswith("date:"):
            date_str = end_type.split(":")[1] # YYYY-MM-DD
            from datetime import date
            dt = date.fromisoformat(date_str)
            end = datetime(dt.year, dt.month, dt.day, 23, 59, 59, tzinfo=z)
            return int(end.timestamp() * 1000)
    except Exception:
        pass
    return None
