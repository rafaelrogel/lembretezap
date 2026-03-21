"""Parser de comandos: /lembrete, /list, /filme. Retorna intent estruturado ou None.

Suporta lembretes pontuais e recorrentes (diário, semanal, a cada N, mensal).
Parse de tempo/recorrência em backend.time_parse.
"""

import re
from typing import Any

from backend.time_parse import extract_start_date, parse_lembrete_time

# Padrões com aliases internacionais (PT, ES, EN)
RE_LEMBRETE = re.compile(r"^/(?:lembrete|reminder|recordatorio)\s+([^\r\n]+)$", re.I)
RE_LIST_ADD = re.compile(r"^/(?:list|lista)\s+(\S+)\s+add\s+([^\r\n]+)$", re.I)
# /list filme|livro|musica|receita|notas|nota|sites|site|links|link <item> (categorias; sem "add")
RE_LIST_CATEGORY_ADD = re.compile(
    r"^/(?:list|lista)\s+(filme|filmes|livro|livros|musica|musicas|m[uú]sicas?|receita|receitas|recipe|recipes|receta|recetas|notas?|sites?|links?|pel[ií]culas?|libros?|movies?|books?)\s+([^\r\n]+)$",
    re.I,
)
RE_LIST_SHOW = re.compile(r"^/(?:list|lista)\s+(\S+)\s*$", re.I)
RE_LIST_ALL = re.compile(r"^/(?:list|lista)\s*$", re.I)
RE_FEITO_LIST_ID = re.compile(r"^/(?:feito|done|hecho)\s+(\S+)\s+(\d+)\s*$", re.I)
RE_FEITO_ID_ONLY = re.compile(r"^/(?:feito|done|hecho)\s+(\d+)\s*$", re.I)
RE_FEITO_TEXT = re.compile(r"^/(?:feito|done|hecho)\s+(.+)$", re.I)
# /remove
RE_REMOVE_LIST_ID = re.compile(r"^/(?:remove|delete|quitar|borrar)\s+(\S+)\s+(\d+)\s*$", re.I)
RE_REMOVE_ID_ONLY = re.compile(r"^/(?:remove|delete|quitar|borrar)\s+(\d+)\s*$", re.I)
RE_REMOVE_TEXT = re.compile(r"^/(?:remove|delete|quitar|borrar)\s+(.+)$", re.I)

RE_HORA = re.compile(r"^/(?:hora|time)\s*$", re.I)
RE_DATA = re.compile(r"^/(?:data|date|fecha)\s*$", re.I)
# Linguagem natural: mostre lista X, lista de X, minha lista X, qual lista, mercado, compras
RE_NL_MOSTRE_LISTA = re.compile(
    r"^(?:mostr(?:e|ar)|ver|listar|mostra)\s+(?:a\s+)?(?:minha\s+)?lista\s+(?:de\s+)?[\"']?(\w+)[\"']?\s*$", re.I
)
RE_NL_LISTA_DE = re.compile(r"^lista\s+(?:de\s+)?[\"']?(\w+)[\"']?\s*\??\s*$", re.I)
RE_NL_QUAL_LISTA = re.compile(
    r"^qual\s+(?:é|e)\s+(?:a\s+)?(?:minha\s+)?lista\s+(?:de\s+)?[\"']?(\w+)[\"']?\s*\??\s*$", re.I
)
RE_NL_LISTA_SOZINHA = re.compile(r"^(lista|mercado|compras|pendentes)\s*$", re.I)
# Atalhos: /filme, /livro, /musica, /receita, /nota, /site → equivalente a /list <categoria> <item>
RE_FILME = re.compile(r"^/filmes?\s+([^\r\n]+)$", re.I)
RE_LIVRO = re.compile(r"^/livros?\s+([^\r\n]+)$", re.I)
RE_MUSICA = re.compile(r"^/(?:musica|m[uú]sica)s?\s+([^\r\n]+)$", re.I)
RE_RECEITA = re.compile(r"^/receita\s+([^\r\n]+)$", re.I)
# Atalhos ES/EN
RE_PELICULA = re.compile(r"^/pel[ií]culas?\s+([^\r\n]+)$", re.I)
RE_LIBRO = re.compile(r"^/libros?\s+([^\r\n]+)$", re.I)
RE_MOVIE = re.compile(r"^/movies?\s+([^\r\n]+)$", re.I)
RE_BOOK = re.compile(r"^/books?\s+([^\r\n]+)$", re.I)
# NL: "adicione ovos bacon e queijos a listas" → list_add mercado
RE_NL_ADICIONE_LISTA = re.compile(
    r"^(?:adicione|adiciona|adicionar|coloca|coloque|colocar)\s+(.+?)\s+(?:a|à|nas?)\s+listas?\s*$",
    re.I,
)
# NL: "add lista filmes X", "add list filmes X" → list_add filme
RE_NL_ADD_LISTA_CATEGORIA = re.compile(
    r"^(?:add|adicione|adiciona|a[ñn]adir)\s+(?:listas?\s+)?(filmes?|livros?|m[uú]sicas?|receitas?|notas?|sites?|links?|pel[ií]culas?|libros?|movies?|books?)\s+([^\r\n]+)$",
    re.I,
)
# PT: cria, crie, faça, faz, me dê, me de, de-me, dê-me
# ES: crea, crear, haz, dame
# EN: create, make, give me
RE_NL_CRIA_LISTA_DE = re.compile(
    r"^(?:cria|crie|faça|faz|me\s+d[êe]|de-me|dê-me"
    r"|crea|crear|haz|dame"
    r"|create|make|give\s+me)\s+"
    r"(?:uma\s+|una\s+|a\s+)?(?:lista|list)\s+(?:de\s+|of\s+)?[\"']?(\w+)[\"']?(?:\s+(.+))?$",
    re.I,
)
# Verbos de visualização: mostre, mostra, exiba, muéstrame, muestra, exhibe, show me, show, display
RE_NL_MOSTRE_LISTA_DE = re.compile(
    r"^(?:mostre|mostra|exiba|mu[eé]strame|muestra|exhibe|show\s+me|show|display)\s+"
    r"(?:uma\s+|una\s+|a\s+)?(?:lista|list)\s+(?:de\s+|of\s+)?[\"']?(\w+)[\"']?(?:\s+(.+))?$",
    re.I,
)
# NL: "coloca/põe/anota X na lista", "põe leite na lista" → list_add mercado
RE_NL_POR_LISTA = re.compile(
    r"^(?:coloca|coloque|p[oô]e|põe|anota|anotar|inclui|incluir|marca)\s+(.+?)\s+(?:na|no|à|a)\s+(?:lista|listas)\s*$",
    re.I,
)
# NL (4 idiomas): "coloca na lista: X", "adiciona à lista: X", "pon en la lista: X", "add to list: X"
# PT-BR/PT-PT: coloca/adiciona/põe na lista: X
# ES: pon/añade/agrega en la lista: X
# EN: add/put to the list: X
RE_NL_LISTA_DOIS_PONTOS = re.compile(
    r"^(?:"
    # PT-BR/PT-PT
    r"(?:coloca|coloque|p[oô]e|põe|adiciona|adicione|inclui|incluir)\s+(?:na|à|a)\s+lista"
    r"|(?:adiciona|adicione|coloca|coloque)\s+(?:à|a|na)\s+lista"
    # ES
    r"|(?:pon|pone|a[ñn]ade|a[ñn]adir|agrega|agregar)\s+(?:en\s+la|a\s+la)\s+lista"
    # EN
    r"|(?:add|put)\s+(?:to\s+(?:the\s+)?|on\s+(?:the\s+)?)?list"
    r")\s*:\s*(.+)$",
    re.I,
)
# NL: "anota X" / "anotar X" (sem "na lista") → list_add notas
RE_NL_ANOTA = re.compile(r"^(?:anota|anotar)\s+([^\r\n]+)$", re.I)
# NL: "hoje tenho muita coisa para fazer, X, Y e Z" → sempre list_add hoje (to-do)
RE_NL_MUITA_COISA = re.compile(
    r"^(?:hoje\s+)?tenho\s+(muita\s+coisa|v[aá]rias\s+coisas|v[aá]rias\s+tarefas)(\s+para\s+fazer)?\s*[,:]\s*(.+)$",
    re.I,
)
# NL: "tenho de X, Y e Z" — 1 item = evento (return None); 2+ itens = ambíguo (list_or_events_ambiguous)
RE_NL_HOJE_TENHO_DE = re.compile(
    r"^(?:hoje\s+)?tenho\s+(?:de|que)\s+(.+)$",
    re.I,
)
# NL: "lembra de comprar X", "não esqueças de comprar X" → list_add mercado
RE_NL_LEMBRA_COMPRAR = re.compile(
    r"^(?:lembra[- ]?me\s+de\s+comprar|n[aã]o\s+esque[cç]as?\s+de\s+comprar|lembra\s+de\s+comprar)\s+([^\r\n]+)$",
    re.I,
)
# NL: "filme/livro para ver: X" ou "quero ver filme X"
RE_NL_FILME_LIVRO_VER = re.compile(
    r"^(?:(?:filme|livro)\s+para\s+(?:ver|ler)\s*:\s*|quero\s+(?:ver|ler)\s+(?:o\s+)?(?:filme|livro)\s+)([^\r\n]+)$",
    re.I,
)

# Normalizar categoria para singular (list_name). PT + EN + ES para mesma lógica em todos os idiomas.
# Qualquer outro nome (ex.: ingredientes, tarefas) fica como está — lista com esse nome.
_CATEGORY_TO_LIST = {
    # PT
    "filme": "filme", "filmes": "filme",
    "livro": "livro", "livros": "livro",
    "musica": "musica", "musicas": "musica", "música": "musica", "músicas": "musica",
    "receita": "receita", "receitas": "receita",
    # "compras" e "mercado" são aliases fortes mas o usuário pode querer listas separadas.
    # Vamos manter o mapeamento mas o Tool vai tentar encontrar a lista exata primeiro.
    "mercado": "mercado", "supermercado": "mercado",
    "nota": "notas", "notas": "notas",
    "site": "sites", "sites": "sites",
    "link": "sites", "links": "sites",
    # EN
    "movie": "filme", "movies": "filme", "film": "filme", "films": "filme",
    "book": "livro", "books": "livro",
    "music": "musica", "song": "musica", "songs": "musica",
    "recipe": "receita", "recipes": "receita",
    "note": "notas", "notes": "notas",
    "shopping": "mercado", "grocery": "mercado", "groceries": "mercado",
    # ES
    "película": "filme", "películas": "filme", "pelicula": "filme", "peliculas": "filme",
    "libro": "livro", "libros": "livro",
    "receta": "receita", "recetas": "receita",
    "notas": "notas",
}

def parse(raw: str, tz_iana: str = "UTC") -> dict[str, Any] | None:
    """Parseia a mensagem. Retorna um intent dict ou None.
    tz_iana: fuso do utilizador para lembretes (hoje/amanhã/datas); ex. America/Sao_Paulo."""
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None

    # Guard: comandos de agenda/evento não são listas
    if text.lower().startswith(("/agenda", "/evento", "/compromisso", "/cita", "/calendar", "/tasks")):
        return None

    m = RE_LEMBRETE.match(text)
    if m:
        rest = m.group(1).strip()
        if rest:
            intent = parse_lembrete_time(rest, tz_iana=tz_iana)
            intent["type"] = "lembrete"
            # Encadeamento ("depois de X") é tratado pelo LLM a partir de áudio/texto natural
            # "até X" = prazo: se não fizer até X, alerta e lembra 3x; sem resposta exclui
            if re.search(r"\bat[eé]\b", rest.lower()):
                intent["has_deadline"] = True
            # "a partir de 1º de julho" → start_date para cron/every
            if intent.get("cron_expr") or intent.get("every_seconds"):
                sd = extract_start_date(rest, tz_iana=tz_iana)
                if sd:
                    intent["start_date"] = sd
            return intent
        return None

    m = RE_LIST_ADD.match(text)
    if m:
        list_name_raw = m.group(1).strip().lower()
        # Normalizar nome da lista (compras/shopping → mercado, etc.)
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

    # /feito
    m = RE_FEITO_LIST_ID.match(text)
    if m:
        _fn = m.group(1).strip().lower()
        return {"type": "feito", "list_name": _CATEGORY_TO_LIST.get(_fn, m.group(1).strip()), "item_id": int(m.group(2))}
    m = RE_FEITO_ID_ONLY.match(text)
    if m:
        return {"type": "feito", "list_name": None, "item_id": int(m.group(1))}
    m = RE_FEITO_TEXT.match(text)
    if m:
        # Tenta extrair [lista] [item_text]
        parts = m.group(1).strip().split(None, 1)
        if len(parts) == 2:
            _fn = parts[0].strip().lower()
            return {"type": "feito", "list_name": _CATEGORY_TO_LIST.get(_fn, parts[0].strip()), "item": parts[1].strip()}
        return {"type": "feito", "list_name": None, "item": m.group(1).strip()}

    # /remove
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

    # /hora e /data
    if RE_HORA.match(text):
        return {"type": "hora"}
    if RE_DATA.match(text):
        return {"type": "data"}

    # Linguagem natural: mostre lista mercado, lista de mercado, qual minha lista, mercado
    # Guard partilhado: palavras de lembretes/agenda não são nomes de lista
    _REMINDER_AGENDA_WORDS_SHOW = {
        "lembretes", "lembrete", "agenda", "agendas", "compromissos",
        "compromisso", "eventos", "evento", "tarefas", "tarefa",
        "reminders", "reminder", "calendar", "tasks", "task",
        "recordatorios", "recordatorio",
    }
    m = RE_NL_MOSTRE_LISTA.match(text)
    if m:
        _name = m.group(1).strip().lower()
        if _name in _REMINDER_AGENDA_WORDS_SHOW:
            return None  # Deixa o LLM tratar como consulta de agenda/lembretes
        return {"type": "list_show", "list_name": _CATEGORY_TO_LIST.get(_name, _name)}
    m = RE_NL_LISTA_DE.match(text)
    if m:
        _name = m.group(1).strip().lower()
        if _name in _REMINDER_AGENDA_WORDS_SHOW:
            return None
        return {"type": "list_show", "list_name": _CATEGORY_TO_LIST.get(_name, _name)}
    m = RE_NL_QUAL_LISTA.match(text)
    if m:
        _name = m.group(1).strip().lower()
        if _name in _REMINDER_AGENDA_WORDS_SHOW:
            return None
        return {"type": "list_show", "list_name": _CATEGORY_TO_LIST.get(_name, _name)}
    m = RE_NL_LISTA_SOZINHA.match(text)
    if m:
        name = m.group(1).strip()
        return {"type": "list_show", "list_name": name if name != "lista" else None}


    # Atalhos: /filme X, /livro X, /musica X → list_add (dentro de /list)
    m = RE_FILME.match(text)
    if m:
        return {"type": "list_add", "list_name": "filme", "item": m.group(1).strip()}
    m = RE_LIVRO.match(text)
    if m:
        return {"type": "list_add", "list_name": "livro", "item": m.group(1).strip()}
    m = re.match(r"^/(?:musica|m[uú]sica)s?\s+(.+)$", text, re.I)
    if m:
        return {"type": "list_add", "list_name": "musica", "item": m.group(1).strip()}
    
    # ES/EN Shortcuts
    m = RE_PELICULA.match(text)
    if m:
        return {"type": "list_add", "list_name": "filme", "item": m.group(1).strip()}
    m = RE_LIBRO.match(text)
    if m:
        return {"type": "list_add", "list_name": "livro", "item": m.group(1).strip()}
    m = RE_MOVIE.match(text)
    if m:
        return {"type": "list_add", "list_name": "filme", "item": m.group(1).strip()}
    m = RE_BOOK.match(text)
    if m:
        return {"type": "list_add", "list_name": "livro", "item": m.group(1).strip()}
    
    # Receita continua como lista por enquanto (ou pode mover para event se quiser)
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
    # NL: "cria uma lista de livros do lovecraft para eu comprar" ou "cria uma lista de livros" → list_add
    m = RE_NL_CRIA_LISTA_DE.match(text)
    if m:
        list_name = m.group(1).strip().lower()
        # Guard: palavras de lembretes/agenda nunca devem ser tratadas como nomes de lista
        _REMINDER_AGENDA_WORDS = {
            "lembretes", "lembrete", "agenda", "agendas", "compromissos",
            "compromisso", "eventos", "evento", "tarefas", "tarefa",
            "reminders", "reminder", "calendar", "tasks", "task",
            "recordatorios", "recordatorio",
        }
        if list_name in _REMINDER_AGENDA_WORDS:
            return None
        list_name = _CATEGORY_TO_LIST.get(list_name, list_name)
        item = (m.group(2) or "").strip()
        if item:
            return {"type": "list_add", "list_name": list_name, "item": item}
        return {"type": "list_show", "list_name": list_name}

    m = RE_NL_MOSTRE_LISTA_DE.match(text)
    if m:
        list_name = m.group(1).strip().lower()
        if list_name in _REMINDER_AGENDA_WORDS_SHOW:
            return None
        list_name = _CATEGORY_TO_LIST.get(list_name, list_name)
        # Se tem o resto (m.group(2)), pode ser um pedido de busca
        # Ex: "mostre lista de filmes de David Lynch"
        # Devolver show por enquanto, o Router vai tentar o search_handler primeiro se detectarmos busca.
        return {"type": "list_show", "list_name": list_name}

    # NL: "coloca X na lista" → list_add mercado (assumindo compras se não especificar)
    m = RE_NL_POR_LISTA.match(text)
    if m:
        item = m.group(1).strip()
        if item:
            return {"type": "list_add", "list_name": "mercado", "item": item}
    # NL (4 idiomas): "coloca na lista: X, Y, Z" → list_add mercado
    m = RE_NL_LISTA_DOIS_PONTOS.match(text)
    if m:
        raw_items = m.group(1).strip()
        if raw_items:
            # Split por vírgula e conectores (e/y/and)
            parts = re.split(r"\s*,\s*|\s+(?:e|y|and)\s+", raw_items, flags=re.IGNORECASE)
            items = [p.strip() for p in parts if p.strip()]
            if items:
                if len(items) == 1:
                    return {"type": "list_add", "list_name": "mercado", "item": items[0]}
                return {"type": "list_add", "list_name": "mercado", "items": items}
    # NL: "anota X" / "anotar X" (sem "na lista") → list_add notas
    m = RE_NL_ANOTA.match(text)
    if m:
        item = m.group(1).strip()
        if item:
            return {"type": "list_add", "list_name": "notas", "item": item}
    # NL: "hoje tenho muita coisa para fazer, X, Y e Z" → sempre lista de afazeres (to-do)
    m = RE_NL_MUITA_COISA.match(text)
    if m:
        raw_items = (m.group(3) or "").strip()
        if raw_items:
            parts = re.split(r"\s*,\s*|\s+e\s+", raw_items)
            items = [p.strip() for p in parts if p.strip()]
            if items:
                if len(items) == 1:
                    return {"type": "list_add", "list_name": "hoje", "item": items[0]}
                return {"type": "list_add", "list_name": "hoje", "items": items}
    # NL: "tenho de X" (1 item) = evento/lembrete → None para fluxo de lembrete; "tenho de X, Y" (2+) = ambíguo
    m = RE_NL_HOJE_TENHO_DE.match(text)
    if m:
        raw_items = m.group(1).strip()
        if raw_items:
            parts = re.split(r"\s*,\s*|\s+e\s+", raw_items)
            items = [p.strip() for p in parts if p.strip()]
            if not items:
                return None
            if len(items) == 1:
                return None  # evento único → deixa para /lembrete ou LLM
            return {"type": "list_or_events_ambiguous", "items": items}
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
