"""
Detecta quando o utilizador pede resposta em áudio (em linguagem natural).
Ex.: "responde em áudio", "manda áudio", "fala comigo", "respond in audio".
Usado para ativar TTS (audio_mode) quando o utilizador pede resposta em áudio por texto ou áudio.
"""

import re
import unicodedata


# Padrões que indicam pedido de resposta em áudio
# a\xe1 = á (evita problemas de encoding no source)
_AUDIO_REQUEST_PATTERNS = [
    # Português (áudio, audio) — [aáàâ] evita capturar "video"
    r"\b(?:me\s+)?(?:responde?|responda)\s+(?:.+?\s+)?(?:em|por)\s+[a\xe1\xe0\xe2\u00e3]?udio\b",
    r"\b(?:manda|envia|mande|envie|solta)\s+(?:.+?\s+)?(?:me\s+)?(?:o\s+)?[a\xe1\xe0\xe2\u00e3]?udio\b",
    r"\b(?:em|por)\s+[a\xe1\xe0\xe2\u00e3]?udio\s*(?:por\s+favor|pf|pfv)?\b",
    r"\b(?:quero|prefiro|pode\s+ser)\s+(?:.+?\s+)?[a\xe1\xe0\xe2\u00e3]?udio\b",
    r"\b(?:responda|responde)\s+(?:.+?\s+)?por\s+voz\b",
    r"\bfala\s+(?:comigo|pra\s+mim|com\s+mim)\b",
    r"\b(?:mensagem|resposta)\s+(?:.+?\s+)?em\s+[a\xe1\xe0\xe2\u00e3]?udio\b",
    r"\b(?:voice\s+note|nota\s+de\s+voz|mensagem\s+de\s+voz)\b",
    r"\b(?:mande|manda|envie|envia)\s+(?:.+?\s+)?por\s+voz\b",
    r"\b(?:fale|fala)\s+(?:.+?\s+)?(?:o\s+)?(?:resultado|texto|lembrete)\b",
    # Espanhol
    r"\b(?:me\s+)?(?:responde?|responda)\s+(?:.+?\s+)?(?:en|por)\s+audio\b",
    r"\b(?:manda|env[ií]a)\s+(?:.+?\s+)?(?:me\s+)?audio\b",
    r"\b(?:en|por)\s+audio\s*(?:por\s+favor)?\b",
    r"\b(?:quiero|prefiero)\s+(?:.+?\s+)?audio\b",
    r"\bh[aá]blame\b",
    r"\bresp[oó]ndeme\s+(?:.+?\s+)?en\s+audio\b",
    r"\b(?:nota\s+de\s+voz|mensaje\s+de\s+voz)\b",
    # Inglês
    r"\b(?:respond|reply)\s+(?:.+?\s+)?(?:in|with)\s+audio\b",
    r"\b(?:send|give)\s+(?:.+?\s+)?me\s+(?:an?\s+)?audio\b",
    r"\bin\s+audio\s*(?:please)?\b",
    r"\bvoice\s+(?:message|note)\s*(?:please)?\b",
    r"\bspeak\s+(?:.+?\s+)?(?:to\s+me|the\s+answer)\b",
    r"\b(?:i\s+want|i\s+prefer)\s+(?:.+?\s+)?audio\b",
]
_AUDIO_REQUEST_RE = re.compile("|".join(_AUDIO_REQUEST_PATTERNS), re.I)


def detects_audio_request(content: str | None) -> bool:
    """
    True se a mensagem indica que o utilizador quer resposta em áudio.
    Ex.: "responde em áudio, lembrete amanhã", "manda áudio por favor", "fala comigo".
    """
    if not content or not content.strip():
        return False
    # Normalizar Unicode (ex.: á como NFC para consistência)
    try:
        text = unicodedata.normalize("NFC", content.strip())
    except Exception:
        text = content.strip()
    return bool(_AUDIO_REQUEST_RE.search(text))
