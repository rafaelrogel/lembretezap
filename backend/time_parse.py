"""Parse de datas/horários e recorrência para lembretes.

Extraído do command_parser para manter o parse de comandos enxuto.
O parse() de comando chama parse_lembrete_time() quando detecta /lembrete.
Usa tz_iana (ex. America/Sao_Paulo) para «hoje», «amanhã» e datas no fuso do utilizador.
"""

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

# Recorrência: dia da semana em cron (0=domingo, 1=segunda, ..., 6=sábado)
DIAS_SEMANA = {
    "segunda-feira": 1, "terça-feira": 2, "terca-feira": 2, "quarta-feira": 3, "quinta-feira": 4, "sexta-feira": 5,
    "domingo": 0, "segunda": 1, "terça": 2, "terca": 2, "quarta": 3, "quinta": 4, "sexta": 5,
    "sábado": 6, "sabado": 6,
}

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
    # EN
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
    # ES
    "enero": 1, "febrero": 2, "marzo": 3, "mayo": 5,
    "junio": 6, "julio": 7, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Common separator between day↔month and month↔year: de, /, -, or whitespace
_SEP = r"(?:\s*(?:de|/|-)\s*|\s+)"
# Month names for regex (all languages)
_MONTH_NAMES = (
    r"janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
    r"|january|february|march|april|may|june|july|august|september|october|november|december"
    r"|enero|febrero|marzo|mayo|junio|julio|septiembre|octubre|noviembre|diciembre"
)

RE_LEMBRETE_DAQUI = re.compile(r"daqui\s+a\s+(\d+)\s*(minutos?|minuto?|min|horas?|hora?|dias?|dia?)\b", re.I)
RE_LEMBRETE_EM = re.compile(r"em\s+(\d+)\s*(minutos?|minuto?|min|horas?|hora?|dias?|dia?)\b", re.I)

# Modificadores de período (PT, ES, EN)
_AM_PM_MODIFIERS = (
    r"("
    r"(?:da|de|na|[àa]s?)\s+(?:manh[ãa]|tarde|noite)|"
    r"(?:de|por)\s+la\s+(?:ma[ñn]ana|tarde|noche)|"
    r"in\s+the\s+(?:morning|afternoon|evening)|"
    r"at\s+night|"
    r"a\.?m\.?|p\.?m\.?"
    r")"
)

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
    """Remove o padrão do texto e retorna limpo. pattern pode ser str ou re.Pattern."""
    if isinstance(pattern, str):
        return re.sub(pattern, "", text, flags=re.I).strip()
    return pattern.sub("", text).strip()


def clean_message(t: str) -> str:
    """Remove conectores e barras do início (ex.: «30 min/ lembre-me» → «lembre-me»)."""
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
    """Extrai «a partir de 1º de julho» → '2026-07-01'. Retorna None se não encontrar. Ano atual no fuso tz_iana."""
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
        r"a\s+partir\s+de\s+(\d{1,2})[ºª]?" + _SEP +
        r"(\d{1,2}|" + _MONTH_NAMES + r")"
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
                dt = datetime(ano, mes, min(dia, 28))
                return dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
    return None


def parse_lembrete_time(text: str, tz_iana: str = "UTC") -> dict[str, Any]:
    """Extrai in_seconds, every_seconds ou cron_expr e message. Suporta recorrência.
    tz_iana: fuso do utilizador para «hoje», «amanhã» e datas (ex. America/Sao_Paulo)."""
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

    # Detect explicit timezone mention (e.g. "no fuso do Amapá", "no fuso de Lisboa")
    original_tz_iana = tz_iana
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
                logger.info(f"parse_lembrete_time: overriding tz '{original_tz_iana}' with '{found_tz}' from '{possible_city}'")
        except Exception:
            pass

    for pattern in (RE_LEMBRETE_DAQUI, RE_LEMBRETE_EM):
        m = pattern.search(text)
        if m:
            n = int(m.group(1))
            unit = (m.group(2) or "").lower()
            if "hora" in unit:
                n *= 3600
            elif "dia" in unit:
                n *= 86400
            else:
                n *= 60
            if n > 0 and n <= 86400 * 30:
                message = (text[: m.start()] + text[m.end() :]).strip()
                return {"in_seconds": n, "message": clean_message(message)}

    m = re.search(r"a\s+cada\s+(\d+)\s*(minuto?s?|hora?s?|dia?s?)\b", text_lower, re.I)
    if m:
        num = int(m.group(1))
        u = (m.group(2) or "").lower()
        if "hora" in u:
            every = num * 3600
        elif "dia" in u:
            every = num * 86400
        else:
            every = num * 60
        if 1800 <= every <= 86400 * 30:
            message = strip_pattern(text, r"a\s+cada\s+\d+\s*(minuto?s?|hora?s?|dia?s?)\s*")
            return {"every_seconds": every, "message": clean_message(message)}

    m = re.search(
        r"(?:(?:(?:[àa]s?|at|a\s+las?)\s*)?(\d{1,2})(?:h|:|min)?(\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\s*(?:de\s+)?(?:hoje|hoy|today)\b|"
        r"(?:hoje|hoy|today)\s+(?:(?:[àa]s?|at|a\s+las?)\s*)?(\d{1,2})(?:h|:)?(\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\b)",
        text_lower,
        re.I,
    )
    if m:
        if m.group(1):
            hora = int(m.group(1))
            minute = int(m.group(2) or 0)
            period = m.group(3)
        else:
            hora = int(m.group(4))
            minute = int(m.group(5) or 0)
            period = m.group(6)
        
        hora = adjust_am_pm_hour(hora, period)

        if not period and hora < 12 and "h" in text_lower and not ("manh" in text_lower or "tarde" in text_lower or "morn" in text_lower or "after" in text_lower):
             pass

        hora = min(23, max(0, hora))
        message = strip_pattern(text, m.group(0))
        today_at = now.replace(hour=hora, minute=minute, second=0, microsecond=0)
        delta = (today_at - now).total_seconds()
        
        # Se for no passado hoje (ex.: 01:20 vindo às 01:31), retornar delta negativo
        # O CronTool irá validar e recusar se for > 2 min.
        return {"in_seconds": int(delta), "message": clean_message(message)}

    m = re.search(
        r"(?:amanh[ãa]|ma[ñn]ana|tomorrow)\s+(?:(?:[àa]s?|at|a\s+las?)\s*)?(\d{1,2})(?:h|:)?(\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\b",
        text_lower,
        re.I,
    )
    if m:
        hora = min(23, max(0, int(m.group(1))))
        minute = int(m.group(2) or 0)
        hora = adjust_am_pm_hour(hora, m.group(3))
        message = strip_pattern(text, m.group(0))
        tomorrow = (now + timedelta(days=1)).replace(
            hour=hora, minute=minute, second=0, microsecond=0
        )
        delta = (tomorrow - now).total_seconds()
        if delta > 0 and delta <= 86400 * 30:
            return {"in_seconds": int(delta), "message": clean_message(message)}

    if "a partir de" in text_lower:
        m = re.search(
            r"(?:todo\s+dia|todos\s+os\s+dias|diariamente)\s+(?:às?|as)\s*(\d{1,2})\s*h?\b",
            text_lower,
            re.I,
        )
        if m:
            hora = min(23, max(0, int(m.group(1))))
            message = strip_pattern(
                text, r"(?:todo\s+dia|todos\s+os\s+dias|diariamente)\s+(?:às?|as)\s*\d{1,2}\s*h?\s*"
            )
            out = {"cron_expr": f"0 {hora} * * *", "message": clean_message(message)}
            sd = extract_start_date(text, tz_iana)
            if sd:
                out["start_date"] = sd
            return out
        for dia_name, cron_dow in DIAS_SEMANA.items():
            pat = rf"\btoda\s+(?:semana\s+)?{re.escape(dia_name)}\b\s+(?:às?|as)\s*(\d{{1,2}})\s*h?\b"
            m = re.search(pat, text_lower, re.I)
            if m:
                hora = min(23, max(0, int(m.group(1))))
                message = re.sub(pat, "", text, flags=re.I).strip()
                out = {"cron_expr": f"0 {hora} * * {cron_dow}", "message": clean_message(message)}
                sd = extract_start_date(text, tz_iana)
                if sd:
                    out["start_date"] = sd
                return out

    _pat_data_hora = (
        r"(?:dia\s+)?(\d{1,2})[ºª]?" + _SEP +
        r"(\d{1,2}|" + _MONTH_NAMES + r")"
        r"(?:" + _SEP + r"(\d{4}))?\s*(?:às?|as|at|a\s+las?)\s*(\d{1,2})\s*(?:h|:)\s*(\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\s*"
    )
    m = re.search(_pat_data_hora, text_lower, re.I)
    if m:
        dia = int(m.group(1))
        mes_str = m.group(2).lower()
        mes = int(mes_str) if mes_str.isdigit() else MESES.get(mes_str)
        ano = int(m.group(3)) if m.group(3) else now.year
        minute = int(m.group(5)) if m.group(5) else 0
        period = m.group(6)
        if mes and 1 <= dia <= 31 and 1 <= mes <= 12:
            hora = min(23, max(0, int(m.group(4))))
            hora = adjust_am_pm_hour(hora, period)
            try:
                tz = getattr(now, "tzinfo", None) or ZoneInfo(tz_iana)
                target = datetime(ano, mes, min(dia, 28), hora, minute, 0, tzinfo=tz)
                delta = (target - now).total_seconds()
                if target < now and target.date() == now.date() and delta >= -86400:
                    # Hoje mas o horário já passou: devolver in_seconds negativo para o cron avisar (não agendar ano seguinte)
                    message = strip_pattern(text, _pat_data_hora)
                    return {"in_seconds": int(delta), "message": clean_message(message)}
                if target < now:
                    # Data inteira no passado: não agendar; avisar e pedir confirmação para ano seguinte
                    target_next = datetime(ano + 1, mes, min(dia, 28), hora, minute, 0, tzinfo=tz)
                    delta_next = (target_next - now).total_seconds()
                    if delta_next > 0 and delta_next <= 86400 * 366:
                        message = strip_pattern(text, _pat_data_hora)
                        return {
                            "date_in_past": True,
                            "in_seconds": int(delta_next),
                            "message": clean_message(message),
                        }
                    return None
                if delta > 0 and delta <= 86400 * 365:
                    message = strip_pattern(text, _pat_data_hora)
                    return {"in_seconds": int(delta), "message": clean_message(message)}
            except (ValueError, TypeError):
                pass

    # Novo: "dia 22 às 9h" (sem mês)
    _pat_dia_sozinho_hora = r"(?:dia\s+)(\d{1,2})(?!\s*(?:de|/|-))\s*(?:às?|as|at|a\s+las?)\s*(\d{1,2})\s*(?:h|:)?\s*(\d{2})?\s*" + _AM_PM_MODIFIERS + r"?\s*"
    m = re.search(_pat_dia_sozinho_hora, text_lower, re.I)
    if m:
        dia_target = int(m.group(1))
        hora = int(m.group(2))
        minute = int(m.group(3) or 0)
        period = m.group(4)
        hora = adjust_am_pm_hour(hora, period)
        if 1 <= dia_target <= 31:
            try:
                tz = getattr(now, "tzinfo", None) or ZoneInfo(tz_iana)
                # Tenta este mês
                try:
                    target = now.replace(day=dia_target, hour=hora, minute=minute, second=0, microsecond=0)
                except ValueError:
                    # Se o dia não existe este mês (ex: dia 31 em Abril), pula para o próximo mês
                    target = now.replace(day=1) + timedelta(days=32)
                    target = target.replace(day=dia_target, hour=hora, minute=minute)
                
                if target < now:
                    # Se já passou, tenta o próximo mês
                    # Mover para o dia 1 do próximo mês e então definir o dia
                    if now.month == 12:
                        target = now.replace(year=now.year + 1, month=1, day=dia_target, hour=hora, minute=minute)
                    else:
                        target = now.replace(month=now.month + 1, day=min(dia_target, 28), hour=hora, minute=minute)
                        # Tenta restaurar o dia exato se possível (evita dia 31 -> 28 se o dia existe no próximo mês)
                        try:
                            # Próximo mês real
                            from calendar import monthrange
                            _, last_day = monthrange(target.year, target.month)
                            target = target.replace(day=min(dia_target, last_day))
                        except Exception: pass

                delta = (target - now).total_seconds()
                if delta > 0:
                    message = strip_pattern(text, _pat_dia_sozinho_hora)
                    return {"in_seconds": int(delta), "message": clean_message(message)}
            except Exception:
                pass

    _pat_data = (
        r"(?:dia\s+)?(\d{1,2})[ºª]?" + _SEP +
        r"(\d{1,2}|" + _MONTH_NAMES + r")"
        r"(?:" + _SEP + r"(\d{4}))?\b"
    )
    _pat_data_strip = (
        r"(?:dia\s+)?\d{1,2}[ºª]?" + _SEP +
        r"(?:\d{1,2}|" + _MONTH_NAMES + r")"
        r"(?:" + _SEP + r"\d{4})?\s*"
    )
    m = re.search(_pat_data, text_lower, re.I)
    if m:
        dia = int(m.group(1))
        mes_str = m.group(2).lower()
        mes = int(mes_str) if mes_str.isdigit() else MESES.get(mes_str)
        ano = int(m.group(3)) if m.group(3) else now.year
        if mes and 1 <= dia <= 31 and 1 <= mes <= 12:
            hora = 9
            try:
                tz = getattr(now, "tzinfo", None) or ZoneInfo(tz_iana)
                target = datetime(ano, mes, min(dia, 28), hora, 0, 0, tzinfo=tz)
                if target < now:
                    # Data no passado: pedir confirmação para ano seguinte
                    target_next = datetime(ano + 1, mes, min(dia, 28), hora, 0, 0, tzinfo=tz)
                    delta_next = (target_next - now).total_seconds()
                    if delta_next > 0 and delta_next <= 86400 * 366:
                        message = strip_pattern(text, _pat_data_strip)
                        return {
                            "date_in_past": True,
                            "in_seconds": int(delta_next),
                            "message": clean_message(message),
                        }
                    return None
                delta = (target - now).total_seconds()
                if delta > 0 and delta <= 86400 * 365:
                    message = strip_pattern(text, _pat_data_strip)
                    return {"in_seconds": int(delta), "message": clean_message(message)}
            except (ValueError, TypeError):
                pass

    m = re.search(
        r"(?:todo\s+dia|todos\s+os\s+dias|diariamente)\s+às?\s*(\d{1,2})\s*h?\b",
        text_lower,
        re.I,
    )
    if m:
        hora = min(23, max(0, int(m.group(1))))
        message = strip_pattern(
            text,
            r"(?:todo\s+dia|todos\s+os\s+dias|diariamente)\s+às?\s*\d{1,2}\s*h?\s*",
        )
        return {"cron_expr": f"0 {hora} * * *", "message": clean_message(message)}

    m = re.search(r"(?:todo\s+dia|todos\s+os\s+dias)\s+(.+)$", text_lower, re.I)
    if m:
        message = m.group(1).strip()
        return {"cron_expr": "0 9 * * *", "message": clean_message(message)}
    if re.search(r"^(?:todo\s+dia|todos\s+os\s+dias)\s*$", text_lower):
        return {"cron_expr": "0 9 * * *", "message": "Lembrete"}

    for dia_name, cron_dow in DIAS_SEMANA.items():
        pat = rf"\btoda\s+(?:semana\s+)?{re.escape(dia_name)}\b\s+às?\s*(\d{{1,2}})\s*h?\b"
        m = re.search(pat, text_lower, re.I)
        if m:
            hora = min(23, max(0, int(m.group(1))))
            message = re.sub(pat, "", text, flags=re.I).strip()
            return {"cron_expr": f"0 {hora} * * {cron_dow}", "message": clean_message(message)}

    m = re.search(
        r"mensalmente\s+(?:dia\s+)?(\d{1,2})\s*às?\s*(\d{1,2})\s*h?\b",
        text_lower,
        re.I,
    )
    if m:
        dia_mes = int(m.group(1))
        hora = min(23, max(0, int(m.group(2))))
        if 1 <= dia_mes <= 28:
            message = strip_pattern(
                text,
                r"mensalmente\s+(?:dia\s+)?\d{1,2}\s*às?\s*\d{1,2}\s*h?\s*",
            )
            return {"cron_expr": f"0 {hora} {dia_mes} * *", "message": clean_message(message)}

    # Hoje/Amanhã/Days of week WITHOUT time: default to 9:00 AM
    _vague_days = {
        "hoje": 0, "hoy": 0, "today": 0,
        "amanhã": 1, "amanha": 1, "mañana": 1, "mañana": 1, "tomorrow": 1,
    }
    for word, days_offset in _vague_days.items():
        if word in text_lower:
            target = (now + timedelta(days=days_offset)).replace(hour=9, minute=0, second=0, microsecond=0)
            delta = (target - now).total_seconds()
            if delta > 0:
                message = strip_pattern(text, rf"\b{re.escape(word)}\b")
                return {"in_seconds": int(delta), "message": clean_message(message)}

    for dia_name, cron_dow in DIAS_SEMANA.items():
        if re.search(rf"\b{re.escape(dia_name)}\b", text_lower, re.I):
            # Python weekday(): 0=Seg, 6=Dom.
            # Nosso cron_dow: 0=Dom, 1=Seg, ..., 5=Sex, 6=Sáb.
            # Normalizar agora para 0=Dom:
            now_dow_normalized = (now.weekday() + 1) % 7
            days_ahead = (cron_dow - now_dow_normalized + 7) % 7
            if days_ahead == 0 and now.hour >= 9:
                days_ahead = 7
            target = (now + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0)
            delta = (target - now).total_seconds()
            if delta > 0:
                message = strip_pattern(text, rf"\b{re.escape(dia_name)}\b")
                return {"in_seconds": int(delta), "message": clean_message(message)}

    return {"message": text}
