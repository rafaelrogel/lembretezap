"""Parser de comandos: /lembrete, /list, /feito, /filme. Retorna intent estruturado ou None.

Suporta lembretes pontuais e recorrentes (diário, semanal, a cada N, mensal).
Parse de tempo/recorrência em backend.time_parse.
"""

import re
from typing import Any

from backend.time_parse import extract_start_date, parse_lembrete_time

# Padrões
RE_LEMBRETE = re.compile(r"^/lembrete\s+(.+)$", re.I)
RE_LIST_ADD = re.compile(r"^/list\s+(\S+)\s+add\s+(.+)$", re.I)
# /list filme|livro|musica|receita <item> (categorias especiais; sem "add")
RE_LIST_CATEGORY_ADD = re.compile(
    r"^/list\s+(filme|filmes|livro|livros|musica|musicas|música|músicas|receita|receitas)\s+(.+)$",
    re.I,
)
RE_LIST_SHOW = re.compile(r"^/list\s+(\S+)\s*$", re.I)
RE_LIST_ALL = re.compile(r"^/list\s*$", re.I)
# Linguagem natural: mostre lista X, lista de X, minha lista X, qual lista, mercado, compras
RE_NL_MOSTRE_LISTA = re.compile(
    r"^(?:mostr(?:e|ar)|ver|listar|mostra)\s+(?:a\s+)?(?:minha\s+)?lista\s+(?:de\s+)?(\w+)\s*$", re.I
)
RE_NL_LISTA_DE = re.compile(r"^lista\s+(?:de\s+)?(\w+)\s*\??\s*$", re.I)
RE_NL_QUAL_LISTA = re.compile(
    r"^qual\s+(?:é|e)\s+(?:a\s+)?(?:minha\s+)?lista\s+(?:de\s+)?(\w+)\s*\??\s*$", re.I
)
RE_NL_LISTA_SOZINHA = re.compile(r"^(lista|mercado|compras|pendentes)\s*$", re.I)
RE_FEITO_ID = re.compile(r"^/feito\s+(\d+)\s*$", re.I)
RE_FEITO_LIST_ID = re.compile(r"^/feito\s+(\S+)\s+(\d+)\s*$", re.I)
# Atalhos: /filme, /livro, /musica, /receita → equivalente a /list filme|livro|musica|receita <item>
RE_FILME = re.compile(r"^/filme\s+(.+)$", re.I)
RE_LIVRO = re.compile(r"^/livro\s+(.+)$", re.I)
RE_MUSICA = re.compile(r"^/musica\s+(.+)$", re.I)
RE_MUSICA_ACCENT = re.compile(r"^/música\s+(.+)$", re.I)
RE_RECEITA = re.compile(r"^/receita\s+(.+)$", re.I)
# NL: "adicione ovos bacon e queijos a listas" → list_add mercado
RE_NL_ADICIONE_LISTA = re.compile(
    r"^(?:adicione|adiciona|adicionar|coloca|coloque|colocar)\s+(.+?)\s+(?:a|à|nas?)\s+listas?\s*$",
    re.I,
)
# NL: "add lista filmes X", "add list filmes X" → list_add filme
RE_NL_ADD_LISTA_CATEGORIA = re.compile(
    r"^(?:add|adicione|adiciona)\s+listas?\s+(filmes?|livros?|m[uú]sicas?|receitas?)\s+(.+)$",
    re.I,
)
# NL: "coloca/põe/anota X na lista", "põe leite na lista"
RE_NL_POR_LISTA = re.compile(
    r"^(?:coloca|coloque|p[oô]e|põe|anota|anotar|inclui|incluir|marca)\s+(.+?)\s+(?:na|no|à|a)\s+(?:lista|listas)\s*$",
    re.I,
)
# NL: "lembra de comprar X", "não esqueças de comprar X" → list_add mercado
RE_NL_LEMBRA_COMPRAR = re.compile(
    r"^(?:lembra[- ]?me\s+de\s+comprar|n[aã]o\s+esque[cç]as?\s+de\s+comprar|lembra\s+de\s+comprar)\s+(.+)$",
    re.I,
)
# NL: "filme/livro para ver: X" ou "quero ver filme X"
RE_NL_FILME_LIVRO_VER = re.compile(
    r"^(?:(?:filme|livro)\s+para\s+(?:ver|ler)\s*:\s*|quero\s+(?:ver|ler)\s+(?:o\s+)?(?:filme|livro)\s+)(.+)$",
    re.I,
)

# Normalizar categoria para singular (list_name)
_CATEGORY_TO_LIST = {
    "filme": "filme", "filmes": "filme",
    "livro": "livro", "livros": "livro",
    "musica": "musica", "musicas": "musica", "música": "musica", "músicas": "musica",
    "receita": "receita", "receitas": "receita",
}

RE_DEPOIS_DE = re.compile(
    r"(?:depois\s+de\s+|depois\s+do\s+|ap[só]s\s+(?:o\s+)?)([A-Za-z]{2,4})\b",
    re.I,
)


def _extract_depends_on(text: str) -> tuple[str | None, str]:
    """Extrai 'depois de X' / 'após X'. Retorna (job_id, texto sem a expressão)."""
    if not text or not text.strip():
        return None, text
    t = text.strip()
    m = RE_DEPOIS_DE.search(t)
    if not m:
        return None, t
    job_id = (m.group(1) or "").strip().upper()
    if not job_id:
        return None, t
    clean = (t[: m.start()] + t[m.end() :]).strip()
    clean = re.sub(r"^[,;]\s*", "", clean)
    clean = re.sub(r"[,;]\s*$", "", clean).strip()
    return job_id, clean


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
            depends_on, rest = _extract_depends_on(rest)
            intent = parse_lembrete_time(rest)
            intent["type"] = "lembrete"
            if depends_on:
                intent["depends_on_job_id"] = depends_on
            # "até X" = prazo: se não fizer até X, alerta e lembra 3x; sem resposta exclui
            if re.search(r"\bat[eé]\b", rest.lower()):
                intent["has_deadline"] = True
            # "a partir de 1º de julho" → start_date para cron/every
            if intent.get("cron_expr") or intent.get("every_seconds"):
                sd = extract_start_date(rest)
                if sd:
                    intent["start_date"] = sd
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

    # Linguagem natural: mostre lista mercado, lista de mercado, qual minha lista, mercado
    m = RE_NL_MOSTRE_LISTA.match(text)
    if m:
        return {"type": "list_show", "list_name": m.group(1).strip()}
    m = RE_NL_LISTA_DE.match(text)
    if m:
        return {"type": "list_show", "list_name": m.group(1).strip()}
    m = RE_NL_QUAL_LISTA.match(text)
    if m:
        return {"type": "list_show", "list_name": m.group(1).strip()}
    m = RE_NL_LISTA_SOZINHA.match(text)
    if m:
        name = m.group(1).strip()
        return {"type": "list_show", "list_name": name if name != "lista" else None}

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

    # NL: "add lista filmes X" → list_add filme
    m = RE_NL_ADD_LISTA_CATEGORIA.match(text)
    if m:
        cat = m.group(1).strip().lower()
        list_name = _CATEGORY_TO_LIST.get(cat, cat)
        item = m.group(2).strip()
        if item:
            return {"type": "list_add", "list_name": list_name, "item": item}
    # NL: "coloca X na lista" → list_add mercado (assumindo compras se não especificar)
    m = RE_NL_POR_LISTA.match(text)
    if m:
        item = m.group(1).strip()
        if item:
            return {"type": "list_add", "list_name": "mercado", "item": item}
    # NL: "lembra de comprar X" → list_add mercado
    m = RE_NL_LEMBRA_COMPRAR.match(text)
    if m:
        item = m.group(1).strip()
        if item:
            return {"type": "list_add", "list_name": "mercado", "item": item}
    # NL: "filme para ver: X", "quero ver filme X" → list_add filme ou livro
    m = RE_NL_FILME_LIVRO_VER.match(text)
    if m:
        item = m.group(1).strip()
        if item:
            list_name = "livro" if "ler" in text.lower() or "livro" in text.lower() else "filme"
            return {"type": "list_add", "list_name": list_name, "item": item}
    # NL: "adicione ovos bacon e queijos a listas" → list_add mercado (default lista de compras)
    m = RE_NL_ADICIONE_LISTA.match(text)
    if m:
        raw_items = m.group(1).strip()
        # Split por ", " e " e " → ["ovos","bacon","galinha","queijos"]
        parts = re.split(r"\s*,\s*|\s+e\s+", raw_items)
        items = [p.strip() for p in parts if p.strip()]
        if not items:
            return None
        if len(items) == 1:
            return {"type": "list_add", "list_name": "mercado", "item": items[0]}
        return {"type": "list_add", "list_name": "mercado", "items": items}

    return None
