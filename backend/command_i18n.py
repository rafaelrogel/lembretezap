"""Localização de comandos com / para 4 idiomas (pt-PT, pt-BR, es, en).

Cada comando canónico tem aliases nas 4 línguas. normalize_command() substitui
o primeiro token pela forma canónica para os handlers e parser funcionarem igual.
"""

import re
from typing import Sequence

# (comando canónico, [alias pt-PT, pt-BR, es, en e variações])
# Ordem: canónico primeiro, depois aliases; o primeiro match ganha.
COMMAND_ALIASES: Sequence[tuple[str, Sequence[str]]] = (
    # Ajuda / Help
    ("/help", ("/help", "/ajuda", "/ayuda")),
    # Início
    ("/start", ("/start", "/iniciar", "/comenzar", "/begin")),
    # Lista
    ("/list", ("/list", "/lista", "/listar")),
    # Lembrete
    ("/lembrete", ("/lembrete", "/recordatorio", "/recordar", "/remind", "/reminder")),
    # Hoje / Semana / Timeline
    ("/hoje", ("/hoje", "/hoy", "/today")),
    ("/semana", ("/semana", "/week")),
    ("/agenda", ("/agenda", "/schedule", "/programação", "/programacion")),
    ("/timeline", ("/timeline", "/cronologia", "/cronología", "/linha", "/histórico", "/historico", "/history")),
    ("/mes", ("/mes", "/mês", "/month")),
    # Estatísticas
    ("/stats", ("/stats", "/estatísticas", "/estatisticas", "/est", "/estadísticas", "/estadisticas", "/estd", "/statistics")),
    # Resumo
    ("/resumo", ("/resumo", "/resumen", "/summary", "/revisao", "/revisão", "/revisión", "/review")),
    # Recorrente
    ("/recorrente", ("/recorrente", "/recurrente", "/recurring", "/repetir")),
    # Meta(s)
    ("/meta", ("/meta", "/goal", "/objetivo")),
    ("/metas", ("/metas", "/goals", "/objetivos")),
    # Pomodoro
    ("/pomodoro", ("/pomodoro", "/foco", "/focus", "/timer")),
    # Configuração: tz, lang, reset, quiet
    ("/tz", ("/tz", "/cidade", "/ciudad", "/city", "/fuso", "/timezone", "/zona")),
    ("/lang", ("/lang", "/idioma", "/language", "/língua", "/lingua")),
    ("/reset", ("/reset", "/reiniciar", "/reinicio", "/restart", "/reboot", "/limpar")),
    ("/quiet", ("/quiet", "/silêncio", "/silencio", "/silent", "/mudo", "/mute")),
    # Ações
    ("/add", ("/add", "/adicionar", "/añadir", "/adiciona", "/agregar")),
    ("/remove", ("/remove", "/remover", "/quitar", "/delete", "/del", "/borrar")),
    ("/feito", ("/feito", "/done", "/hecho", "/ok", "/listo", "/visto", "/terminado")),
    ("/pendente", ("/pendente", "/pendiente", "/pending", "/pendentes", "/pendientes")),
    ("/stop", ("/stop", "/parar", "/detener", "/quit")),
    ("/exportar", ("/exportar", "/export", "/exporta", "/enviar")),
    ("/deletar_tudo", ("/deletar_tudo", "/apagar_tudo", "/borrar_todo", "/delete_all")),
    # Tempo
    ("/hora", ("/hora", "/horas", "/time", "/qué hora", "/que hora")),
    ("/data", ("/data", "/date", "/fecha", "/que dia", "/qué día")),
    # Evento
    ("/evento", ("/evento", "/event", "/compromisso", "/cita")),
    # Limpeza / Organização
    ("/limpeza", ("/limpeza", "/limpieza", "/cleaning", "/clean")),
    ("/projeto", ("/projeto", "/proyecto", "/project")),
    ("/projetos", ("/projetos", "/proyectos", "/projects")),
    ("/template", ("/template", "/modelo", "/plantilla")),
    ("/templates", ("/templates", "/modelos", "/plantillas")),
    ("/produtividade", ("/produtividade", "/productividad", "/productivity")),
    ("/nuke", ("/nuke", "/bomba", "/bomb", "/detonar")),
    # Integrações
    ("/crypto", ("/crypto", "/cripto", "/bitcoin", "/btc")),
    ("/atendimento", ("/atendimento", "/suporte", "/support", "/ayuda_humana")),
    ("/biblia", ("/biblia", "/bíblia", "/bible", "/versiculo", "/versículo")),
    ("/alcorao", ("/alcorao", "/alcorão", "/quran", "/sura")),
)

# Construir set de todos os aliases em minúsculas para match rápido
_CANONICAL_BY_ALIAS: dict[str, str] = {}
for canonical, aliases in COMMAND_ALIASES:
    for a in aliases:
        _CANONICAL_BY_ALIAS[a.lower().strip()] = canonical


def normalize_command(content: str) -> str:
    """Substitui o primeiro token (comando) pela forma canónica se for um alias conhecido."""
    import json as _j, os as _os
    _log_path = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "nanobot", ".cursor", "debug.log"))
    # #region agent log
    try: open(_log_path, "a", encoding="utf-8").write(_j.dumps({"location": "command_i18n.normalize_command.entry", "message": "normalize_command", "data": {"content_in": content[:200] if content else None}, "timestamp": __import__("time").time() * 1000, "hypothesisId": "H1"}) + "\n"); pass
    except Exception: pass
    # #endregion
    if not content or not isinstance(content, str):
        return content
    t = content.strip()
    if not t:
        return content
    m = re.match(r"^(\S+)(?:\s+(.*))?$", t, re.DOTALL)
    if not m:
        return content
    first, rest = m.group(1), (m.group(2) or "").strip()
    canonical = _CANONICAL_BY_ALIAS.get(first.lower())
    if canonical is None:
        return content
    out = f"{canonical} {rest}" if rest else canonical
    # #region agent log
    try: open(_log_path, "a", encoding="utf-8").write(_j.dumps({"location": "command_i18n.normalize_command.exit", "message": "normalize_command", "data": {"content_out": out[:200], "changed": out != content}, "timestamp": __import__("time").time() * 1000, "hypothesisId": "H1"}) + "\n"); pass
    except Exception: pass
    # #endregion
    return out
