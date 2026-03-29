"""Core parsing logic for command_parser package."""

import re
from typing import Any
from . import pt, en, es

# Dynamically build unified lists/mappings (sorted by length to avoid regex shadowing)
LEMBRETE_ALIASES_STR = "|".join(sorted(set(pt.LEMBRETE_ALIASES + en.LEMBRETE_ALIASES + es.LEMBRETE_ALIASES), key=len, reverse=True))
LISTA_ALIASES_STR = "|".join(sorted(set(pt.LISTA_ALIASES + en.LISTA_ALIASES + es.LISTA_ALIASES), key=len, reverse=True))
FEITO_ALIASES_STR = "|".join(sorted(set(pt.FEITO_ALIASES + en.FEITO_ALIASES + es.FEITO_ALIASES), key=len, reverse=True))
REMOVE_ALIASES_STR = "|".join(sorted(set(pt.REMOVE_ALIASES + en.REMOVE_ALIASES + es.REMOVE_ALIASES), key=len, reverse=True))

ALL_CATEGORIES_STR = "|".join(sorted(set(pt.CATEGORIES + en.CATEGORIES + es.CATEGORIES), key=len, reverse=True))

CATEGORY_TO_LIST = {**pt.CATEGORY_TO_LIST, **en.CATEGORY_TO_LIST, **es.CATEGORY_TO_LIST}
_REMINDER_AGENDA_WORDS_SHOW = pt.REMINDER_AGENDA_WORDS | en.REMINDER_AGENDA_WORDS | es.REMINDER_AGENDA_WORDS
_ALL_LIST_SOZINHA_WORDS_STR = "|".join(sorted(set(pt.LISTA_SOZINHA_WORDS + en.LISTA_SOZINHA_WORDS + es.LISTA_SOZINHA_WORDS), key=len, reverse=True))

# Unified NL fragments
VERBS_MOSTRE_STR = "|".join(sorted(set(pt.VERBS_MOSTRE + en.VERBS_MOSTRE + es.VERBS_MOSTRE), key=len, reverse=True))
VERBS_CRIA_STR = "|".join(sorted(set(pt.VERBS_CRIA + en.VERBS_CRIA + es.VERBS_CRIA), key=len, reverse=True))
ARTICLES_STR = "|".join(sorted(set(pt.ARTICLES + en.ARTICLES + es.ARTICLES), key=len, reverse=True))
POSSESSIVES_STR = "|".join(sorted(set(pt.POSSESSIVES + en.POSSESSIVES + es.POSSESSIVES), key=len, reverse=True))
LIST_WORDS_STR = "|".join(sorted(set(pt.LIST_WORDS + en.LIST_WORDS + es.LIST_WORDS), key=len, reverse=True))
PREPOSITIONS_OF_STR = "|".join(sorted(set(pt.PREPOSITIONS_OF + en.PREPOSITIONS_OF + es.PREPOSITIONS_OF), key=len, reverse=True))

ADICIONE_VERBS_STR = "|".join(sorted(set(pt.ADICIONE_VERBS + en.ADICIONE_VERBS + es.ADICIONE_VERBS), key=len, reverse=True))
NAS_WORDS_STR = "|".join(sorted(set(pt.NAS_WORDS + en.NAS_WORDS + es.NAS_WORDS), key=len, reverse=True))
POR_LISTA_VERBS_STR = "|".join(sorted(set(pt.POR_LISTA_VERBS + en.POR_LISTA_VERBS + es.POR_LISTA_VERBS), key=len, reverse=True))
NA_LISTA_WORDS_STR = "|".join(sorted(set(pt.NA_LISTA_WORDS + en.NA_LISTA_WORDS + es.NA_LISTA_WORDS), key=len, reverse=True))

ANOTA_VERBS_STR = "|".join(sorted(set(pt.ANOTA_VERBS + en.ANOTA_VERBS + es.ANOTA_VERBS), key=len, reverse=True))
TENHO_DE_WORDS_STR = "|".join(sorted(set(pt.TENHO_DE_WORDS + en.TENHO_DE_WORDS + es.TENHO_DE_WORDS), key=len, reverse=True))
MUITA_COISA_WORDS_STR = "|".join(sorted(set(pt.MUITA_COISA_WORDS + en.MUITA_COISA_WORDS + es.MUITA_COISA_WORDS), key=len, reverse=True))
LEMBRA_COMPRAR_STR = "|".join(sorted(set(pt.LEMBRA_COMPRAR_ALTS + en.LEMBRA_COMPRAR_ALTS + es.LEMBRA_COMPRAR_ALTS), key=len, reverse=True))
FILME_LIVRO_VER_STR = "|".join(sorted(set(pt.FILME_LIVRO_VER_ALTS + en.FILME_LIVRO_VER_ALTS + es.FILME_LIVRO_VER_ALTS), key=len, reverse=True))
LISTA_DOIS_PONTOS_STR = "|".join(sorted(set([pt.LISTA_DOIS_PONTOS_FRAGMENT, en.LISTA_DOIS_PONTOS_FRAGMENT, es.LISTA_DOIS_PONTOS_FRAGMENT]), key=len, reverse=True))

AGENDA_ALIASES_STR = "|".join(sorted(set(pt.REMINDER_AGENDA_WORDS | en.REMINDER_AGENDA_WORDS | es.REMINDER_AGENDA_WORDS), key=len, reverse=True))
DATA_ALIASES_STR = "|".join(sorted(set(["data", "date", "fecha"]), key=len, reverse=True))
REMIND_ME_VERBS_STR = "|".join(sorted(set(["lembrete", "reminder", "recordatorio", "recordar", "lembra", "remind", "avisa", "avisar"]), key=len, reverse=True))
PARSE_REJECT_PREFIXES = tuple(sorted(["/agenda", "/evento", "/compromisso", "/cita", "/calendar", "/tasks", "/agendas", "/eventos", "/compromissos", "/citas", "/calendario", "/calendário"], key=len, reverse=True))

DE_WORDS_STR = "|".join(sorted(set(["de", "da", "do", "das", "dos", "del", "al", "de la", "a la", "of", "from", "for", "to", "by", "con", "with", "para", "por", "in", "on", "at", "en", "sobre", "a", "as", "os", "um", "uma", "uns", "umas", "na", "no", "nas", "nos", "pela", "pelo", "la", "las", "el", "los"]), key=len, reverse=True))

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
RE_DATA = re.compile(rf"^/(?:{DATA_ALIASES_STR})\s*$", re.I)

# Unified NL patterns
RE_NL_LIST_SHOW = re.compile(
    rf"^(?:{VERBS_MOSTRE_STR}|show\s+me|me\s+d)\S*\s+"
    rf"(?:(?:{ARTICLES_STR})\s+)?(?:(?:{POSSESSIVES_STR}|ma|mon)\s+)?(?:{LIST_WORDS_STR})"
    rf"(?:\s+(?:(?:{PREPOSITIONS_OF_STR})\S*\s+)?({ALL_CATEGORIES_STR}|[\"']?[^\"'\r\n]+?[\"']?))?"
    rf"(?:\s+(.+))?\s*$",
    re.I | re.UNICODE,
)
 
AGENDA_WORDS_STR = "|".join(sorted(_REMINDER_AGENDA_WORDS_SHOW, key=len, reverse=True))
RE_NL_AGENDA_SHOW = re.compile(
    rf"^(?:{VERBS_MOSTRE_STR}|show\s+me|me\s+d)\S*\s+"
    rf"(?:(?:{ARTICLES_STR})\s+)?(?:(?:{POSSESSIVES_STR}|ma|mon)\s+)?(?:{AGENDA_WORDS_STR})\s*$",
    re.I | re.UNICODE,
)
 
RE_NL_LIST_ADD = re.compile(
    rf"^(?:{ADICIONE_VERBS_STR}|{VERBS_CRIA_STR})\S*\s+"
    rf"(?:(?:{ARTICLES_STR})\s+)?(?:(?:{POSSESSIVES_STR}|ma|mon)\s+)?(?:{LIST_WORDS_STR})\s+"
    rf"(?:(?:{PREPOSITIONS_OF_STR})\S*\s+)?"
    rf"([\"']?[^\"'\r\n]+?[\"']?)(?:\s+(.+))?$",
    re.I | re.UNICODE,
)

RE_NL_LISTA_SOZINHA = re.compile(
    rf"^(?:(?:{POSSESSIVES_STR}|my|mi|mis)\s+)?({LIST_WORDS_STR}s?|{_ALL_LIST_SOZINHA_WORDS_STR})(?:\s+(.+))?\s*$",
    re.I
)





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
    rf"^(?:{ADICIONE_VERBS_STR})\s+(.+?)\s+(?:{NAS_WORDS_STR})\s+(.+)$",
    re.I,
)
RE_NL_ADD_LISTA_CATEGORIA = re.compile(
    rf"^(?:{ADICIONE_VERBS_STR})\s+(?:listas?\s+)?({ALL_CATEGORIES_STR})\s+([^\r\n]+)$",
    re.I,
)
RE_NL_POR_LISTA = re.compile(
    rf"^(?:{POR_LISTA_VERBS_STR})\s+(.+?)\s+(?:{NA_LISTA_WORDS_STR})\s+(.+)$",
    re.I,
)
RE_NL_LISTA_DOIS_PONTOS = re.compile(rf"^(?:{LISTA_DOIS_PONTOS_STR})\s*[:\s]\s*(.+)$", re.I)
RE_NL_ANOTA = re.compile(rf"^(?:{ANOTA_VERBS_STR})\s+([^\r\n]+)$", re.I)
RE_NL_MUITA_COISA = re.compile(
    rf"^(?:hoje\s+)?tenho\s+({MUITA_COISA_WORDS_STR})(\s+para\s+fazer)?\s*[,:]\s*(.+)$",
    re.I,
)
RE_NL_HOJE_TENHO_DE = re.compile(
    rf"^(?:hoje\s+)?({TENHO_DE_WORDS_STR})\s+(.+)$",
    re.I,
)
RE_NL_LEMBRA_COMPRAR = re.compile(rf"^(?:{LEMBRA_COMPRAR_STR})\s+([^\r\n]+)$", re.I)
RE_HOJE = re.compile(rf"^/(?:hoje|hoy|today)\s*$", re.I)
RE_SEMANA = re.compile(rf"^/(?:semana|week)\s*$", re.I)
RE_AGENDA = re.compile(rf"^/(?:{AGENDA_ALIASES_STR})\s*(.*)$", re.I)
RE_NL_REMIND_ME = re.compile(
    rf"^(?:me\s+)?(?:{REMIND_ME_VERBS_STR})\S*\s+(?:de\s+)?(.+)$",
    re.I | re.UNICODE
)
RE_NL_GENERIC_LEMBRETE = re.compile(rf"^(?:{REMIND_ME_VERBS_STR})\s*[:\s]\s*(.+)$", re.I)
RE_NL_FILME_LIVRO_VER = re.compile(rf"^(?:{FILME_LIVRO_VER_STR})\s*[:\s]?\s*([^\r\n]+)$", re.I)

def _extract_list_name(full: str) -> str:
    """Extrai e limpa o nome da lista (ex: 'mercado' de 'lista de mercado' ou 'shopping' de 'shopping list')."""
    # 1. Limpeza inicial: Artigos e Possessivos (globalmente seguro)
    pattern_meta = rf"\b(?:{ARTICLES_STR}|{POSSESSIVES_STR}|ma|mon|my|mi|mis)\b"
    clean = re.sub(pattern_meta, "", full, flags=re.I | re.UNICODE).strip()
    
    # 2. Limpeza conservadora de 'Lista/List' (apenas no início ou no fim)
    pattern_list = rf"^(?:{LIST_WORDS_STR}s?)\b|\b(?:{LIST_WORDS_STR}s?)$"
    # Remove apenas uma ocorrência no início ou fim
    new_clean = re.sub(pattern_list, "", clean, count=1, flags=re.I).strip()
    if new_clean:
        clean = new_clean
    # Se ao remover 'lista' a string ficar vazia, mantemos a palavra original (limpa de artigos)

    # 3. Limpeza recursiva de preposições nas extremidades
    prev = None
    while clean != prev:
        prev = clean
        clean = re.sub(rf"^(?:{DE_WORDS_STR})\s+", "", clean, flags=re.I).strip()
        clean = re.sub(rf"\s+(?:{DE_WORDS_STR})$", "", clean, flags=re.I).strip()
    
    # 4. Colapsar espaços e normalizar
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean.lower() if clean else "mercado"

def parse(raw: str, tz_iana: str = "UTC") -> dict[str, Any] | None:
    """Parseia a mensagem. Retorna um intent dict ou None."""
    from backend.time_parse import extract_start_date, parse_lembrete_time
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None

    if text.lower().startswith(PARSE_REJECT_PREFIXES):
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
        list_name = CATEGORY_TO_LIST.get(list_name_raw, list_name_raw)
        return {"type": "list_add", "list_name": list_name, "item": m.group(2).strip()}
    m = RE_LIST_CATEGORY_ADD.match(text)
    if m:
        cat = m.group(1).strip().lower()
        list_name = CATEGORY_TO_LIST.get(cat, cat)
        return {"type": "list_add", "list_name": list_name, "item": m.group(2).strip()}
    m = RE_LIST_SHOW.match(text)
    if m:
        raw_name = m.group(1).strip().lower()
        return {"type": "list_show", "list_name": CATEGORY_TO_LIST.get(raw_name, m.group(1).strip())}
    if RE_LIST_ALL.match(text):
        return {"type": "list_show", "list_name": None}
 
    m = RE_FEITO_LIST_ID.match(text)
    if m:
        _fn = m.group(1).strip().lower()
        return {"type": "feito", "list_name": CATEGORY_TO_LIST.get(_fn, m.group(1).strip()), "item_id": int(m.group(2))}
    m = RE_FEITO_ID_ONLY.match(text)
    if m:
        return {"type": "feito", "list_name": None, "item_id": int(m.group(1))}
    m = RE_FEITO_TEXT.match(text)
    if m:
        parts = m.group(1).strip().split(None, 1)
        if len(parts) == 2:
            _fn = parts[0].strip().lower()
            return {"type": "feito", "list_name": CATEGORY_TO_LIST.get(_fn, parts[0].strip()), "item": parts[1].strip()}
        return {"type": "feito", "list_name": None, "item": m.group(1).strip()}
 
    m = RE_REMOVE_LIST_ID.match(text)
    if m:
        _rn = m.group(1).strip().lower()
        return {"type": "remove", "list_name": CATEGORY_TO_LIST.get(_rn, m.group(1).strip()), "item_id": int(m.group(2))}
    m = RE_REMOVE_ID_ONLY.match(text)
    if m:
        return {"type": "remove", "list_name": None, "item_id": int(m.group(1))}
    m = RE_REMOVE_TEXT.match(text)
    if m:
        parts = m.group(1).strip().split(None, 1)
        if len(parts) == 2:
            _rn = parts[0].strip().lower()
            return {"type": "remove", "list_name": CATEGORY_TO_LIST.get(_rn, parts[0].strip()), "item": parts[1].strip()}
        return {"type": "remove", "list_name": None, "item": m.group(1).strip()}

    if RE_HORA.match(text): return {"type": "hora"}
    if RE_DATA.match(text): return {"type": "data"}
 
    if RE_NL_AGENDA_SHOW.match(text): return {"type": "agenda"}
 
    m = RE_NL_LIST_SHOW.match(text)
    if m:
        _cat_raw = m.group(1)
        if not _cat_raw:
            return {"type": "list_show", "list_name": None}
        _name = _cat_raw.strip().lower()
        if _name in _REMINDER_AGENDA_WORDS_SHOW:
            # "mostra minha agenda" -> let handle_agenda handle it unless we add it here
            return {"type": "agenda"}
        list_name = CATEGORY_TO_LIST.get(_name, _name)
        return {"type": "list_show", "list_name": list_name}
 
    if RE_HOJE.match(text): return {"type": "hoje"}
    if RE_SEMANA.match(text): return {"type": "semana"}
    m = RE_AGENDA.match(text)
    if m: return {"type": "agenda", "query": m.group(1).strip()}
 
    m = RE_NL_LIST_ADD.match(text)
    if m:
        _name = m.group(1).strip().lower()
        if _name in _REMINDER_AGENDA_WORDS_SHOW:
            return None
        list_name = CATEGORY_TO_LIST.get(_name, _name)
        item = (m.group(2) or "").strip()
        if item:
            return {"type": "list_add", "list_name": list_name, "item": item}

    m = RE_NL_LISTA_SOZINHA.match(text)
    if m:
        p1 = m.group(1).strip().lower()
        p2 = (m.group(2) or "").strip().lower()
        # "lista mercado" -> p1="lista", p2="mercado" -> name="mercado"
        # "mercado" -> p1="mercado", p2="" -> name="mercado"
        name = p2 if p2 else p1
        list_name = CATEGORY_TO_LIST.get(name, name)
        p1_name = CATEGORY_TO_LIST.get(p1, p1)
        if p1_name in _REMINDER_AGENDA_WORDS_SHOW or list_name in _REMINDER_AGENDA_WORDS_SHOW:
            return {"type": "agenda"}
        is_generic = list_name in ("lista", "listas", "list", "lists")
        return {"type": "list_show", "list_name": None if is_generic else list_name}



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
        list_name = CATEGORY_TO_LIST.get(cat, cat)
        item = m.group(2).strip()
        if item: return {"type": "list_add", "list_name": list_name, "item": item}

    m = RE_NL_POR_LISTA.match(text)
    if m:
        item = m.group(1).strip()
        if item:
            _raw_name = m.group(2).strip()
            _name = _extract_list_name(_raw_name).lower()
            list_name = CATEGORY_TO_LIST.get(_name, _name)
            return {"type": "list_add", "list_name": list_name, "item": item}

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
            list_name = "livros" if "ler" in text.lower() or "livro" in text.lower() else "filmes"
            return {"type": "list_add", "list_name": list_name, "item": item}

    m = RE_NL_ADICIONE_LISTA.match(text)
    if m:
        raw_items = m.group(1).strip()
        _raw_name = m.group(2).strip()
        _name = _extract_list_name(_raw_name).lower()
        list_name = CATEGORY_TO_LIST.get(_name, _name)
        parts = re.split(r"\s*,\s*|\s+e\s+", raw_items)
        items = [p.strip() for p in parts if p.strip()]
        if not items: return None
        if len(items) == 1: return {"type": "list_add", "list_name": list_name, "item": items[0]}
        return {"type": "list_add", "list_name": list_name, "items": items}

    m = RE_NL_REMIND_ME.match(text)
    if m:
        return {"type": "lembrete", "msg": m.group(1).strip()}

    m = RE_NL_GENERIC_LEMBRETE.match(text)
    if m:
        return {"type": "lembrete", "msg": m.group(1).strip()}

    return None
