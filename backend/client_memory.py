"""Memória do cliente: nome, timezone e idioma. Usada pelo sistema e pela LLM para horários corretos e respostas no idioma certo.

Cada cliente tem:
- Dados na BD (User: preferred_name, timezone, language)
- Um ficheiro por cliente em workspace/users/<chat_id_safe>.md, criado/atualizado ao construir o contexto

O sistema e a LLM devem sempre usar este contexto para:
- Mostrar horários no fuso do cliente (comparar com o servidor e converter)
- Enviar lembretes na hora local do cliente
- Responder no idioma de comunicação do cliente
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _safe_filename(chat_id: str) -> str:
    """Identificador seguro para nome de ficheiro (evitar @, :, etc.)."""
    if not chat_id:
        return "unknown"
    s = re.sub(r"[^\w\-.]", "_", str(chat_id).strip())
    return s[:80] if s else "unknown"


def build_client_memory_content(db: "Session", chat_id: str) -> str:
    """
    Constrói o conteúdo da memória do cliente: nome, timezone, idioma e instrução
    para usar sempre o fuso do cliente nos horários (lembretes e respostas).

    O servidor/VPS pode estar em UTC ou outro fuso; todas as horas para este cliente
    devem ser calculadas/no fuso do cliente para lembretes no horário certo.
    """
    from backend.user_store import (
        get_or_create_user,
        get_user_timezone,
        get_user_language,
        get_user_preferred_name,
    )
    from backend.locale import resolve_response_language

    user = get_or_create_user(db, chat_id)
    name = (get_user_preferred_name(db, chat_id) or "").strip() or "(nome não definido)"
    tz_iana = get_user_timezone(db, chat_id)
    lang = get_user_language(db, chat_id)
    lang = resolve_response_language(lang, chat_id, None)
    city = (user.city or "").strip() if getattr(user, "city", None) else ""

    lines = [
        "# Cliente (memória)",
        "",
        f"- **Nome:** {name}",
        f"- **Timezone:** {tz_iana}" + (f" ({city})" if city else ""),
        f"- **Idioma de comunicação:** {lang}",
        "",
        "**Horários:** O servidor pode estar em UTC ou outro fuso. Todos os horários para este cliente (lembretes, respostas, \"que horas são?\") devem ser **no fuso do cliente**. Comparar com a hora local do servidor e converter quando necessário, para que o cliente receba lembretes na hora certa do seu local.",
    ]

    # Notas adicionais (context_notes) se existirem
    notes = (getattr(user, "context_notes", None) or "").strip()
    if notes:
        lines.append("")
        lines.append("**Notas:**")
        lines.append(notes)

    return "\n".join(lines)


def get_client_memory_file_path(workspace: Path, chat_id: str) -> Path:
    """Caminho do ficheiro de memória deste cliente (workspace/users/<chat_id_safe>.md)."""
    users_dir = workspace / "users"
    return users_dir / f"{_safe_filename(chat_id)}.md"


def write_client_memory_file(workspace: Path, chat_id: str, content: str) -> None:
    """
    Cria ou atualiza o ficheiro de memória do cliente.
    O sistema e a LLM podem sempre aceder a este ficheiro para nome, timezone e idioma.
    """
    path = get_client_memory_file_path(workspace, chat_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
