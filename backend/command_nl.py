"""Normalização de linguagem natural para comandos com barra.

Cada comando /xyz pode ser invocado por frases em NL (ex.: "ajuda" → /help).
Usado por handlers e views para aceitar NL além do comando explícito.
"""

import re
import unicodedata


def _normalize_lower(text: str) -> str:
    """Lowercase e normaliza para comparação (remove acentos comuns pt)."""
    if not text:
        return text
    t = text.lower().strip()
    # NFD + remove combining (ç, á, ã, etc. → c, a, a)
    nfd = unicodedata.normalize("NFD", t)
    t = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    # Fallback: substituições comuns para pt
    for old, new in [("ç", "c"), ("ã", "a"), ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")]:
        t = t.replace(old, new)
    return t


def normalize_nl_to_command(content: str) -> str:
    """
    Se a mensagem for linguagem natural para um comando conhecido, devolve o equivalente com barra.
    Caso contrário devolve content inalterado.
    """
    if not content or not isinstance(content, str):
        return content
    t = content.strip()
    if not t or t.startswith("/"):
        return content
    lower = t.lower()

    # Ajuda / Help
    if lower in ("ajuda", "ayuda", "help", "comandos", "comando"):
        return "/help"
    if re.match(
        r"^(quais?\s+os?\s+comandos?|o\s+que\s+(você|voce|faz)|como\s+usar|lista\s+de\s+comandos)\s*$",
        lower,
    ):
        return "/help"

    # Start / Início
    lower_ascii = _normalize_lower(t)
    if lower_ascii in ("comecar", "inicio", "iniciar", "begin", "start"):
        return "/start"
    if re.match(r"^quero\s+comecar\s*$", lower_ascii):
        return "/start"
    # Fallback: formas com acento (encoding variável): início, começar
    if re.match(r"^in[ií]cio\s*$", lower) or re.match(r"^come.{1,2}ar\s*$", lower):
        if len(lower.strip()) <= 8:
            return "/start"

    # Pendente
    if lower in ("pendente", "pendentes"):
        return "/pendente"
    if re.match(
        r"^(o\s+que\s+est[aá]\s+pendente|tarefas?\s+pendentes?|mostrar\s+pendentes?)\s*$",
        lower,
    ):
        return "/pendente"

    # Stop / Parar
    if lower in ("parar", "pausar", "stop"):
        return "/stop"
    if re.match(
        r"^(parar\s+mensagens?|pausar\s+mensagens?|n[aã]o\s+quero\s+mais\s+receber)\s*$",
        lower,
    ):
        return "/stop"

    # Add: "adicione X", "adiciona X" (sem "lista"/"listas") → /add mercado X
    m = re.match(r"^(adicione|adiciona|adicionar|add|anyadir|anadir)\s+(.+)$", lower_ascii)
    if m:
        rest = m.group(2).strip()
        # Se contiver keywords de lembrete/agenda, NÃO deve ser interceptado pelo comando /add (lista)
        reminder_kws = {"lembrete", "reminder", "reunion", "cita", "avisar", "avisa", "avisame", "recordar", "recuerdame"}
        has_reminder_intent = any(kw in lower_ascii for kw in reminder_kws)
        
        if rest and not has_reminder_intent and "lista" not in lower_ascii and "listas" not in lower_ascii:
            return f"/add {rest}"

    # Recorrente: "lembrete recorrente X" ou "todo dia X" / "toda semana X"
    m = re.match(r"^lembrete\s+recorrente\s+(.+)$", lower)
    if m and m.group(1).strip():
        return f"/recorrente {m.group(1).strip()}"
    m = re.match(r"^(todo\s+dia|toda\s+semana|todos\s+os\s+dias|toda\s+(?:segunda|terça|quarta|quinta|sexta|sábado|domingo)|cada\s+\d+\s+(?:dias|horas|minutos|semanas))\s+(.+)$", lower)
    if m and m.group(2).strip():
        return f"/recorrente {lower}"

    # Hoje / Semana / Agenda (views)
    if lower in ("hoje", "today", "hoy"):
        return "/hoje"
    if re.match(r"^(o\s+que\s+tenho\s+hoje|tarefas?\s+de\s+hoje|what\s+is\s+on\s+my\s+agenda\s+today|what\s+do\s+i\s+have\s+today|qu[eé]\s+tengo\s+hoy)\s*$", lower):
        return "/hoje"
    if lower in ("semana", "week"):
        return "/semana"
    if re.match(r"^(esta\s+semana|this\s+week|esta\s+semana)\s*$", lower):
        return "/semana"
    if lower == "agenda":
        return "/agenda"
    # "agenda 21 de março", "agenda de amanhã", "agenda desta semana", etc.
    m = re.match(r"^agenda\s+(.+)$", lower)
    if m and m.group(1).strip():
        return f"/agenda {m.group(1).strip()}"
    if re.match(r"^(minha\s+agenda|o\s+que\s+tenho\s+agendado|what\s+is\s+on\s+my\s+agenda|mi\s+agenda|my\s+agenda)\s*(.*)$", lower):
        m = re.match(r"^(minha\s+agenda|o\s+que\s+tenho\s+agendado|what\s+is\s+on\s+my\s+agenda|mi\s+agenda|my\s+agenda)\s*(.*)$", lower)
        suffix = m.group(2).strip()
        if suffix:
            return f"/agenda {suffix}"
        return "/agenda"
    # Agenda commands in PT, ES, EN
    # covers: mostre minha agenda, show my calendar, ver el calendario, etc.
    m = re.match(
        r"^(liste|listar|mostre|mostrar|mostra|exiba|exibir|ver|show|display|view|muestra|mostrarme|muestrame)\s+"
        r"(?:(?:minha?|meu|my|mi|meus|mis|the|a|as|os|el|la|las|los|an?)\s+)?"
        r"(agendas?|calend[aá]rios?|calendars?|schedules?|eventos?|events?|plan(?:ning|er)?)\s*(.*)$",
        lower
    )
    if m:
        suffix = m.group(3).strip()
        if suffix:
            return f"/agenda {suffix}"
        return "/agenda"

    # Timeline
    if lower in ("timeline", "cronologia", "linha do tempo"):
        return "/timeline"

    # Stats / Estatísticas
    if lower in ("stats", "estatísticas", "estatisticas", "estadísticas", "est"):
        return "/stats"
    if re.search(r"\b(estat[íi]sticas?|estat[íi]stica|stats)\b", lower):
        # Diferenciar de analise (LLM) vs stats (view)
        # Mais flexível com prefixos: "ver", "minhas", "quero ver minhas", etc.
        patterns = [
            r"^(ver|mostrar|minhas|as|me\s+d[eá]|quero\s+ver|quero\s+ver\s+minhas)\s+",
            r"^(estat[íi]sticas?|stats)$"
        ]
        if any(re.match(p, lower) for p in patterns) or lower.endswith(("estatisticas", "estatísticas", "stats")):
            # Se for uma frase curta ( < 30 chars) contendo as keywords, assumir comando
            if len(lower) < 35:
                return "/stats"

    # Resumo / Revisão
    if lower in ("resumo", "resumen", "summary", "revisão", "revisao", "revisión"):
        return "/resumo"

    # Mês
    if lower in ("mês", "mes", "month"):
        return "/mes"

    # List shortcuts (NL)
    _LIST_NL_CAT = (
        "pelicula", "peliculas", "movie", "movies", "film", "films",
        "libro", "libros", "book", "books", "note", "notes", "notas", "nota",
        "shopping", "market", "mercado", "compras", "ingredients", "ingredientes",
        "recipe", "recipes", "receita", "receitas"
    )
    if lower_ascii in _LIST_NL_CAT:
        return f"/list {lower_ascii}"
    # "movie Matrix" -> /list movie Matrix
    for cat in _LIST_NL_CAT:
        if lower_ascii.startswith(cat + " "):
            return f"/list {lower_ascii}"

    # Common list items (fallback to /add if it looks like an item)
    _COMMON_ITEMS = {
        "arroz", "feijao", "massa", "azeite", "sal", "acucar", "leite", "ovos", "queijo", "manteiga",
        "tomate", "cebola", "alho", "batata", "frango", "carne", "peixe", "pao", "cafe", "agua",
        "cerveja", "vinho", "fruta", "banana", "laranja", "presunto", "iogurte",
        "detergente", "papel", "sabonete", "shampoo", "creme", "pasta", "escova"
    }
    if lower_ascii in _COMMON_ITEMS:
        return f"/add {lower_ascii}"

    # Produtividade
    if lower in ("produtividade", "productividad", "productivity"):
        return "/produtividade"

    # Reset
    if lower in ("reiniciar", "reinicio", "reset", "restart", "reboot", "reset total"):
        return "/reset"

    # Exportar
    if lower in ("exportar", "exporta", "export"):
        return "/exportar"

    # Quiet / Silêncio
    if lower in ("silêncio", "silencio", "silent", "quiet"):
        return "/quiet"

    # Deletar tudo
    if lower in ("deletar tudo", "apagar tudo", "apaga tudo", "borrar todo", "delete all"):
        return "/deletar_tudo"

    # Limpeza
    if lower in ("limpeza", "limpieza", "cleaning"):
        return "/limpeza"

    # Meta(s)
    if lower in ("metas", "goals", "objetivos"):
        return "/metas"
    if lower in ("meta", "goal", "objetivo"):
        return "/meta"

    # Projeto(s)
    if lower in ("projetos", "proyectos", "projects"):
        return "/projetos"
    if lower in ("projeto", "proyecto", "project"):
        return "/projeto"

    # Template(s)
    if lower in ("templates", "modelos", "plantillas"):
        return "/templates"
    if lower in ("template", "modelo", "plantilla"):
        return "/template"

    # Pomodoro / Foco
    if lower in ("pomodoro", "foco", "focus", "timer"):
        return "/pomodoro"
    m = re.match(r"^(?:foco|focus|timer)\s+(\d+)$", lower)
    if m:
        return f"/pomodoro {m.group(1)}"

    # Hora e Data
    if lower in ("hora", "horas", "time", "qué hora", "que hora", "qual a hora", "me diga a hora"):
        return "/hora"
    if lower in ("data", "date", "fecha", "que dia", "qué día", "que dia é hoje"):
        return "/data"

    # Remove / Delete
    m = re.match(r"^(remover|apagar|deletar|tirar|quitar|borrar|apaga|borra|quita|delete|remove|suprimir)\s+(.+)$", lower_ascii)
    if m:
        rest = m.group(2).strip()
        if rest:
            return f"/remove {rest}"

    # Feito / Done / Hecho
    m = re.match(r"^(feito|concluido|pronto|ok|done|hecho|check|concluir)\s+(.+)$", lower_ascii)
    if m:
        rest = m.group(2).strip()
        if rest:
            return f"/feito {rest}"

    return content
