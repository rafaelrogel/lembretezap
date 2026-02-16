"""
Recursos pouco usados: listas, lembretes (cron) sem atividade nos últimos N dias.
Usado pelo comando #cleanup (god-mode) para sugerir remoção.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.models_db import List, ListItem, AuditLog


def gather_unused_resources(
    db: Session,
    cron_store_path: Path | None,
    days: int = 90,
) -> dict[str, Any]:
    """
    Reúne recursos sem atividade nos últimos N dias.
    Retorna: {lists_unused: [...], cron_unused: [...], summary: str}.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_ts_ms = int(since.timestamp() * 1000)

    # Listas: última atividade (AuditLog ou ListItem) há mais de N dias
    lists_unused: list[dict[str, Any]] = []
    for lst in db.query(List).all():
        user_id = lst.user_id
        list_name = lst.name
        # Última atividade: AuditLog (list_add, list_remove, list_feito para esta lista)
        last_audit_row = (
            db.query(AuditLog.created_at)
            .filter(
                AuditLog.user_id == user_id,
                AuditLog.action.in_(("list_add", "list_remove", "list_feito")),
                (AuditLog.resource == list_name) | (AuditLog.resource.op("LIKE")(f"{list_name}#%")),
            )
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        last_item_row = (
            db.query(ListItem.created_at)
            .filter(ListItem.list_id == lst.id)
            .order_by(ListItem.created_at.desc())
            .first()
        )
        last_dates = [r[0] for r in (last_audit_row, last_item_row) if r and r[0]]
        if not last_dates:
            continue  # Lista vazia sem histórico — ignorar
        last_activity = max(last_dates)
        if last_activity >= since:
            continue  # Teve atividade recente
        pending = db.query(ListItem).filter(
            ListItem.list_id == lst.id,
            ListItem.done == False,
        ).count()
        total_items = db.query(ListItem).filter(ListItem.list_id == lst.id).count()
        lists_unused.append({
            "user_id": user_id,
            "list_name": list_name,
            "pending": pending,
            "total_items": total_items,
            "last_activity": last_activity.isoformat()[:10] if last_activity else "",
        })

    # Cron jobs: lastRunAtMs antigo ou nunca executou (e createdAt antigo)
    cron_unused: list[dict[str, Any]] = []
    if cron_store_path and cron_store_path.exists():
        import json
        try:
            data = json.loads(cron_store_path.read_text())
            jobs = data.get("jobs", [])
            for j in jobs:
                if not j.get("enabled", True):
                    continue
                payload = j.get("payload") or {}
                state = j.get("state") or {}
                last_run = state.get("lastRunAtMs")
                created = j.get("createdAtMs") or 0
                to = payload.get("to", "?")
                msg = (payload.get("message") or j.get("name") or "?")[:40]
                # Nunca executou e criado há mais de N dias
                if not last_run and created > 0 and created < since_ts_ms:
                    cron_unused.append({
                        "id": j.get("id", "?"),
                        "to": to[-10:] if to else "?",
                        "message": msg,
                        "reason": "nunca executou",
                    })
                # Última execução há mais de N dias
                elif last_run and last_run < since_ts_ms:
                    cron_unused.append({
                        "id": j.get("id", "?"),
                        "to": to[-10:] if to else "?",
                        "message": msg,
                        "reason": f"última execução há {days}+ dias",
                    })
        except Exception:
            pass

    # Resumo em texto para o Mimo
    lines = []
    if lists_unused:
        lines.append("## Listas sem atividade (últimos {} dias)".format(days))
        for u in lists_unused[:20]:
            lines.append("- Lista \"{}\" (user_id={}): {} pendentes, {} itens totais".format(
                u["list_name"], u["user_id"], u["pending"], u["total_items"]
            ))
    if cron_unused:
        lines.append("\n## Lembretes (cron) pouco usados")
        for u in cron_unused[:15]:
            lines.append("- \"{}\" (***{}): {}".format(u["message"], u["to"], u["reason"]))
    summary = "\n".join(lines) if lines else "Nenhum recurso pouco usado encontrado nos últimos {} dias.".format(days)

    return {
        "lists_unused": lists_unused,
        "cron_unused": cron_unused,
        "summary": summary,
        "days": days,
    }
