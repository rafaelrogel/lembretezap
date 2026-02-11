"""User lookup by phone: get_or_create with truncated PII, hash for id. Idioma por chat_id."""

import hashlib
from sqlalchemy.orm import Session

from backend.models_db import User, _truncate_phone
from backend.locale import LangCode, phone_to_default_language
from backend.timezone import phone_to_default_timezone


def phone_hash(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def get_or_create_user(db: Session, phone: str) -> User:
    h = phone_hash(phone)
    user = db.query(User).filter(User.phone_hash == h).first()
    if user:
        return user
    user = User(
        phone_hash=h,
        phone_truncated=_truncate_phone(phone),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_language(db: Session, chat_id: str) -> LangCode:
    """Idioma do utilizador: guardado ou inferido pelo prefixo do número (pt-BR, pt-PT, es, en)."""
    from backend.locale import SUPPORTED_LANGS
    user = get_or_create_user(db, chat_id)
    if user.language and user.language in SUPPORTED_LANGS:
        return user.language  # type: ignore
    return phone_to_default_language(chat_id)


def set_user_language(db: Session, chat_id: str, lang: LangCode) -> None:
    """Grava preferência de idioma do utilizador (pt-PT, pt-BR, es, en)."""
    from backend.locale import SUPPORTED_LANGS
    if lang not in SUPPORTED_LANGS:
        return
    user = get_or_create_user(db, chat_id)
    user.language = lang
    db.commit()


def get_user_timezone(db: Session, chat_id: str) -> str:
    """Timezone do utilizador: guardado (IANA) ou inferido pelo prefixo do número."""
    user = get_or_create_user(db, chat_id)
    if user.timezone:
        try:
            from backend.timezone import is_valid_iana
            if is_valid_iana(user.timezone):
                return user.timezone
        except Exception:
            pass
    return phone_to_default_timezone(chat_id)


def set_user_timezone(db: Session, chat_id: str, tz_iana: str) -> bool:
    """Grava timezone do utilizador (IANA, ex. Europe/Lisbon). Retorna True se válido e gravado."""
    from backend.timezone import is_valid_iana
    if not tz_iana or not is_valid_iana(tz_iana):
        return False
    user = get_or_create_user(db, chat_id)
    user.timezone = tz_iana
    db.commit()
    return True


def _parse_time_hhmm(s: str) -> tuple[int, int] | None:
    """Valida HH:MM (0-23, 0-59). Retorna (h, m) ou None."""
    if not s or len(s) > 5:
        return None
    s = s.strip()
    if len(s) == 5 and s[2] == ":":
        try:
            h, m = int(s[:2]), int(s[3:5])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return (h, m)
        except ValueError:
            pass
    return None


def get_user_quiet(db: Session, chat_id: str) -> tuple[str | None, str | None]:
    """Retorna (quiet_start, quiet_end) em HH:MM ou (None, None)."""
    user = get_or_create_user(db, chat_id)
    return (user.quiet_start, user.quiet_end)


def set_user_quiet(db: Session, chat_id: str, start_hhmm: str | None, end_hhmm: str | None) -> bool:
    """Grava horário silencioso. start/end em HH:MM (ex.: 22:00, 08:00). None para desativar. Retorna True se válido."""
    user = get_or_create_user(db, chat_id)
    if start_hhmm is None and end_hhmm is None:
        user.quiet_start = None
        user.quiet_end = None
        db.commit()
        return True
    start = _parse_time_hhmm(start_hhmm or "")
    end = _parse_time_hhmm(end_hhmm or "")
    if start is None or end is None:
        return False
    user.quiet_start = start_hhmm.strip()[:5]
    user.quiet_end = end_hhmm.strip()[:5]
    db.commit()
    return True


def is_user_in_quiet_window(chat_id: str) -> bool:
    """
    True se o utilizador está no horário silencioso (não enviar notificações).
    Usa timezone do user e hora atual nesse fuso.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        user = get_or_create_user(db, chat_id)
        if not user.quiet_start or not user.quiet_end:
            return False
        start = _parse_time_hhmm(user.quiet_start)
        end = _parse_time_hhmm(user.quiet_end)
        if not start or not end:
            return False
        tz_iana = user.timezone or phone_to_default_timezone(chat_id)
        try:
            now = datetime.now(ZoneInfo(tz_iana))
        except Exception:
            return False
        now_m = now.hour * 60 + now.minute
        start_m = start[0] * 60 + start[1]
        end_m = end[0] * 60 + end[1]
        if start_m <= end_m:
            return start_m <= now_m < end_m
        return now_m >= start_m or now_m < end_m
    finally:
        db.close()


def _sanitize_preferred_name(raw: str, max_len: int = 128) -> str | None:
    """Normaliza o nome preferido: trim, limite de caracteres. Retorna None se vazio ou inválido."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    return s[:max_len] if len(s) > max_len else s


def _sanitize_city(raw: str, max_len: int = 128) -> str | None:
    """Normaliza nome de cidade para guardar. Retorna None se vazio."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    return s[:max_len] if len(s) > max_len else s


def get_user_city(db: Session, chat_id: str) -> str | None:
    """Cidade do utilizador (guardada no onboarding). None se não definida."""
    user = get_or_create_user(db, chat_id)
    c = (user.city or "").strip()
    return c if c else None


def set_user_city(db: Session, chat_id: str, city: str, tz_iana: str | None = None) -> bool:
    """Grava a cidade do utilizador. Se tz_iana for dado (ex.: do Mimo) ou reconhecida em CITY_TO_IANA, define o timezone. Retorna True."""
    from backend.timezone import city_to_iana, is_valid_iana
    sanitized = _sanitize_city(city)
    if sanitized is None:
        return False
    user = get_or_create_user(db, chat_id)
    user.city = sanitized
    if tz_iana and is_valid_iana(tz_iana):
        user.timezone = tz_iana
    else:
        tz = city_to_iana(sanitized)
        if tz and is_valid_iana(tz):
            user.timezone = tz
    db.commit()
    return True


def get_user_preferred_name(db: Session, chat_id: str) -> str | None:
    """Nome como o cliente gostaria de ser chamado (ou None se ainda não definido)."""
    user = get_or_create_user(db, chat_id)
    name = (user.preferred_name or "").strip()
    return name if name else None


def set_user_preferred_name(db: Session, chat_id: str, name: str) -> bool:
    """Grava o nome preferido do utilizador. Retorna True se válido e gravado."""
    sanitized = _sanitize_preferred_name(name)
    if sanitized is None:
        return False
    user = get_or_create_user(db, chat_id)
    user.preferred_name = sanitized
    db.commit()
    return True


def get_default_reminder_lead_seconds(db: Session, chat_id: str) -> int | None:
    """Segundos de antecedência do primeiro aviso (ex.: 86400 = 1 dia). None se não definido."""
    user = get_or_create_user(db, chat_id)
    v = user.default_reminder_lead_seconds
    return int(v) if v is not None and v > 0 else None


def set_default_reminder_lead_seconds(db: Session, chat_id: str, seconds: int) -> bool:
    """Grava antecedência do primeiro aviso (segundos). Retorna True se válido."""
    if seconds <= 0 or seconds > 86400 * 365:
        return False
    user = get_or_create_user(db, chat_id)
    user.default_reminder_lead_seconds = seconds
    db.commit()
    return True


def get_extra_reminder_leads_seconds(db: Session, chat_id: str) -> list[int]:
    """Lista de até 3 antecedências extra em segundos (ex.: [259200, 86400, 7200])."""
    from backend.lead_time import extra_leads_from_json
    user = get_or_create_user(db, chat_id)
    return extra_leads_from_json(user.extra_reminder_leads)


def set_extra_reminder_leads_seconds(db: Session, chat_id: str, seconds_list: list[int]) -> bool:
    """Grava até 3 antecedências extra (segundos). Retorna True."""
    from backend.lead_time import extra_leads_to_json
    user = get_or_create_user(db, chat_id)
    user.extra_reminder_leads = extra_leads_to_json(seconds_list, max_count=3)
    db.commit()
    return True


def clear_onboarding_data(db: Session, chat_id: str) -> bool:
    """
    Limpa dados do onboarding (nome, cidade) para permitir refazer.
    Mantém idioma; timezone volta ao padrão do número.
    Retorna True se alterou algo.
    """
    user = get_or_create_user(db, chat_id)
    changed = False
    if user.preferred_name:
        user.preferred_name = None
        changed = True
    if user.city:
        user.city = None
        changed = True
    user.timezone = None  # volta ao phone_to_default_timezone
    changed = True
    db.commit()
    return changed
