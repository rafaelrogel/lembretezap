"""
Conteúdo de memória longa com dados do onboarding (nome, cidade, idioma).
O agente usa isto para saber e lembrar as preferências de cada cliente.
Avisos antes do lembrete são decididos por contexto (classificador) por lembrete, não guardados no perfil.
"""

from sqlalchemy.orm import Session

from backend.user_store import (
    get_user_preferred_name,
    get_user_city,
    get_user_timezone,
    get_user_language,
)


SECTION_HEADING = "## Perfil do utilizador (onboarding)"


def build_onboarding_profile_md(db: Session, chat_id: str) -> str:
    """
    Monta o texto em Markdown do perfil do utilizador a partir da BD (onboarding).
    Para ser gravado na memória longa do cliente (MEMORY.md) via MemoryStore.upsert_section.
    """
    name = get_user_preferred_name(db, chat_id)
    city = get_user_city(db, chat_id)
    tz = get_user_timezone(db, chat_id)
    lang = get_user_language(db, chat_id)

    lines: list[str] = []
    if name:
        lines.append(f"- **Nome preferido:** {name}")
    if city:
        lines.append(f"- **Cidade:** {city}")
    if tz:
        lines.append(f"- **Fuso horário:** {tz}")
    if lang:
        lines.append(f"- **Idioma:** {lang}")

    if not lines:
        return "_(Dados do onboarding ainda não preenchidos.)_"
    return "\n".join(lines)
