"""
Mapa de vozes Piper por locale.

Locale (pt-BR, pt-PT, es, en) -> model + config path.
Paths relativos a TTS_MODELS_BASE ou /root/.zapista/models/piper.
"""

import os
from pathlib import Path

# Locale do agente (pt-BR, pt-PT, es, en) -> Piper voice (pt_BR, pt_PT, es_ES, en_US)
# Estrutura: <lang>/<voice>/<quality>/<lang>-<voice>-<quality>.onnx
# tugão: HuggingFace pode usar "tugão" (unicode) ou "tug%C3%A3o" (encoded) na pasta
PIPER_VOICES = {
    "pt-BR": {
        "model": "pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx",
        "config": "pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx.json",
    },
    "pt-PT": {
        "model": "pt/pt_PT/tug%C3%A3o/medium/pt_PT-tug%C3%A3o-medium.onnx",
        "config": "pt/pt_PT/tug%C3%A3o/medium/pt_PT-tug%C3%A3o-medium.onnx.json",
        # Fallback se HuggingFace usar pasta unicode
        "model_alt": "pt/pt_PT/tugão/medium/pt_PT-tugão-medium.onnx",
        "config_alt": "pt/pt_PT/tugão/medium/pt_PT-tugão-medium.onnx.json",
    },
    "es": {
        "model": "es/es_ES/davefx/medium/es_ES-davefx-medium.onnx",
        "config": "es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json",
    },
    "en": {
        "model": "en/en_US/amy/medium/en_US-amy-medium.onnx",
        "config": "en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    },
}

# Fallback quando modelo não existe (ex.: pt_PT falhou download → pt_BR)
LOCALE_FALLBACK: dict[str, str] = {
    "pt-PT": "pt-BR",
    "es": "pt-BR",
    "en": "pt-BR",
}


def tts_models_base() -> str:
    """Base path dos modelos Piper."""
    base = (os.environ.get("TTS_MODELS_BASE", "") or "").strip()
    if base:
        return base
    zap = os.environ.get("ZAPISTA_DATA", "") or os.path.expanduser("~/.zapista")
    return os.path.join(zap, "models", "piper")


def get_voice_paths(locale: str, try_fallback: bool = True) -> tuple[str | None, str | None]:
    """
    Retorna (model_path, config_path) para o locale.
    locale: pt-BR, pt-PT, es, en
    Se ficheiros não existirem: tenta path alternativo (pt-PT tugão) ou locale fallback.
    """
    base = tts_models_base()
    voice = PIPER_VOICES.get(locale)
    if not voice:
        if try_fallback and locale in LOCALE_FALLBACK:
            return get_voice_paths(LOCALE_FALLBACK[locale], try_fallback=False)
        return None, None

    def _paths(m: str, c: str) -> tuple[str, str]:
        return os.path.join(base, m), os.path.join(base, c)

    model, config = _paths(voice["model"], voice["config"])
    if Path(model).exists() and Path(config).exists():
        return model, config

    # pt-PT: tentar path unicode (tugão) se encoded (tug%C3%A3o) não existir
    if "model_alt" in voice and "config_alt" in voice:
        m2, c2 = _paths(voice["model_alt"], voice["config_alt"])
        if Path(m2).exists() and Path(c2).exists():
            return m2, c2

    # Fallback para outro locale (ex.: pt_PT → pt_BR)
    if try_fallback and locale in LOCALE_FALLBACK:
        return get_voice_paths(LOCALE_FALLBACK[locale], try_fallback=False)
    return None, None


def resolve_locale_for_audio(chat_id: str, override: str | None) -> str:
    """
    Determina o locale para TTS.
    override: do comando /audio ptpt|es|en (None = usar default do utilizador).
    """
    if override:
        m = override.strip().lower()
        # ptpt, pt-pt -> pt-PT
        if m in ("ptpt", "pt-pt", "pt_pt"):
            return "pt-PT"
        # ptbr, pt-br -> pt-BR
        if m in ("ptbr", "pt-br", "pt_br"):
            return "pt-BR"
        # es, esp, espanhol -> es
        if m in ("es", "esp", "espanol", "español"):
            return "es"
        # en, eng, english -> en
        if m in ("en", "eng", "english"):
            return "en"

    try:
        from backend.user_store import get_user_language
        from backend.database import SessionLocal
        from backend.locale import phone_to_default_language

        db = SessionLocal()
        try:
            lang = get_user_language(db, chat_id)
            if lang:
                return lang
        finally:
            db.close()
    except Exception:
        pass

    return phone_to_default_language(chat_id) or "pt-BR"
