"""
Fluxo para eventos recorrentes agendados: academia, aulas, cursos, faculdade, artes marciais.

Ex.: "academia segunda e quarta 19h" → detecta, confirma, pergunta até quando, registra.
"""

import re
from typing import Any

from backend.recurring_patterns import is_in_recurring_list, _normalize
from backend.time_parse import DIAS_SEMANA

# Eventos tipicamente recorrentes com horário fixo semanal (academia, aulas, etc.)
SCHEDULED_RECURRING_HINTS = frozenset({
    "academia", "gym", "ginásio", "ginasio",
    "artes marciais", "martial arts", "karatê", "karate", "judô", "judo",
    "jujitsu", "jiu-jitsu", "taekwondo", "boxe", "muay thai",
    "aula", "aulas", "class", "classes", "clase", "clases",
    "faculdade", "universidade", "university", "college",
    "curso", "cursos", "course", "courses",
    "simposio", "simpósio", "symposium", "workshop", "seminário", "seminario",
    "treino", "trainning", "entrenamiento",
    "inglês", "ingles", "english", "idioma", "language",
    "natação", "natacao", "swimming", "yoga", "pilates",
})

FLOW_KEY = "pending_recurring_event_flow"
STAGE_NEED_CONFIRM = "need_confirm"
STAGE_NEED_END_DATE = "need_end_date"
MAX_RETRIES_END_DATE = 3

# Padrão: evento + (segunda e quarta | segunda, quarta | segunda a sexta) + hora
_DAY_NAMES = "|".join(sorted(DIAS_SEMANA.keys(), key=len, reverse=True))
_RE_MULTI_DAY = re.compile(
    rf"((?:{_DAY_NAMES})(?:\s*(?:e|,)\s*(?:{_DAY_NAMES}))*)\s+"
    r"(?:às?\s*)?(\d{1,2})(?::(\d{2}))?\s*h?\b",
    re.I,
)
_RE_SINGLE_DAY = re.compile(
    rf"({_DAY_NAMES})\s+(?:às?\s*)?(\d{{1,2}})(?::(\d{{2}}))?\s*h?\b",
    re.I,
)
_RE_WEEKDAYS = re.compile(
    r"segunda\s+a\s+sexta\s+(?:às?\s*)?(\d{1,2})(?::(\d{2}))?\s*h?\b",
    re.I,
)


def is_scheduled_recurring_event(text: str) -> bool:
    """True se o texto parece evento recorrente com horário (academia segunda 19h, etc.)."""
    if not text or len(text.strip()) < 8:
        return False
    t = _normalize(text)
    return any(h in t for h in {_normalize(x) for x in SCHEDULED_RECURRING_HINTS})


def parse_recurring_schedule(text: str) -> tuple[str, str, int, int] | None:
    """
    Extrai evento + cron de «academia segunda e quarta 19h» ou «aulas terça 10h».
    Retorna (event_content, cron_expr, hour, minute) ou None.
    """
    if not text or len(text.strip()) < 8:
        return None
    t = text.strip()
    tl = t.lower()

    # "segunda a sexta 8h" → cron 0 8 * * 1-5
    m = _RE_WEEKDAYS.search(tl)
    if m:
        hora = min(23, max(0, int(m.group(1))))
        minuto = int(m.group(2) or 0) if m.group(2) else 0
        content = _RE_WEEKDAYS.sub("", t).strip()
        content = re.sub(r"\s+", " ", content).strip()
        if content and len(content) >= 2:
            cron = f"0 {hora} * * 1-5"
            return content, cron, hora, minuto

    # "segunda e quarta 19h", "terça, quinta 10h"
    m = _RE_MULTI_DAY.search(tl)
    if m:
        days_str = m.group(1)
        hora = min(23, max(0, int(m.group(2))))
        minuto = int(m.group(3) or 0) if m.group(3) else 0
        dow_nums = _parse_day_list(days_str)
        if dow_nums:
            dow_cron = ",".join(str(d) for d in sorted(dow_nums))
            cron = f"0 {hora} * * {dow_cron}"
            content = _RE_MULTI_DAY.sub("", t).strip()
            content = re.sub(r"\s+", " ", content).strip()
            if content and len(content) >= 2:
                return content, cron, hora, minuto

    # "terça 10h", "segunda 19h"
    m = _RE_SINGLE_DAY.search(tl)
    if m:
        dia_raw = (m.group(1) or "").strip().lower()
        hora = min(23, max(0, int(m.group(2))))
        minuto = int(m.group(3) or 0) if m.group(3) else 0
        dow = DIAS_SEMANA.get(dia_raw)
        if dow is not None:
            cron = f"0 {hora} * * {dow}"
            content = _RE_SINGLE_DAY.sub("", t).strip()
            content = re.sub(r"\s+", " ", content).strip()
            if content and len(content) >= 2:
                return content, cron, hora, minuto

    return None


def _parse_day_list(days_str: str) -> list[int]:
    """'segunda e quarta' → [1, 3]. 'terça, quinta' → [2, 4]."""
    parts = re.split(r"\s*(?:e|,)\s*", days_str.strip(), flags=re.I)
    result = []
    for p in parts:
        p = p.strip().lower()
        for name, dow in DIAS_SEMANA.items():
            if name in p or p == name:
                result.append(dow)
                break
    return sorted(set(result))


def format_schedule_for_display(cron_expr: str, lang: str = "pt-BR") -> str:
    """'0 19 * * 1,3' → 'segunda e quarta às 19h'."""
    parts = (cron_expr or "").strip().split()
    if len(parts) < 5:
        return cron_expr
    try:
        hora = int(parts[1])
        dow_str = parts[4]
        if "-" in dow_str:
            # 1-5 = segunda a sexta
            return f"segunda a sexta às {hora}h"
        dows = [int(x) for x in dow_str.split(",")]
        names = {1: "segunda", 2: "terça", 3: "quarta", 4: "quinta", 5: "sexta", 6: "sábado", 0: "domingo"}
        labels = [names.get(d, "") for d in dows if d in names]
        if len(labels) == 1:
            return f"{labels[0]} às {hora}h"
        if len(labels) == 2:
            return f"{labels[0]} e {labels[1]} às {hora}h"
        return ", ".join(labels[:-1]) + f" e {labels[-1]} às {hora}h"
    except (ValueError, IndexError):
        return cron_expr


def parse_end_date_response(text: str) -> str | None:
    """
    Interpreta resposta sobre «até quando».
    Retorna: "indefinido" | "fim_semana" | "fim_mes" | "fim_ano" | None
    """
    if not text or not text.strip():
        return None
    t = text.strip().lower()
    if any(p in t for p in ("indefinido", "para sempre", "sempre", "nunca", "ate eu remover", "até eu remover")):
        return "indefinido"
    # "não" sozinho pode ser "não sei" → excluir quando tem "sei"
    if ("nao" in t or "não" in t) and "sei" not in t and len(t) < 15:
        return "indefinido"
    if any(p in t for p in ("fim da semana", "fim semana", "final da semana", "ate sexta", "até sexta")):
        return "fim_semana"
    if any(p in t for p in ("fim do mês", "fim mes", "fim do mes", "final do mês")):
        return "fim_mes"
    if any(p in t for p in ("fim do ano", "fim ano", "final do ano")):
        return "fim_ano"
    return None


def looks_like_confirm_yes(text: str) -> bool:
    """Resposta afirmativa para confirmação."""
    t = (text or "").strip().lower()
    if not t or len(t) > 30:
        return False
    return any(
        p in t for p in ("sim", "s", "quero", "yes", "pode", "regista", "registre", "faz", "claro", "ok")
    )


def looks_like_confirm_no(text: str) -> bool:
    """Resposta negativa."""
    t = (text or "").strip().lower()
    if not t or len(t) > 30:
        return False
    return any(p in t for p in ("não", "nao", "no", "n", "dispenso", "cancelar"))


def compute_end_date_ms(end_type: str, tz_iana: str = "UTC") -> int | None:
    """Calcula not_after_ms para fim_semana, fim_mes, fim_ano."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        z = ZoneInfo(tz_iana)
        now = datetime.now(tz=z)

        if end_type == "fim_semana":
            # Próximo domingo 23:59
            days_until_sun = (6 - now.weekday()) % 7
            if days_until_sun == 0 and now.hour >= 23:
                days_until_sun = 7
            from datetime import timedelta
            end = now.replace(hour=23, minute=59, second=59, microsecond=0)
            end = end + timedelta(days=days_until_sun)
            return int(end.timestamp() * 1000)
        if end_type == "fim_mes":
            from calendar import monthrange
            _, last = monthrange(now.year, now.month)
            end = now.replace(day=last, hour=23, minute=59, second=59, microsecond=0)
            return int(end.timestamp() * 1000)
        if end_type == "fim_ano":
            end = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=0)
            return int(end.timestamp() * 1000)
    except Exception:
        pass
    return None
