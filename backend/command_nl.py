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
    m = re.match(r"^(adicione|adiciona|adicionar)\s+(.+)$", lower)
    if m:
        rest = m.group(2).strip()
        if rest and "lista" not in lower and "listas" not in lower:
            return f"/add mercado {rest}"

    # Recorrente: "lembrete recorrente X" ou "todo dia X" / "toda semana X"
    m = re.match(r"^lembrete\s+recorrente\s+(.+)$", lower)
    if m and m.group(1).strip():
        return f"/recorrente {m.group(1).strip()}"
    m = re.match(r"^(todo\s+dia|toda\s+semana|todos\s+os\s+dias)\s+(.+)$", lower)
    if m and m.group(2).strip():
        return f"/recorrente {m.group(2).strip()}"

    # Hoje / Semana / Agenda (views)
    if lower in ("hoje", "today", "hoy"):
        return "/hoje"
    if re.match(r"^(o\s+que\s+tenho\s+hoje|tarefas?\s+de\s+hoje)\s*$", lower):
        return "/hoje"
    if lower in ("semana", "week"):
        return "/semana"
    if re.match(r"^esta\s+semana\s*$", lower):
        return "/semana"
    if lower == "agenda":
        return "/agenda"
    if re.match(r"^(minha\s+agenda|o\s+que\s+tenho\s+agendado)\s*$", lower):
        return "/agenda"

    # Timeline
    if lower in ("timeline", "cronologia", "linha do tempo"):
        return "/timeline"

    # Stats / Estatísticas
    if lower in ("stats", "estatísticas", "estatisticas", "estadísticas", "est"):
        return "/stats"

    # Resumo / Revisão
    if lower in ("resumo", "resumen", "summary", "revisão", "revisao", "revisión"):
        return "/resumo"

    # Mês
    if lower in ("mês", "mes", "month"):
        return "/mes"

    # Produtividade
    if lower in ("produtividade", "productividad", "productivity"):
        return "/produtividade"

    # Reset
    if lower in ("reiniciar", "reinicio", "reset", "restart", "reboot"):
        return "/reset"

    # Exportar
    if lower in ("exportar", "exporta", "export"):
        return "/exportar"

    # Quiet / Silêncio
    if lower in ("silêncio", "silencio", "silent", "quiet"):
        return "/quiet"

    # Deletar tudo
    if lower in ("deletar tudo", "apagar tudo", "borrar todo", "delete all"):
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

    return content
