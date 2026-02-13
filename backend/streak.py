"""Streak counting e mensagens motivadoras para hábitos (saúde, água, academia, estudos).

Regra: DeepSeek → criar mensagens. Mimo → histórico, verificação, análise de dados."""

from datetime import timedelta

from backend.models_db import HabitCheck


def get_habit_streak(db, habit_id: int, today_str: str) -> int:
    """
    Calcula dias consecutivos do hábito até hoje (incluindo hoje).
    today_str: YYYY-MM-DD no timezone do user.
    """
    from datetime import datetime

    today = datetime.strptime(today_str, "%Y-%m-%d").date()
    checks = (
        db.query(HabitCheck.check_date)
        .filter(HabitCheck.habit_id == habit_id)
        .distinct()
        .all()
    )
    dates_set = {c[0] for c in checks if c[0]}
    streak = 0
    d = today
    while d.isoformat() in dates_set:
        streak += 1
        d -= timedelta(days=1)
    return streak


async def generate_streak_message(
    provider,
    model: str,
    habit_name: str,
    streak: int,
    user_lang: str = "pt-BR",
) -> str | None:
    """
    Gera mensagem motivadora via Mimo primeiro, fallback DeepSeek. Curta, positiva, suscinta.
    Ex.: "Você foi à academia 5 dias consecutivos! Isso aí! 🔥"
    """
    if not provider or not model or streak < 2:
        return None
    try:
        lang_instruction = {
            "pt-PT": "Responde em português de Portugal.",
            "pt-BR": "Responde em português do Brasil.",
            "es": "Responde en español.",
            "en": "Respond in English.",
        }.get(user_lang or "pt-BR", "Responde no idioma do utilizador.")

        prompt = (
            f"O utilizador completou o hábito «{habit_name}» {streak} dias consecutivos. "
            f"Cria UMA frase curta (máx 15 palavras), positiva, motivadora e simpática. "
            "Um emoji no fim. Sem ponto final. "
            f"{lang_instruction} Exemplo de tom: «5 dias seguidos! Isso aí! 🔥»"
        )
        r = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            max_tokens=60,
            temperature=0.7,
        )
        out = (r.content or "").strip().strip('"\'')
        if out and len(out) <= 80:
            return out
    except Exception:
        pass
    return None


def _default_streak_message(habit_name: str, streak: int, user_lang: str) -> str:
    """Fallback quando DeepSeek não está disponível."""
    templates = {
        "pt-PT": f"{streak} dias consecutivos de {habit_name}! Continua assim! 💪",
        "pt-BR": f"{streak} dias consecutivos de {habit_name}! Continua assim! 💪",
        "es": f"¡{streak} días seguidos de {habit_name}! ¡Sigue así! 💪",
        "en": f"{streak} days in a row of {habit_name}! Keep it up! 💪",
    }
    return templates.get(user_lang, templates["pt-BR"])
