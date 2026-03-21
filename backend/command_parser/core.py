"""Core parsing logic for command_parser package."""

import re
from typing import Any
from . import pt, en, es

# Dynamically build unified lists/mappings
LEMBRETE_ALIASES_STR = "|".join(set(pt.LEMBRETE_ALIASES + en.LEMBRETE_ALIASES + es.LEMBRETE_ALIASES))
LISTA_ALIASES_STR = "|".join(set(pt.LISTA_ALIASES + en.LISTA_ALIASES + es.LISTA_ALIASES))
FEITO_ALIASES_STR = "|".join(set(pt.FEITO_ALIASES + en.FEITO_ALIASES + es.FEITO_ALIASES))
REMOVE_ALIASES_STR = "|".join(set(pt.REMOVE_ALIASES + en.REMOVE_ALIASES + es.REMOVE_ALIASES))

ALL_CATEGORIES_STR = "|".join(set(pt.CATEGORIES + en.CATEGORIES + es.CATEGORIES))

_CATEGORY_TO_LIST = {**pt.CATEGORY_TO_LIST, **en.CATEGORY_TO_LIST, **es.CATEGORY_TO_LIST}
_REMINDER_AGENDA_WORDS_SHOW = pt.REMINDER_AGENDA_WORDS | en.REMINDER_AGENDA_WORDS | es.REMINDER_AGENDA_WORDS

# Unified NL fragments
VERBS_MOSTRE_STR = "|".join(set(pt.VERBS_MOSTRE + en.VERBS_MOSTRE + es.VERBS_MOSTRE))
VERBS_CRIA_STR = "|".join(set(pt.VERBS_CRIA + en.VERBS_CRIA + es.VERBS_CRIA))
ARTICLES_STR = "|".join(set(pt.ARTICLES + en.ARTICLES + es.ARTICLES))
POSSESSIVES_STR = "|".join(set(pt.POSSESSIVES + en.POSSESSIVES + es.POSSESSIVES))
LIST_WORDS_STR = "|".join(set(pt.LIST_WORDS + en.LIST_WORDS + es.LIST_WORDS))
PREPOSITIONS_OF_STR = "|".join(set(pt.PREPOSITIONS_OF + en.PREPOSITIONS_OF + es.PREPOSITIONS_OF))

# Regex compilation
RE_LEMBRETE = re.compile(rf"^/(?:{LEMBRETE_ALIASES_STR})\s+([^\r\n]+)$", re.I)
RE_LIST_ADD = re.compile(rf"^/(?:{LISTA_ALIASES_STR})\s+(\S+)\s+add\s+([^\r\n]+)$", re.I)
RE_LIST_CATEGORY_ADD = re.compile(rf"^/(?:{LISTA_ALIASES_STR})\s+({ALL_CATEGORIES_STR})\s+([^\r\n]+)$", re.I)
RE_LIST_SHOW = re.compile(rf"^/(?:{LISTA_ALIASES_STR})\s+(\S+)\s*$", re.I)
RE_LIST_ALL = re.compile(rf"^/(?:{LISTA_ALIASES_STR})\s*$", re.I)

RE_FEITO_LIST_ID = re.compile(rf"^/(?:{FEITO_ALIASES_STR})\s+(\S+)\s+(\d+)\s*$", re.I)
RE_FEITO_ID_ONLY = re.compile(rf"^/(?:{FEITO_ALIASES_STR})\s+(\d+)\s*$", re.I)
RE_FEITO_TEXT = re.compile(rf"^/(?:{FEITO_ALIASES_STR})\s+(.+)$", re.I)

RE_REMOVE_LIST_ID = re.compile(rf"^/(?:{REMOVE_ALIASES_STR})\s+(\S+)\s+(\d+)\s*$", re.I)
RE_REMOVE_ID_ONLY = re.compile(rf"^/(?:{REMOVE_ALIASES_STR})\s+(\d+)\s*$", re.I)
RE_REMOVE_TEXT = re.compile(rf"^/(?:{REMOVE_ALIASES_STR})\s+(.+)$", re.I)

RE_HORA = re.compile(r"^/(?:hora|time)\s*$", re.I)
RE_DATA = re.compile(r"^/(?:data|date|fecha)\s*$", re.I)

RE_NL_LIST_ACTION = re.compile(
    rf"^(?:{VERBS_MOSTRE_STR}|{VERBS_CRIA_STR}|me\s+d)\S*\s+"
    rf"(?:(?:{ARTICLES_STR})\s+)?(?:(?:{POSSESSIVES_STR}|ma|mon)\s+)?(?:{LIST_WORDS_STR})\s+"
    rf"(?:(?:{PREPOSITIONS_OF_STR})\S*\s+)?"
    rf"([\"']?[^\"'\r\n]+?[\"']?)(?:\s+(.+))?$",
    re.I | re.UNICODE,
)
RE_NL_LISTA_SOZINHA = re.compile(rf"^(?:{'|'.join(pt.LISTA_SOZINHA_WORDS)})\s*$", re.I)

# Shortcuts
RE_FILME = re.compile(r"^/filmes?\s+([^\r\n]+)$", re.I)
RE_LIVRO = re.compile(r"^/livros?\s+([^\r\n]+)$", re.I)
RE_MUSICA = re.compile(r"^/(?:musica|m[uú]sica)s?\s+([^\r\n]+)$", re.I)
RE_SERIE = re.compile(r"^/s[ée]ries?\s+([^\r\n]+)$", re.I)
RE_JOGO = re.compile(r"^/jogos?\s+([^\r\n]+)$", re.I)
RE_RECEITA = re.compile(r"^/receita\s+([^\r\n]+)$", re.I)
RE_PELICULA = re.compile(r"^/pel[ií]culas?\s+([^\r\n]+)$", re.I)
RE_LIBRO = re.compile(r"^/libros?\s+([^\r\n]+)$", re.I)
RE_MOVIE = re.compile(r"^/movies?\s+([^\r\n]+)$", re.I)
RE_BOOK = re.compile(r"^/books?\s+([^\r\n]+)$", re.I)

RE_NL_ADICIONE_LISTA = re.compile(
    rf"^(?:{'|'.join(pt.ADICIONE_VERBS)})\s+(.+?)\s+(?:{'|'.join(pt.NAS_WORDS)})\s+listas?\s*$",
    re.I,
)
RE_NL_ADD_LISTA_CATEGORIA = re.compile(
    rf"^(?:add|adicione|adiciona|a[ñn]adir)\s+(?:listas?\s+)?({ALL_CATEGORIES_STR})\s+([^\r\n]+)$",
    re.I,
)
RE_NL_MOSTRE_LISTA_DE = re.compile(
    rf"^(?:{VERBS_MOSTRE_STR}|show\s+me)\s+"
    rf"(?:uma\s+|una\s+|a\s+|la\s+)?(?:{LIST_WORDS_STR})\s+"
    rf"(?:(?:{PREPOSITIONS_OF_STR})\s+)?"
    rf"[\"']?([^\"'\r\n]+)[\"']?(?:\s+(.+))?$",
    re.I,
)
RE_NL_POR_LISTA = re.compile(
    rf"^(?:{'|'.join(pt.POR_LISTA_VERBS)})\s+(.+?)\s+(?:{'|'.join(pt.NA_LISTA_WORDS)})\s+(?:lista|listas)\s*$",
    re.I,
)
RE_NL_LISTA_DOIS_PONTOS = re.compile(
    rf"^(?:{pt.LISTA_DOIS_PONTOS_FRAGMENT}|{en.LISTA_DOIS_PONTOS_FRAGMENT}|{es.LISTA_DOIS_PONTOS_FRAGMENT})\s*:\s*(.+)$",
    re.I,
)
RE_NL_ANOTA = re.compile(rf"^(?:{'|'.join(pt.ANOTA_VERBS)})\s+([^\r\n]+)$", re.I)
RE_NL_MUITA_COISA = re.compile(
    rf"^(?:hoje\s+)?tenho\s+({ '|'.join(pt.MUITA_COISA_WORDS) })(\s+para\s+fazer)?\s*[,:]\s*(.+)$",
    re.I,
)
RE_NL_HOJE_TENHO_DE = re.compile(
    rf"^(?:hoje\s+)?({ '|'.join(pt.TENHO_DE_WORDS) })\s+(.+)$",
    re.I,
)
RE_NL_LEMBRA_COMPRAR = re.compile(rf"^{pt.LEMBRA_COMPRAR_FRAGMENT}\s+([^\r\n]+)$", re.I)
RE_NL_FILME_LIVRO_VER = re.compile(rf"^{pt.FILME_LIVRO_VER_FRAGMENT}([^\r\n]+)$", re.I)

def parse(raw: str, tz_iana: str = "UTC") -> dict[str, Any] | None:
    """Parseia a mensagem. Retorna um intent dict ou None."""
    from backend.time_parse import extract_start_date, parse_lembrete_time
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None

    if text.lower().startswith(("/agenda", "/evento", "/compromisso", "/cita", "/calendar", "/tasks")):
        return None

    m = RE_LEMBRETE.match(text)
    if m:
        rest = m.group(1).strip()
        if rest:
            intent = parse_lembrete_time(rest, tz_iana=tz_iana)
            intent["type"] = "lembrete"
            if re.search(r"\bat[eé]\b", rest.lower()):
                intent["has_deadline"] = True
            if intent.get("cron_expr") or intent.get("every_seconds"):
                sd = extract_start_date(rest, tz_iana=tz_iana)
                if sd:
                    intent["start_date"] = sd
            return intent
        return None

    m = RE_LIST_ADD.match(text)
    if m:
        list_name_raw = m.group(1).strip().lower()
        list_name = _CATEGORY_TO_LIST.get(list_name_raw, list_name_raw)
        return {"type": "list_add", "list_name": list_name, "item": m.group(2).strip()}
    m = RE_LIST_CATEGORY_ADD.match(text)
    if m:
        cat = m.group(1).strip().lower()
        list_name = _CATEGORY_TO_LIST.get(cat, cat)
        return {"type": "list_add", "list_name": list_name, "item": m.group(2).strip()}
    m = RE_LIST_SHOW.match(text)
    if m:
        raw_name = m.group(1).strip().lower()
        return {"type": "list_show", "list_name": _CATEGORY_TO_LIST.get(raw_name, m.group(1).strip())}
    if RE_LIST_ALL.match(text):
        return {"type": "list_show", "list_name": None}

    m = RE_FEITO_LIST_ID.match(text)
    if m:
        _fn = m.group(1).strip().lower()
        return {"type": "feito", "list_name": _CATEGORY_TO_LIST.get(_fn, m.group(1).strip()), "item_id": int(m.group(2))}
    m = RE_FEITO_ID_ONLY.match(text)
    if m:
        return {"type": "feito", "list_name": None, "item_id": int(m.group(1))}
    m = RE_FEITO_TEXT.match(text)
    if m:
        parts = m.group(1).strip().split(None, 1)
        if len(parts) == 2:
            _fn = parts[0].strip().lower()
            return {"type": "feito", "list_name": _CATEGORY_TO_LIST.get(_fn, parts[0].strip()), "item": parts[1].strip()}
        return {"type": "feito", "list_name": None, "item": m.group(1).strip()}

    m = RE_REMOVE_LIST_ID.match(text)
    if m:
        _rn = m.group(1).strip().lower()
        return {"type": "remove", "list_name": _CATEGORY_TO_LIST.get(_rn, m.group(1).strip()), "item_id": int(m.group(2))}
    m = RE_REMOVE_ID_ONLY.match(text)
    if m:
        return {"type": "remove", "list_name": None, "item_id": int(m.group(1))}
    m = RE_REMOVE_TEXT.match(text)
    if m:
        parts = m.group(1).strip().split(None, 1)
        if len(parts) == 2:
            _rn = parts[0].strip().lower()
            return {"type": "remove", "list_name": _CATEGORY_TO_LIST.get(_rn, parts[0].strip()), "item": parts[1].strip()}
        return {"type": "remove", "list_name": None, "item": m.group(1).strip()}

    if RE_HORA.match(text): return {"type": "hora"}
    if RE_DATA.match(text): return {"type": "data"}

    m = RE_NL_LIST_ACTION.match(text)
    if m:
        _name = m.group(1).strip().lower()
        if _name in _REMINDER_AGENDA_WORDS_SHOW:
            return None
        list_name = _CATEGORY_TO_LIST.get(_name, _name)
        item = (m.group(2) or "").strip()
        if item:
            return {"type": "list_add", "list_name": list_name, "item": item}
        return {"type": "list_show", "list_name": list_name}

    m = RE_NL_LISTA_SOZINHA.match(text)
    if m:
        name = m.group(1).strip()
        return {"type": "list_show", "list_name": name if name != "lista" else None}

    m = RE_FILME.match(text)
    if m: return {"type": "list_add", "list_name": "filmes", "item": m.group(1).strip()}
    m = RE_LIVRO.match(text)
    if m: return {"type": "list_add", "list_name": "livros", "item": m.group(1).strip()}
    m = re.match(r"^/(?:musica|m[uú]sica)s?\s+(.+)$", text, re.I)
    if m: return {"type": "list_add", "list_name": "músicas", "item": m.group(1).strip()}
    m = RE_SERIE.match(text)
    if m: return {"type": "list_add", "list_name": "séries", "item": m.group(1).strip()}
    m = RE_JOGO.match(text)
    if m: return {"type": "list_add", "list_name": "jogos", "item": m.group(1).strip()}
    m = RE_PELICULA.match(text)
    if m: return {"type": "list_add", "list_name": "filmes", "item": m.group(1).strip()}
    m = RE_LIBRO.match(text)
    if m: return {"type": "list_add", "list_name": "livros", "item": m.group(1).strip()}
    m = RE_MOVIE.match(text)
    if m: return {"type": "list_add", "list_name": "filmes", "item": m.group(1).strip()}
    m = RE_BOOK.match(text)
    if m: return {"type": "list_add", "list_name": "livros", "item": m.group(1).strip()}
    m = RE_RECEITA.match(text)
    if m: return {"type": "list_add", "list_name": "receitas", "item": m.group(1).strip()}

    m = RE_NL_ADD_LISTA_CATEGORIA.match(text)
    if m:
        cat = m.group(1).strip().lower()
        list_name = _CATEGORY_TO_LIST.get(cat, cat)
        item = m.group(2).strip()
        if item: return {"type": "list_add", "list_name": list_name, "item": item}

    m = RE_NL_MOSTRE_LISTA_DE.match(text)
    if m:
        list_name = m.group(1).strip().lower()
        if list_name in _REMINDER_AGENDA_WORDS_SHOW: return None
        list_name = _CATEGORY_TO_LIST.get(list_name, list_name)
        return {"type": "list_show", "list_name": list_name}

    m = RE_NL_POR_LISTA.match(text)
    if m:
        item = m.group(1).strip()
        if item: return {"type": "list_add", "list_name": "mercado", "item": item}

    m = RE_NL_LISTA_DOIS_PONTOS.match(text)
    if m:
        raw_items = m.group(1).strip()
        if raw_items:
            parts = re.split(r"\s*,\s*|\s+(?:e|y|and)\s+", raw_items, flags=re.IGNORECASE)
            items = [p.strip() for p in parts if p.strip()]
            if items:
                if len(items) == 1: return {"type": "list_add", "list_name": "mercado", "item": items[0]}
                return {"type": "list_add", "list_name": "mercado", "items": items}

    m = RE_NL_ANOTA.match(text)
    if m:
        item = m.group(1).strip()
        if item: return {"type": "list_add", "list_name": "notas", "item": item}

    m = RE_NL_MUITA_COISA.match(text)
    if m:
        raw_items = (m.group(3) or "").strip()
        if raw_items:
            parts = re.split(r"\s*,\s*|\s+e\s+", raw_items)
            items = [p.strip() for p in parts if p.strip()]
            if items:
                if len(items) == 1: return {"type": "list_add", "list_name": "hoje", "item": items[0]}
                return {"type": "list_add", "list_name": "hoje", "items": items}

    m = RE_NL_HOJE_TENHO_DE.match(text)
    if m:
        raw_items = m.group(2).strip()
        if raw_items:
            parts = re.split(r"\s*,\s*|\s+e\s+", raw_items)
            items = [p.strip() for p in parts if p.strip()]
            if not items: return None
            if len(items) == 1: return None
            return {"type": "list_or_events_ambiguous", "items": items}

    m = RE_NL_LEMBRA_COMPRAR.match(text)
    if m:
        item = m.group(1).strip()
        if item: return {"type": "list_add", "list_name": "mercado", "item": item}

    m = RE_NL_FILME_LIVRO_VER.match(text)
    if m:
        item = m.group(1).strip()
        if item:
            list_name = "livro" if "ler" in text.lower() or "livro" in text.lower() else "filme"
            return {"type": "list_add", "list_name": list_name, "item": item}

    m = RE_NL_ADICIONE_LISTA.match(text)
    if m:
        raw_items = m.group(1).strip()
        parts = re.split(r"\s*,\s*|\s+e\s+", raw_items)
        items = [p.strip() for p in parts if p.strip()]
        if not items: return None
        if len(items) == 1: return {"type": "list_add", "list_name": "mercado", "item": items[0]}
        return {"type": "list_add", "list_name": "mercado", "items": items}

    return None
