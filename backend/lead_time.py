"""Parse "1 dia", "2 horas", "30 min" para segundos (preferências de aviso antes do evento)."""

import re
import json


def parse_lead_time_to_seconds(text: str) -> int | None:
    """
    Converte um texto como "1 dia", "2 horas", "30 min" em segundos.
    Retorna None se não reconhecer. Aceita pt, es, en.
    """
    if not text or not text.strip():
        return None
    t = text.strip().lower()
    # Número + unidade: 1 dia, 2 horas, 30 minutos, 30 min
    m = re.search(r"(\d+)\s*(dia|dias|hora|horas|minuto?|minutos?|min)\b", t)
    if not m:
        return None
    try:
        n = int(m.group(1))
        unit = (m.group(2) or "").lower()
        if "dia" in unit:
            return n * 86400
        if "hora" in unit:
            return n * 3600
        if "min" in unit:
            return n * 60
    except (ValueError, IndexError):
        pass
    return None


def parse_lead_times_to_seconds(text: str, max_count: int = 3) -> list[int]:
    """
    Extrai até max_count valores "X dia/hora/min" do texto (ex.: "3 dias, 1 dia e 30 min").
    Retorna lista de segundos, ordenada por valor decrescente (maior antecedência primeiro).
    """
    if not text or not text.strip():
        return []
    # Split por vírgula, " e ", " e também ", etc.
    parts = re.split(r"[, e \t]+", text.strip().lower())
    seen = set()
    result = []
    for part in parts:
        part = part.strip()
        if not part or part in ("não", "no", "nao", "sim", "si", "yes"):
            continue
        sec = parse_lead_time_to_seconds(part)
        if sec is not None and sec > 0 and sec not in seen:
            seen.add(sec)
            result.append(sec)
            if len(result) >= max_count:
                break
    # Ordenar por antecedência (maior primeiro: 3 dias > 1 dia > 2 horas)
    result.sort(reverse=True)
    return result


def extra_leads_to_json(seconds_list: list[int], max_count: int = 3) -> str:
    """Serializa lista de segundos para JSON (coluna extra_reminder_leads)."""
    trimmed = [int(s) for s in seconds_list if s > 0][:max_count]
    return json.dumps(trimmed) if trimmed else ""


def extra_leads_from_json(json_str: str | None) -> list[int]:
    """Deserializa coluna extra_reminder_leads para lista de segundos."""
    if not json_str or not json_str.strip():
        return []
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            return [int(x) for x in data if isinstance(x, (int, float)) and x > 0][:3]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return []
