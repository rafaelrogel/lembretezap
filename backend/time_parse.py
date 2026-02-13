"""Parse de datas/horários e recorrência para lembretes.

Extraído do command_parser para manter o parse de comandos enxuto.
O parse() de comando chama parse_lembrete_time() quando detecta /lembrete.
"""

import re
from datetime import datetime, timedelta
from typing import Any

# Recorrência: dia da semana em cron (0=domingo, 1=segunda, ..., 6=sábado)
DIAS_SEMANA = {
    "domingo": 0, "segunda": 1, "terça": 2, "terca": 2, "quarta": 3, "quinta": 4,
    "sexta": 5, "sábado": 6, "sabado": 6,
    "segunda-feira": 1, "terça-feira": 2, "quarta-feira": 3, "quinta-feira": 4, "sexta-feira": 5,
}

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}

RE_LEMBRETE_DAQUI = re.compile(r"daqui\s+a\s+(\d+)\s*(min|minuto|hora|dia)s?", re.I)
RE_LEMBRETE_EM = re.compile(r"em\s+(\d+)\s*(min|minuto|hora|dia)s?", re.I)


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
    for prefix in ("de ", "para ", "a ", "sobre "):
        if t.lower().startswith(prefix) and len(t) > len(prefix):
            t = t[len(prefix):].strip()
    t = re.sub(r"\s+at[eé]\s*$", "", t, flags=re.I)
    return t or "Lembrete"


def extract_start_date(text: str) -> str | None:
    """Extrai «a partir de 1º de julho» → '2026-07-01'. Retorna None se não encontrar."""
    text_lower = (text or "").strip().lower()
    m = re.search(
        r"a\s+partir\s+de\s+(\d{1,2})[ºª]?\s*(?:de\s+)?"
        r"(\d{1,2}|janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
        r"(?:\s+de\s+(\d{4}))?\b",
        text_lower,
        re.I,
    )
    if m:
        dia = int(m.group(1))
        mes_str = m.group(2).lower()
        mes = int(mes_str) if mes_str.isdigit() else MESES.get(mes_str)
        ano = int(m.group(3)) if m.group(3) else datetime.now().year
        if mes and 1 <= dia <= 31 and 1 <= mes <= 12:
            try:
                dt = datetime(ano, mes, min(dia, 28))
                return dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
    m = re.search(r"a\s+partir\s+de\s+(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b", text_lower, re.I)
    if m:
        dia, mes = int(m.group(1)), int(m.group(2))
        ano = int(m.group(3)) if m.group(3) else datetime.now().year
        if 1 <= dia <= 31 and 1 <= mes <= 12:
            try:
                dt = datetime(ano, mes, min(dia, 28))
                return dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
    return None


def parse_lembrete_time(text: str) -> dict[str, Any]:
    """Extrai in_seconds, every_seconds ou cron_expr e message. Suporta recorrência."""
    text = text.strip()
    text_lower = text.lower()

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
        r"amanh[ãa]\s+(?:às?\s*)?(\d{1,2})\s*h?\b",
        text_lower,
        re.I,
    )
    if m:
        hora = min(23, max(0, int(m.group(1))))
        message = strip_pattern(text, r"amanh[ãa]\s+(?:às?\s*)?\d{1,2}\s*h?\s*")
        tomorrow = (datetime.now() + timedelta(days=1)).replace(
            hour=hora, minute=0, second=0, microsecond=0
        )
        delta = (tomorrow - datetime.now()).total_seconds()
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
            sd = extract_start_date(text)
            if sd:
                out["start_date"] = sd
            return out
        for dia_name, cron_dow in DIAS_SEMANA.items():
            pat = rf"toda\s+(?:semana\s+)?{re.escape(dia_name)}\s+(?:às?|as)\s*(\d{{1,2}})\s*h?\b"
            m = re.search(pat, text_lower, re.I)
            if m:
                hora = min(23, max(0, int(m.group(1))))
                message = re.sub(pat, "", text, flags=re.I).strip()
                out = {"cron_expr": f"0 {hora} * * {cron_dow}", "message": clean_message(message)}
                sd = extract_start_date(text)
                if sd:
                    out["start_date"] = sd
                return out

    _pat_data_hora = (
        r"(?:dia\s+)?(\d{1,2})[ºª]?\s*(?:de|/)\s*"
        r"(\d{1,2}|janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
        r"\s*(?:de\s+\d{4})?\s*(?:às?|as)\s*(\d{1,2})\s*h?\b"
    )
    m = re.search(_pat_data_hora, text_lower, re.I)
    if m:
        dia = int(m.group(1))
        mes_str = m.group(2).lower()
        mes = int(mes_str) if mes_str.isdigit() else MESES.get(mes_str)
        if mes and 1 <= dia <= 31 and 1 <= mes <= 12:
            hora = min(23, max(0, int(m.group(3))))
            ano = datetime.now().year
            try:
                target = datetime(ano, mes, min(dia, 28), hora, 0, 0)
                if target < datetime.now():
                    target = datetime(ano + 1, mes, min(dia, 28), hora, 0, 0)
                delta = (target - datetime.now()).total_seconds()
                if delta > 0 and delta <= 86400 * 365:
                    message = strip_pattern(text, _pat_data_hora)
                    return {"in_seconds": int(delta), "message": clean_message(message)}
            except (ValueError, TypeError):
                pass

    m = re.search(
        r"(?:dia\s+)?(\d{1,2})[ºª]?\s*(?:de|/)\s*"
        r"(\d{1,2}|janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
        r"\s*(?:de\s+\d{4})?\b",
        text_lower,
        re.I,
    )
    if m:
        dia = int(m.group(1))
        mes_str = m.group(2).lower()
        mes = int(mes_str) if mes_str.isdigit() else MESES.get(mes_str)
        if mes and 1 <= dia <= 31 and 1 <= mes <= 12:
            hora = 9
            ano = datetime.now().year
            try:
                target = datetime(ano, mes, min(dia, 28), hora, 0, 0)
                if target < datetime.now():
                    target = datetime(ano + 1, mes, min(dia, 28), hora, 0, 0)
                delta = (target - datetime.now()).total_seconds()
                if delta > 0 and delta <= 86400 * 365:
                    _pat_data = r"(?:dia\s+)?\d{1,2}[ºª]?\s*(?:de|/)\s*(?:\d{1,2}|janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s*(?:de\s+\d{4})?\s*"
                    message = strip_pattern(text, _pat_data)
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
        pat = rf"toda\s+(?:semana\s+)?{re.escape(dia_name)}\s+às?\s*(\d{{1,2}})\s*h?\b"
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

    return {"message": text}
