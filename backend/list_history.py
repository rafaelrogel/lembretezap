"""
Histórico de listas para aprendizagem e sugestões via Mimo.

- Itens adicionados na semana passada (por lista)
- Itens mais frequentes (padrões: "costumas adicionar X à lista Y")
"""

from collections import Counter
from datetime import datetime, timedelta, time, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models_db import List, ListItem
from backend.user_store import get_or_create_user


def _utc_week_range(weeks_ago: int = 1) -> tuple[datetime, datetime]:
    """Retorna (início, fim) da semana N atrás, em UTC. Semana = seg-dom."""
    now = datetime.utcnow()
    # Segunda = dia 0 da semana
    today = now.date()
    days_since_monday = (today.weekday()) % 7
    last_monday = today - timedelta(days=days_since_monday)
    target_monday = last_monday - timedelta(weeks=weeks_ago)
    target_sunday = target_monday + timedelta(days=6)
    start = datetime.combine(target_monday, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = datetime.combine(target_sunday, time(23, 59, 59)).replace(tzinfo=timezone.utc)
    return start, end


def get_list_items_last_week(
    db: Session,
    chat_id: str,
    weeks_ago: int = 1,
) -> dict[str, list[dict[str, Any]]]:
    """
    Itens que existiam em cada lista durante a semana N atrás.

    Usa ListItem.created_at: itens criados até ao fim dessa semana e ainda não
    eliminados (ou marcados done) antes do fim da semana. Simplificado: itens
    criados nessa semana, por lista.
    """
    user = get_or_create_user(db, chat_id)
    start, end = _utc_week_range(weeks_ago)

    result: dict[str, list[dict[str, Any]]] = {}
    for lst in db.query(List).filter(List.user_id == user.id).all():
        items = (
            db.query(ListItem)
            .filter(
                ListItem.list_id == lst.id,
                ListItem.created_at >= start,
                ListItem.created_at <= end,
            )
            .order_by(ListItem.created_at)
            .all()
        )
        if items:
            result[lst.name] = [
                {"text": i.text[:80], "done": i.done, "created": str(i.created_at)[:10]}
                for i in items
            ]
    return result


def get_frequent_items(
    db: Session,
    chat_id: str,
    weeks: int = 4,
    top_per_list: int = 10,
) -> dict[str, list[tuple[str, int]]]:
    """
    Itens mais frequentes por lista nos últimos N semanas.
    Retorna {list_name: [(item_text, count), ...]} ordenado por count desc.
    """
    user = get_or_create_user(db, chat_id)
    since = datetime.utcnow() - timedelta(weeks=weeks)

    lists_data: dict[str, Counter[str]] = {}
    for lst in db.query(List).filter(List.user_id == user.id).all():
        items = (
            db.query(ListItem)
            .filter(ListItem.list_id == lst.id, ListItem.created_at >= since)
            .all()
        )
        if items:
            counter = Counter(i.text.strip()[:120] for i in items)
            lists_data[lst.name] = counter

    out: dict[str, list[tuple[str, int]]] = {}
    for name, counter in lists_data.items():
        out[name] = counter.most_common(top_per_list)
    return out


def format_last_week_for_mimo(items_by_list: dict[str, list[dict[str, Any]]]) -> str:
    """Formata o histórico da semana passada para incluir no prompt do Mimo."""
    if not items_by_list:
        return ""
    lines = ["## Listas da semana passada (itens adicionados)"]
    for list_name, items in items_by_list.items():
        texts = [i["text"] for i in items[:8]]
        lines.append(f"- Lista «{list_name}»: {', '.join(texts)}")
    return "\n".join(lines)


def format_frequent_for_mimo(freq: dict[str, list[tuple[str, int]]]) -> str:
    """Formata itens frequentes para o Mimo (sugestões de 'lista habitual')."""
    if not freq:
        return ""
    lines = ["## Itens habituais por lista (últimas 4 semanas)"]
    for list_name, pairs in freq.items():
        parts = [f"{t} ({c}x)" for t, c in pairs[:6]]
        if parts:
            lines.append(f"- Lista «{list_name}»: {', '.join(parts)}")
    return "\n".join(lines)
