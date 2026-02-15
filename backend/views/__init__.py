"""Visões: /hoje, /semana, /mes, /timeline, /stats, /produtividade, /resumo, eventos unificados."""

from backend.views.hoje_semana import handle_hoje, handle_semana, handle_agenda, handle_agenda_nl
from backend.views.mes import handle_mes
from backend.views.timeline import handle_timeline
from backend.views.stats import handle_stats
from backend.views.produtividade import handle_produtividade
from backend.views.revisao import handle_revisao
from backend.views.unificado import handle_eventos_unificado

__all__ = [
    "handle_hoje",
    "handle_semana",
    "handle_agenda",
    "handle_agenda_nl",
    "handle_mes",
    "handle_timeline",
    "handle_stats",
    "handle_produtividade",
    "handle_revisao",
    "handle_eventos_unificado",
]
