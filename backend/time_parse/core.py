"""Core orchestration for time parsing, dynamically building patterns from language submodules."""

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo
from calendar import monthrange

from . import pt, en, es

# Combine constants from all languages
DIAS_SEMANA = {**pt.DIAS_SEMANA, **en.DIAS_SEMANA, **es.DIAS_SEMANA}
MESES = {**pt.MESES, **en.MESES, **es.MESES}

# Common separator
_SEP = r"(?:\s*(?:de|/|-)\s*|\s+)"

# Build dynamic MONTH_NAMES pattern
_MONTH_NAMES_STR = "|".join(set(pt.MONTH_NAMES + en.MONTH_NAMES + es.MONTH_NAMES))

# Localized "in/at/after" patterns
RE_LEMBRETE_DAQUI = re.compile(pt.RE_DAQUI, re.I)
RE_LEMBRETE_EM = re.compile(pt.RE_EM, re.I)
RE_LEMBRETE_IN = re.compile(en.RE_IN, re.I)
RE_LEMBRETE_ES_EN = re.compile(es.RE_EN, re.I)

# Combine AM_PM_MODIFIERS
_ALL_AM_PM = pt.AM_PM_MODIFIERS + en.AM_PM_MODIFIERS + es.AM_PM_MODIFIERS
_AM_PM_MODIFIERS = "(" + "|".join(_ALL_AM_PM) + ")"

def adjust_am_pm_hour(hora: int, period: str | None) -> int:
    if not period:
        return hora
    p = period.lower()
    if any(w in p for w in ("manh", "mañ", "morn", "am", "a.m")):
        if hora == 12: return 0
        if hora > 12: return hora - 12
    if any(w in p for w in ("tarde", "noite", "noch", "after", "even", "night", "pm", "p.m")):
        if 1 <= hora < 12: return hora + 12
    return hora

def strip_pattern(text: str, pattern: str | re.Pattern[str]) -> str:
    """Remove o padrão do texto e retorna limpo."""
    if isinstance(pattern, str):
        return re.sub(pattern, "", text, flags=re.I).strip()
    return pattern.sub("", text).strip()

def clean_message(t: str) -> str:
    """Remove conectores e barras do início."""
    t = t.strip()
    while t.startswith("/"):
        t = t.lstrip("/").strip()
    for prefix in (
        "de ", "para ", "a ", "sobre ", 
        "lembre-me que ", "lembrar que ", "lembra-me que ",
        "lembre me que ", "lembra me que ",
        "lembrar de ", "lembra de ", "lembre de "
    ):
        if t.lower().startswith(prefix) and len(t) > len(prefix):
            t = t[len(prefix):].strip()
    t = re.sub(r"\s+at[eé]\s*$", "", t, flags=re.I)
    return t or "Lembrete"

def extract_start_date(text: str, tz_iana: str = "UTC") -> str | None:
    """Extrai «a partir de 1º de julho» → '2026-07-01'."""
    text_lower = (text or "").strip().lower()
    try:
        from zapista.clock_drift import get_effective_time
        _now_ts = get_effective_time()
    except Exception:
        import time
        _now_ts = time.time()

    try:
        z = ZoneInfo(tz_iana)
        current_year = datetime.fromtimestamp(_now_ts, tz=z).year
    except Exception:
        current_year = datetime.fromtimestamp(_now_ts).year

    m = re.search(
        r"(?:a\s+partir\s+de\s+)?(\d{1,2})[ºª]?" + _SEP +
        r"(\d{1,2}|" + _MONTH_NAMES_STR + r")"
        r"(?:" + _SEP + r"(\d{4}))?\b",
        text_lower,
        re.I,
    )
    if m:
        dia = int(m.group(1))
        mes_str = m.group(2).lower()
        mes = int(mes_str) if mes_str.isdigit() else MESES.get(mes_str)
        ano = int(m.group(3)) if m.group(3) else current_year
        if mes and 1 <= dia <= 31 and 1 <= mes <= 12:
            try:
                dt = datetime(ano, mes, dia)
                return dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
    return None

def parse_lembrete_time(text: str, tz_iana: str = "UTC") -> dict[str, Any]:
    """Extrai tempo/recorrência. Ordem rigorosa igual ao original time_parse.py."""
    text = text.strip()
    text_lower = text.lower()
    try:
        from zapista.clock_drift import get_effective_time
        _now_ts = get_effective_time()
    except Exception:
        import time
        _now_ts = time.time()

    try:
        z = ZoneInfo(tz_iana)
        now = datetime.fromtimestamp(_now_ts, tz=z)
    except Exception:
        now = datetime.fromtimestamp(_now_ts)

    # Timezone override
    m_tz = re.search(r"(?:no\s+fuso\s+d[eoa]|em)\s+([^,.\s?]+(?:\s+[^,.\s?]+)?)", text_lower)
    if m_tz:
        try:
            from backend.timezone import city_to_iana
            possible_city = m_tz.group(1).strip()
            found_tz = city_to_iana(possible_city)
            if found_tz:
                tz_iana = found_tz
                z = ZoneInfo(tz_iana)
                now = datetime.fromtimestamp(_now_ts, tz=z)
        except Exception: pass

    # 1. Prazos relativos (daqui a, em, in, en)
    for pattern in (RE_LEMBRETE_DAQUI, RE_LEMBRETE_EM, RE_LEMBRETE_IN, RE_LEMBRETE_ES_EN):
        m = pattern.search(text)
        if m:
            n = int(m.group(1))
            unit = (m.group(2) or "").lower()
            if any(w in unit for w in ("hora", "hour", "hr")): n *= 3600
            elif any(w in unit for w in ("dia", "day", "d[íi]a")): n *= 86400
            else: n *= 60
            if n > 0 and n <= 86400 * 30:
                message = (text[: m.start()] + text[m.end() :]).strip()
                return {"in_seconds": n, "message": clean_message(message)}

    # 2. "a cada N"
    m = re.search(r"(?:a\s+cada|cada|every)\s+(\d+)\s*(minuto?s?|hora?s?|dia?s?|minutes?|hours?|days?)\b", text_lower, re.I)
    if m:
        num = int(m.group(1))
        u = (m.group(2) or "").lower()
        if any(w in u for w in ("hora", "hour")): every = num * 3600
        elif any(w in u for w in ("dia", "day")): every = num * 86400
        else: every = num * 60
        if 1800 <= every <= 86400 * 30:
            message = strip_pattern(text, r"(?:a\s+cada|cada|every)\s+\d+\s*(minuto?s?|hora?s?|dia?s?|minutes?|hours?|days?)\s*")
            return {"every_seconds": every, "message": clean_message(message)}

    # 3. Hoje
    m = re.search(
        r"(?:(?:(?:[àa]s?|at|a\s+las?)\s*)?(\d{1,2})(?:h|:|min)?(\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\s*(?:de\s+)?(?:hoje|hoy|today)\b|"
        r"(?:hoje|hoy|today)\s+(?:(?:[àa]s?|at|a\s+las?)\s*)?(\d{1,2})(?:h|:)?(\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\b)",
        text_lower, re.I
    )
    if m:
        if m.group(1): hora, minute, period = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        else: hora, minute, period = int(m.group(4)), int(m.group(5) or 0), m.group(6)
        hora = min(23, max(0, adjust_am_pm_hour(hora, period)))
        message = strip_pattern(text, m.group(0))
        delta = (now.replace(hour=hora, minute=minute, second=0, microsecond=0) - now).total_seconds()
        return {"in_seconds": int(delta), "message": clean_message(message)}

    # 4. Amanhã
    m = re.search(
        r"(?:amanh[ãa]|ma[ñn]ana|tomorrow)\s+(?:(?:[àa]s?|at|a\s+las?)\s*)?(\d{1,2})(?:h|:)?(\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\b",
        text_lower, re.I
    )
    if m:
        hora, minute = min(23, max(0, int(m.group(1)))), int(m.group(2) or 0)
        hora = adjust_am_pm_hour(hora, m.group(3))
        message = strip_pattern(text, m.group(0))
        delta = ((now + timedelta(days=1)).replace(hour=hora, minute=minute, second=0, microsecond=0) - now).total_seconds()
        if delta > 0 and delta <= 86400 * 30:
            return {"in_seconds": int(delta), "message": clean_message(message)}

    # 5. Todo dia às HH:MM
    m = re.search(
        r"(?P<rec>(?:todo\s+dia|todos\s+os\s+dias|diariamente|every\s+day|daily|todos\s+los\s+d[íi]as|cada\s+d[íi]a))\s+"
        r"(?:às?|as|at|a\s+las?|a\s+los?)\s*(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*" + _AM_PM_MODIFIERS + r"?\s*h?\b",
        text_lower, re.I
    )
    if m:
        hora, minute, period = int(m.group("h")), int(m.group("m") or 0), m.group(4)
        hora = min(23, max(0, adjust_am_pm_hour(hora, period)))
        message = strip_pattern(text, r"(?P<rec>(?:todo\s+dia|todos\s+os\s+dias|diariamente|every\s+day|daily|todos\s+los\s+d[íi]as|cada\s+d[íi]a))\s+(?:às?|as|at|a\s+las?|a\s+los?)\s*\d{1,2}(?::\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\s*h?\s*")
        return {"cron_expr": f"{minute} {hora} * * *", "message": clean_message(message)}

    # 6. Mensalmente às HH:MM (v1)
    m = re.search(r"(?:mensalmente|monthly|mensualmente)\s+(?:dia\s+|day\s+)?(\d{1,2})\s*(?:às?|as|at|a\s+las?)\s*(\d{1,2})\s*h?\b", text_lower, re.I)
    if m:
        dia_mes, hora = int(m.group(1)), min(23, max(0, int(m.group(2))))
        if 1 <= dia_mes <= 28:
            message = strip_pattern(text, r"(?:mensalmente|monthly|mensualmente)\s+(?:dia\s+|day\s+)?\d{1,2}\s*(?:às?|as|at|a\s+las?)\s*\d{1,2}\s*h?\s*")
            return {"cron_expr": f"0 {hora} {dia_mes} * *", "message": clean_message(message)}

    # 7. Todo dia N: ...
    m = re.search(r"(?P<rec>(?:todo\s+dia|every\s+day|todos\s+los\s+d[íi]as|cada\s+d[íi]a))\s+(?P<day>\d{1,2})(?:\s*[:\-]\s*|\s+)(?P<rest>.+)$", text_lower, re.I)
    if m:
        dia_mes, rest = int(m.group("day")), m.group("rest").strip()
        if 1 <= dia_mes <= 31 and not re.match(r"^\d{2}", rest):
            return {"cron_expr": f"0 9 {dia_mes} * *", "message": clean_message(rest)}

    # 8. Todo dia N
    m = re.search(r"(?P<rec>(?:todo\s+dia|every\s+day|todos\s+los\s+d[íi]as|cada\s+d[íi]a))\s+(?P<day>\d{1,2})\b", text_lower, re.I)
    if m:
        dia_mes = int(m.group(1))
        if 1 <= dia_mes <= 31:
            message = re.sub(r"(?:todo\s+dia|every\s+day|todos\s+los\s+d[íi]as|cada\s+d[íi]a)\s+\d{1,2}\s*", "", text, flags=re.I).strip()
            return {"cron_expr": f"0 9 {dia_mes} * *", "message": clean_message(message)}

    # 9. Todo dia ...
    m = re.search(r"(?:todo\s+dia|todos\s+os\s+dias|every\s+day|todos\s+los\s+d[íi]as|cada\s+d[íi]a)\s+(.+)$", text_lower, re.I)
    if m:
        message = m.group(1).strip()
        if not message.isdigit():
            return {"cron_expr": "0 9 * * *", "message": clean_message(message)}

    # 10. A partir de
    if any(p in text_lower for p in ["a partir de", "starting from", "starting on", "a partir del"]):
        m = re.search(r"(?:todo\s+dia|todos\s+os\s+dias|diariamente|every\s+day|daily|todos\s+los\s+d[íi]as|cada\s+d[íi]a)\s+(?:(?:às?|as|at|a\s+las?|a\s+los?)\s+(\d{1,2})(?:[:h](\d{2}))?\s*" + _AM_PM_MODIFIERS + r"?|(\d{1,2}):(\d{2})\s*" + _AM_PM_MODIFIERS + r"?|(\d{1,2})\s*" + _AM_PM_MODIFIERS + r"?\s*h)\b", text_lower, re.I)
        if m:
            g1, g2, g3, g4, g5, g6, g7, g8 = m.groups()
            if g1: hora, minute, period = int(g1), int(g2 or 0), g3
            elif g4: hora, minute, period = int(g4), int(g5 or 0), g6
            else: hora, minute, period = int(g7), 0, g8
            hora = min(23, max(0, adjust_am_pm_hour(hora, period)))
            message = strip_pattern(text, r"(?:todo\s+dia|todos\s+os\s+dias|diariamente|every\s+day|daily|todos\s+los\s+d[íi]as|cada\s+d[íi]a)\s+(?:(?:às?|as|at|a\s+las?|a\s+los?)\s*\d{1,2}(?:[:h]\d{2})?\s*" + _AM_PM_MODIFIERS + r"?|\d{1,2}:\d{2}\s*" + _AM_PM_MODIFIERS + r"?|\d{1,2}\s*" + _AM_PM_MODIFIERS + r"?\s*h)\s*")
            out = {"cron_expr": f"0 {hora} * * *", "message": clean_message(message)}
            sd = extract_start_date(text, tz_iana); 
            if sd: out["start_date"] = sd
            return out
        for dia_name, cron_dow in DIAS_SEMANA.items():
            pat = rf"\b(?:toda|every|cada)\s+(?:semana\s+|week\s+)?{re.escape(dia_name)}(?:\s*-?\s*f[eé]ira)?\b\s+(?:às?|as|at|a\s+las?)\s*(\d{{1,2}})(?::(\d{{2}}))?\s*" + _AM_PM_MODIFIERS + r"?\s*h?\b"
            m = re.search(pat, text_lower, re.I)
            if m:
                hora, minute, period = int(m.group(1)), int(m.group(2) or 0), m.group(3)
                hora = min(23, max(0, adjust_am_pm_hour(hora, period)))
                message = re.sub(pat, "", text, flags=re.I).strip()
                out = {"cron_expr": f"{minute} {hora} * * {cron_dow}", "message": clean_message(message)}
                sd = extract_start_date(text, tz_iana); 
                if sd: out["start_date"] = sd
                return out

    # 11. Data específica com Hora
    _pat_data_hora = (r"(?:dia\s+)?(\d{1,2})[ºª]?" + _SEP + r"(\d{1,2}|" + _MONTH_NAMES_STR + r")" + r"(?:" + _SEP + r"(\d{4}))?\s*(?:às?|as|at|a\s+las?)\s*(\d{1,2})\s*(?:h|:)\s*(\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\s*")
    m = re.search(_pat_data_hora, text_lower, re.I)
    if m:
        dia, mes_str, ano, h_str, minute, period = int(m.group(1)), m.group(2).lower(), (int(m.group(3)) if m.group(3) else now.year), int(m.group(4)), (int(m.group(5)) if m.group(5) else 0), m.group(6)
        mes = int(mes_str) if mes_str.isdigit() else MESES.get(mes_str)
        if mes and 1 <= dia <= 31 and 1 <= mes <= 12:
            hora = min(23, max(0, adjust_am_pm_hour(h_str, period)))
            try:
                tz = getattr(now, "tzinfo", None) or ZoneInfo(tz_iana)
                _, last_day = monthrange(ano, mes)
                target = datetime(ano, mes, min(dia, last_day), hora, minute, 0, tzinfo=tz)
                delta = (target - now).total_seconds()
                if target < now and target.date() == now.date() and delta >= -86400:
                    return {"in_seconds": int(delta), "message": clean_message(strip_pattern(text, _pat_data_hora))}
                if target < now:
                    _, last_day = monthrange(ano + 1, mes)
                    target_next = datetime(ano + 1, mes, min(dia, last_day), hora, minute, 0, tzinfo=tz)
                    return {"date_in_past": True, "in_seconds": int((target_next - now).total_seconds()), "message": clean_message(strip_pattern(text, _pat_data_hora))}
                return {"in_seconds": int(delta), "message": clean_message(strip_pattern(text, _pat_data_hora))}
            except Exception: pass

    # 12. Dia N às hour (sem mês)
    _pat_dia_sozinho_hora = r"(?:dia\s+|day\s+|el\s+d[íi]a\s+)(\d{1,2})(?!\s*(?:de|/|-))\s*(?:às?|as|at|a\s+las?)\s*(\d{1,2})\s*(?:h|:)?\s*(\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\s*"
    m = re.search(_pat_dia_sozinho_hora, text_lower, re.I)
    if m:
        dia_target, hora, minute, period = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), m.group(4)
        hora = min(23, max(0, adjust_am_pm_hour(hora, period)))
        if 1 <= dia_target <= 31:
            try:
                tz = getattr(now, "tzinfo", None) or ZoneInfo(tz_iana)
                target = now.replace(day=min(dia_target, 28), hour=hora, minute=minute, second=0, microsecond=0)
                _, last_day = monthrange(target.year, target.month); target = target.replace(day=min(dia_target, last_day))
                if target < now:
                    if now.month == 12: target = now.replace(year=now.year + 1, month=1, day=min(dia_target, 28), hour=hora, minute=minute)
                    else: target = now.replace(month=now.month + 1, day=min(dia_target, 28), hour=hora, minute=minute)
                    _, last_day = monthrange(target.year, target.month); target = target.replace(day=min(dia_target, last_day))
                return {"in_seconds": int((target - now).total_seconds()), "message": clean_message(strip_pattern(text, _pat_dia_sozinho_hora))}
            except Exception: pass

    # 13. Dia 21/04
    _pat_data = (r"(?:dia\s+)?(\d{1,2})[ºª]?" + _SEP + r"(\d{1,2}|" + _MONTH_NAMES_STR + r")" + r"(?:" + _SEP + r"(\d{4}))?\b")
    _pat_data_strip = (r"(?:dia\s+)?\d{1,2}[ºª]?" + _SEP + r"(?:\d{1,2}|" + _MONTH_NAMES_STR + r")" + r"(?:" + _SEP + r"\d{4})?\s*")
    m = re.search(_pat_data, text_lower, re.I)
    if m:
        dia, mes_str, ano = int(m.group(1)), m.group(2).lower(), (int(m.group(3)) if m.group(3) else now.year)
        mes = int(mes_str) if mes_str.isdigit() else MESES.get(mes_str)
        if mes and 1 <= dia <= 31 and 1 <= mes <= 12:
            try:
                tz = getattr(now, "tzinfo", None) or ZoneInfo(tz_iana)
                _, last_day = monthrange(ano, mes); target = datetime(ano, mes, min(dia, last_day), 9, 0, 0, tzinfo=tz)
                if target < now:
                    _, last_day = monthrange(ano + 1, mes); target_next = datetime(ano + 1, mes, min(dia, last_day), 9, 0, 0, tzinfo=tz)
                    return {"date_in_past": True, "in_seconds": int((target_next - now).total_seconds()), "message": clean_message(strip_pattern(text, _pat_data_strip))}
                return {"in_seconds": int((target - now).total_seconds()), "message": clean_message(strip_pattern(text, _pat_data_strip))}
            except Exception: pass

    # 14. Todo dia (exato)
    if re.search(r"^(?:todo\s+dia|todos\s+os\s+dias|every\s+day|todos\s+los\s+d[íi]as|cada\s+d[íi]a)\s*$", text_lower):
        return {"cron_expr": "0 9 * * *", "message": "Lembrete"}

    # 15. Weekly fallback
    for dia_name, cron_dow in DIAS_SEMANA.items():
        pat = rf"\b(?:toda|every|cada)\s+(?:semana\s+|week\s+)?{re.escape(dia_name)}(?:\s*-?\s*f[eé]ira)?\b\s+(?:às?|as|at|a\s+las?)\s*(\d{{1,2}})(?::(\d{{2}}))?\s*" + _AM_PM_MODIFIERS + r"?\s*h?\b"
        m = re.search(pat, text_lower, re.I)
        if m:
            hora, minute, period = int(m.group(1)), int(m.group(2) or 0), m.group(3)
            hora = min(23, max(0, adjust_am_pm_hour(hora, period)))
            return {"cron_expr": f"{minute} {hora} * * {cron_dow}", "message": clean_message(re.sub(pat, "", text, flags=re.I).strip())}

    # 16. Monthly fallback (doubled in original?)
    m = re.search(r"(?:mensalmente|monthly|mensualmente)\s+(?:dia\s+|day\s+)?(\d{1,2})\s*(?:às?|as|at|a\s+las?)\s*(\d{1,2})\s*h?\b", text_lower, re.I)
    if m:
        dia_mes, hora = int(m.group(1)), min(23, max(0, int(m.group(2))))
        if 1 <= dia_mes <= 28:
            return {"cron_expr": f"0 {hora} {dia_mes} * *", "message": clean_message(strip_pattern(text, r"(?:mensalmente|monthly|mensualmente)\s+(?:dia\s+|day\s+)?\d{1,2}\s*(?:às?|as|at|a\s+las?)\s*\d{1,2}\s*h?\s*"))}

    # 17. Hoje/Amanhã/Semaval sem hora
    _vague_days = {"hoje": 0, "hoy": 0, "today": 0, "amanhã": 1, "amanha": 1, "mañana": 1, "tomorrow": 1}
    for word, days_offset in _vague_days.items():
        if word in text_lower:
            delta = ((now + timedelta(days=days_offset)).replace(hour=9, minute=0, second=0, microsecond=0) - now).total_seconds()
            if delta > 0: return {"in_seconds": int(delta), "message": clean_message(strip_pattern(text, rf"\b{re.escape(word)}\b"))}
    for dia_name, cron_dow in DIAS_SEMANA.items():
        pat = rf"\b{re.escape(dia_name)}(?:\s*-?\s*f[eé]ira)?\b"
        if re.search(pat, text_lower, re.I):
            days_ahead = (cron_dow - ((now.weekday() + 1) % 7) + 7) % 7
            if days_ahead == 0 and now.hour >= 9: days_ahead = 7
            delta = ((now + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0) - now).total_seconds()
            if delta > 0: return {"in_seconds": int(delta), "message": clean_message(strip_pattern(text, pat))}

    return {"message": text}
