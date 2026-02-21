"""Parser de comandos: /lembrete, /list, /filme. Retorna intent estruturado ou None.

Suporta lembretes pontuais e recorrentes (diário, semanal, a cada N, mensal).
Parse de tempo/recorrência em backend.time_parse.
"""

import re
from typing import Any

from backend.time_parse import extract_start_date, parse_lembrete_time

# Padrões
RE_LEMBRETE = re.compile(r"^/lembrete\s+(.+)$", re.I)
RE_LIST_ADD = re.compile(r"^/list\s+(\S+)\s+add\s+(.+)$", re.I)
# /list filme|livro|musica|receita|notas|nota|sites|site|links|link <item> (categorias; sem "add")
RE_LIST_CATEGORY_ADD = re.compile(
    r"^/list\s+(filme|filmes|livro|livros|musica|musicas|m[uú]sicas?|receita|receitas|notas?|sites?|links?)\s+(.+)$",
    re.I,
)
RE_LIST_SHOW = re.compile(r"^/list\s+(\S+)\s*$", re.I)
RE_LIST_ALL = re.compile(r"^/list\s*$", re.I)
RE_FEITO_ID_ONLY = re.compile(r"^/feito\s+(\d+)\s*$", re.I)
# /remove
RE_REMOVE_LIST_ID = re.compile(r"^/remove\s+(\S+)\s+(\d+)\s*$", re.I)
RE_REMOVE_ID_ONLY = re.compile(r"^/remove\s+(\d+)\s*$", re.I)

RE_HORA = re.compile(r"^/hora\s*$", re.I)
RE_DATA = re.compile(r"^/data\s*$", re.I)
RE_EVENTO = re.compile(r"^/evento\s+(.+)$", re.I)
# Linguagem natural: mostre lista X, lista de X, minha lista X, qual lista, mercado, compras
RE_NL_MOSTRE_LISTA = re.compile(
    r"^(?:mostr(?:e|ar)|ver|listar|mostra)\s+(?:a\s+)?(?:minha\s+)?lista\s+(?:de\s+)?(\w+)\s*$", re.I
)
RE_NL_LISTA_DE = re.compile(r"^lista\s+(?:de\s+)?(\w+)\s*\??\s*$", re.I)
RE_NL_QUAL_LISTA = re.compile(
    r"^qual\s+(?:é|e)\s+(?:a\s+)?(?:minha\s+)?lista\s+(?:de\s+)?(\w+)\s*\??\s*$", re.I
)
RE_NL_LISTA_SOZINHA = re.compile(r"^(lista|mercado|compras|pendentes)\s*$", re.I)
# Atalhos: /filme, /livro, /musica, /receita, /nota, /site → equivalente a /list <categoria> <item>
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
    r"^(?:add|adicione|adiciona)\s+listas?\s+(filmes?|livros?|m[uú]sicas?|receitas?|notas?|sites?|links?)\s+(.+)$",
    re.I,
)
# NL: "cria/faça/mostre uma lista de X ..." (PT) + equivalentes ES/EN → list_add
# PT: cria, crie, faça, faz, me dê, me de, de-me, dê-me, mostre, mostra, exiba
# ES: crea, crear, haz, dame, muéstrame, muestra, exhibe
# EN: create, make, give me, show me, show, display
# Último grupo opcional: "lista de livros" sem resto → item vazio (handler usa placeholder)
RE_NL_CRIA_LISTA_DE = re.compile(
    r"^(?:cria|crie|faça|faz|me\s+d[êe]|de-me|dê-me|mostre|mostra|exiba"
    r"|crea|crear|haz|dame|muéstrame|muestra|exhibe"
    r"|create|make|give\s+me|show\s+me|show|display)\s+"
    r"(?:uma\s+|una\s+|a\s+)?(?:lista|list)\s+(?:de\s+|of\s+)?(\w+)(?:\s+(.+))?$",
    re.I,
)
# NL: "coloca/põe/anota X na lista", "põe leite na lista" → list_add mercado
RE_NL_POR_LISTA = re.compile(
    r"^(?:coloca|coloque|p[oô]e|põe|anota|anotar|inclui|incluir|marca)\s+(.+?)\s+(?:na|no|à|a)\s+(?:lista|listas)\s*$",
    re.I,
)
# NL: "anota X" / "anotar X" (sem "na lista") → list_add notas
RE_NL_ANOTA = re.compile(r"^(?:anota|anotar)\s+(.+)$", re.I)
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
    r"^(?:lembra[- ]?me\s+de\s+comprar|n[aã]o\s+esque[cç]as?\s+de\s+comprar|lembra\s+de\s+comprar)\s+(.+)$",
    re.I,
)
# NL: "filme/livro para ver: X" ou "quero ver filme X"
RE_NL_FILME_LIVRO_VER = re.compile(
    r"^(?:(?:filme|livro)\s+para\s+(?:ver|ler)\s*:\s*|quero\s+(?:ver|ler)\s+(?:o\s+)?(?:filme|livro)\s+)(.+)$",
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
    "compras": "mercado", "mercado": "mercado",
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

    # /feito
    m = RE_FEITO_LIST_ID.match(text)
    if m:
        return {"type": "feito", "list_name": m.group(1).strip(), "item_id": int(m.group(2))}
    m = RE_FEITO_ID_ONLY.match(text)
    if m:
        return {"type": "feito", "list_name": None, "item_id": int(m.group(1))}

    # /remove
    m = RE_REMOVE_LIST_ID.match(text)
    if m:
        return {"type": "remove", "list_name": m.group(1).strip(), "item_id": int(m.group(2))}
    m = RE_REMOVE_ID_ONLY.match(text)
    if m:
        return {"type": "remove", "list_name": None, "item_id": int(m.group(1))}

    # /hora e /data
    if RE_HORA.match(text):
        return {"type": "hora"}
    if RE_DATA.match(text):
        return {"type": "data"}

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

    # Atalhos: /filme X, /livro X, /musica X, /receita X, /nota X, /site X → list_add (tudo dentro de /list)
    # Filme, Livro, Musica agora são Eventos (EventTool)
    m = RE_EVENTO.match(text)
    if m:
        return {"type": "event_add", "event_type": "evento", "name": m.group(1).strip()}
    m = RE_FILME.match(text)
    if m:
        return {"type": "event_add", "event_type": "filme", "name": m.group(1).strip()}
    m = RE_LIVRO.match(text)
    if m:
        return {"type": "event_add", "event_type": "livro", "name": m.group(1).strip()}
    m = RE_MUSICA.match(text) or RE_MUSICA_ACCENT.match(text)
    if m:
        return {"type": "event_add", "event_type": "musica", "name": m.group(1).strip()}
    
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
        list_name = _CATEGORY_TO_LIST.get(list_name, list_name)
        item = (m.group(2) or "").strip()
        if item:  # Só registra se tiver item concreto; sem item → LLM pergunta o que adicionar
            return {"type": "list_add", "list_name": list_name, "item": item}
    # NL: "coloca X na lista" → list_add mercado (assumindo compras se não especificar)
    m = RE_NL_POR_LISTA.match(text)
    if m:
        item = m.group(1).strip()
        if item:
            return {"type": "list_add", "list_name": "mercado", "item": item}
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
