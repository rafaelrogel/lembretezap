"""Parser de comandos: /lembrete, /list, /feito, /filme. Retorna intent estruturado ou None.

Suporta lembretes pontuais e recorrentes (diário, semanal, a cada N, mensal).
"""

import re
from typing import Any

# Padrões
RE_LEMBRETE = re.compile(r"^/lembrete\s+(.+)$", re.I)
RE_LEMBRETE_DAQUI = re.compile(r"daqui\s+a\s+(\d+)\s*(min|minuto|hora|dia)s?", re.I)
RE_LEMBRETE_EM = re.compile(r"em\s+(\d+)\s*(min|minuto|hora|dia)s?", re.I)

RE_LIST_ADD = re.compile(r"^/list\s+(\S+)\s+add\s+(.+)$", re.I)
# /list filme|livro|musica|receita <item> (categorias especiais; sem "add")
RE_LIST_CATEGORY_ADD = re.compile(
    r"^/list\s+(filme|filmes|livro|livros|musica|musicas|música|músicas|receita|receitas)\s+(.+)$",
    re.I,
)
RE_LIST_SHOW = re.compile(r"^/list\s+(\S+)\s*$", re.I)
RE_LIST_ALL = re.compile(r"^/list\s*$", re.I)
RE_FEITO_ID = re.compile(r"^/feito\s+(\d+)\s*$", re.I)
RE_FEITO_LIST_ID = re.compile(r"^/feito\s+(\S+)\s+(\d+)\s*$", re.I)
# Atalhos: /filme, /livro, /musica, /receita → equivalente a /list filme|livro|musica|receita <item>
RE_FILME = re.compile(r"^/filme\s+(.+)$", re.I)
RE_LIVRO = re.compile(r"^/livro\s+(.+)$", re.I)
RE_MUSICA = re.compile(r"^/musica\s+(.+)$", re.I)
RE_MUSICA_ACCENT = re.compile(r"^/música\s+(.+)$", re.I)
RE_RECEITA = re.compile(r"^/receita\s+(.+)$", re.I)

# Normalizar categoria para singular (list_name)
_CATEGORY_TO_LIST = {
    "filme": "filme", "filmes": "filme",
    "livro": "livro", "livros": "livro",
    "musica": "musica", "musicas": "musica", "música": "musica", "músicas": "musica",
    "receita": "receita", "receitas": "receita",
}

# Recorrência: dia da semana em cron (0=domingo, 1=segunda, ..., 6=sábado)
DIAS_SEMANA = {
    "domingo": 0, "segunda": 1, "terça": 2, "terca": 2, "quarta": 3, "quinta": 4,
    "sexta": 5, "sábado": 6, "sabado": 6,
    "segunda-feira": 1, "terça-feira": 2, "quarta-feira": 3, "quinta-feira": 4, "sexta-feira": 5,
}


def _clean_message(t: str) -> str:
    """Remove conectores e barras do início (ex.: «30 min/ lembre-me» → «lembre-me»)."""
    t = t.strip()
    # Suporte a "/lembrete daqui a 30 min/ texto" — remover "/ " ou "/" no início do texto
    while t.startswith("/"):
        t = t.lstrip("/").strip()
    for prefix in ("de ", "para ", "a ", "sobre "):
        if t.lower().startswith(prefix) and len(t) > len(prefix):
            t = t[len(prefix):].strip()
    return t or "Lembrete"


def _parse_lembrete_time(text: str) -> dict[str, Any]:
    """Extrai in_seconds, every_seconds ou cron_expr e message. Suporta recorrência."""
    text = text.strip()
    text_lower = text.lower()

    # --- Um único disparo: "daqui a X min" / "em X minutos"
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
                return {"in_seconds": n, "message": _clean_message(message)}

    # --- Recorrência: "a cada N minutos/horas/dias"
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
        if 1800 <= every <= 86400 * 30:  # mínimo 30 min, máximo 30 dias
            message = re.sub(r"a\s+cada\s+\d+\s*(minuto?s?|hora?s?|dia?s?)\s*", "", text, flags=re.I).strip()
            return {"every_seconds": every, "message": _clean_message(message)}

    # --- Pontual: "amanhã às 12h" / "amanhã 12h" / "amanhã 9h"
    from datetime import datetime, timedelta
    m = re.search(
        r"amanh[ãa]\s+(?:às?\s*)?(\d{1,2})\s*h?\b",
        text_lower,
        re.I,
    )
    if m:
        hora = min(23, max(0, int(m.group(1))))
        message = re.sub(
            r"amanh[ãa]\s+(?:às?\s*)?\d{1,2}\s*h?\s*",
            "",
            text,
            flags=re.I,
        ).strip()
        tomorrow = (datetime.now() + timedelta(days=1)).replace(
            hour=hora, minute=0, second=0, microsecond=0
        )
        delta = (tomorrow - datetime.now()).total_seconds()
        if delta > 0 and delta <= 86400 * 30:
            return {"in_seconds": int(delta), "message": _clean_message(message)}

    # --- Pontual: "1º de julho às 20h" / "dia 15 de março às 10h" (data+hora)
    _pat_data_hora = (
        r"(?:dia\s+)?(\d{1,2})[ºª]?\s*(?:de|/)\s*"
        r"(\d{1,2}|janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
        r"\s*(?:de\s+\d{4})?\s*(?:às?|as)\s*(\d{1,2})\s*h?\b"
    )
    m = re.search(_pat_data_hora, text_lower, re.I)
    if m:
        dia = int(m.group(1))
        mes_str = m.group(2).lower()
        meses = {
            "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
            "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
            "novembro": 11, "dezembro": 12,
        }
        mes = int(mes_str) if mes_str.isdigit() else meses.get(mes_str)
        if mes and 1 <= dia <= 31 and 1 <= mes <= 12:
            hora = min(23, max(0, int(m.group(3))))
            ano = datetime.now().year
            try:
                target = datetime(ano, mes, min(dia, 28), hora, 0, 0)
                if target < datetime.now():
                    target = datetime(ano + 1, mes, min(dia, 28), hora, 0, 0)
                delta = (target - datetime.now()).total_seconds()
                if delta > 0 and delta <= 86400 * 365:
                    message = re.sub(_pat_data_hora, "", text, flags=re.I).strip()
                    return {"in_seconds": int(delta), "message": _clean_message(message)}
            except (ValueError, TypeError):
                pass

    # --- Pontual: "1º de julho" / "dia 15 de março" (data sem hora → 9h)
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
        meses = {
            "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
            "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
            "novembro": 11, "dezembro": 12,
        }
        mes = int(mes_str) if mes_str.isdigit() else meses.get(mes_str)
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
                    message = re.sub(_pat_data, "", text, flags=re.I).strip()
                    return {"in_seconds": int(delta), "message": _clean_message(message)}
            except (ValueError, TypeError):
                pass

    # --- Diário: "todo dia às 9h" / "todos os dias às 14h" / "diariamente às 8h"
    m = re.search(
        r"(?:todo\s+dia|todos\s+os\s+dias|diariamente)\s+às?\s*(\d{1,2})\s*h?\b",
        text_lower,
        re.I,
    )
    if m:
        hora = min(23, max(0, int(m.group(1))))
        message = re.sub(
            r"(?:todo\s+dia|todos\s+os\s+dias|diariamente)\s+às?\s*\d{1,2}\s*h?\s*",
            "",
            text,
            flags=re.I,
        ).strip()
        return {"cron_expr": f"0 {hora} * * *", "message": _clean_message(message)}

    # "todo dia" / "todos os dias" sem hora -> 9h; mensagem = resto do texto
    m = re.search(r"(?:todo\s+dia|todos\s+os\s+dias)\s+(.+)$", text_lower, re.I)
    if m:
        message = m.group(1).strip()
        return {"cron_expr": "0 9 * * *", "message": _clean_message(message)}
    if re.search(r"^(?:todo\s+dia|todos\s+os\s+dias)\s*$", text_lower):
        return {"cron_expr": "0 9 * * *", "message": "Lembrete"}

    # --- Semanal: "toda segunda às 10h" / "toda semana segunda-feira às 9h"
    for dia_name, cron_dow in DIAS_SEMANA.items():
        # "toda segunda às 10h" ou "toda semana segunda às 10h"
        pat = rf"toda\s+(?:semana\s+)?{re.escape(dia_name)}\s+às?\s*(\d{{1,2}})\s*h?\b"
        m = re.search(pat, text_lower, re.I)
        if m:
            hora = min(23, max(0, int(m.group(1))))
            message = re.sub(pat, "", text, flags=re.I).strip()
            return {"cron_expr": f"0 {hora} * * {cron_dow}", "message": _clean_message(message)}

    # --- Mensal: "mensalmente dia 15 às 10h" / "todo dia 5 do mês às 9h"
    m = re.search(
        r"mensalmente\s+(?:dia\s+)?(\d{1,2})\s*às?\s*(\d{1,2})\s*h?\b",
        text_lower,
        re.I,
    )
    if m:
        dia_mes = int(m.group(1))
        hora = min(23, max(0, int(m.group(2))))
        if 1 <= dia_mes <= 28:
            message = re.sub(
                r"mensalmente\s+(?:dia\s+)?\d{1,2}\s*às?\s*\d{1,2}\s*h?\s*",
                "",
                text,
                flags=re.I,
            ).strip()
            return {"cron_expr": f"0 {hora} {dia_mes} * *", "message": _clean_message(message)}

    # Sem tempo claro
    return {"message": text}


def parse(raw: str) -> dict[str, Any] | None:
    """Parseia a mensagem. Retorna um intent dict ou None."""
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None

    m = RE_LEMBRETE.match(text)
    if m:
        rest = m.group(1).strip()
        if rest:
            intent = _parse_lembrete_time(rest)
            intent["type"] = "lembrete"
            return intent
        return None

    m = RE_LIST_ADD.match(text)
    if m:
        return {"type": "list_add", "list_name": m.group(1).strip(), "item": m.group(2).strip()}
    m = RE_LIST_CATEGORY_ADD.match(text)
    if m:
        cat = m.group(1).strip().lower()
        list_name = _CATEGORY_TO_LIST.get(cat, cat)
        return {"type": "list_add", "list_name": list_name, "item": m.group(2).strip()}
    m = RE_LIST_SHOW.match(text)
    if m:
        return {"type": "list_show", "list_name": m.group(1).strip()}
    if RE_LIST_ALL.match(text):
        return {"type": "list_show", "list_name": None}

    m = RE_FEITO_LIST_ID.match(text)
    if m:
        return {"type": "feito", "list_name": m.group(1).strip(), "item_id": int(m.group(2))}
    m = RE_FEITO_ID.match(text)
    if m:
        return {"type": "feito", "list_name": None, "item_id": int(m.group(1))}

    # Atalhos: /filme X, /livro X, /musica X, /receita X → list_add (tudo dentro de /list)
    m = RE_FILME.match(text)
    if m:
        return {"type": "list_add", "list_name": "filme", "item": m.group(1).strip()}
    m = RE_LIVRO.match(text)
    if m:
        return {"type": "list_add", "list_name": "livro", "item": m.group(1).strip()}
    m = RE_MUSICA.match(text) or RE_MUSICA_ACCENT.match(text)
    if m:
        return {"type": "list_add", "list_name": "musica", "item": m.group(1).strip()}
    m = RE_RECEITA.match(text)
    if m:
        return {"type": "list_add", "list_name": "receita", "item": m.group(1).strip()}

    return None
