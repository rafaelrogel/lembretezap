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


def _sanitize_preferred_name(raw: str, max_len: int = 128) -> str | None:
    """Normaliza o nome preferido: trim, limite de caracteres. Retorna None se vazio ou inválido."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    return s[:max_len] if len(s) > max_len else s


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
