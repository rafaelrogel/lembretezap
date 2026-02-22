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
    r"\b(responde?|responda)\s+(.+?\s+)?(em|por)\s+[a\xe1\xe0\xe2\u00e3]?udio\b",
    r"\b(manda|envia|mande|envie)\s+(.+?\s+)?(me\s+)?[a\xe1\xe0\xe2\u00e3]?udio\b",
    r"\b(em|por)\s+[a\xe1\xe0\xe2\u00e3]?udio\s*(por\s+favor|pf|pfv)?\b",
    r"\bquero\s+(.+?\s+)?[a\xe1\xe0\xe2\u00e3]?udio\b",
    r"\bprefiro\s+(.+?\s+)?[a\xe1\xe0\xe2\u00e3]?udio\b",
    r"\b(responda|responde)\s+(.+?\s+)?por\s+voz\b",
    r"\bfala\s+(comigo|pra\s+mim|com\s+mim)\b",
    r"\b(mensagem|resposta)\s+(.+?\s+)?em\s+[a\xe1\xe0\xe2\u00e3]?udio\b",
    r"\b(voice\s+note|nota\s+de\s+voz)\s*(por\s+favor)?\b",
    r"\bmande\s+(.+?\s+)?por\s+voz\b",
    r"\benvia\s+(.+?\s+)?por\s+voz\b",
    r"\bfale\s+(.+?\s+)?o\s+resultado\b",
    # Espanhol
    r"\b(responde?|responda)\s+(.+?\s+)?(en|por)\s+audio\b",
    r"\b(manda|env[ií]a)\s+(.+?\s+)?(me\s+)?audio\b",
    r"\b(en|por)\s+audio\s*(por\s+favor)?\b",
    r"\bquiero\s+(.+?\s+)?audio\b",
    r"\bh[aá]blame\b",
    r"\bresp[oó]ndeme\s+(.+?\s+)?en\s+audio\b",
    # Inglês
    r"\b(respond|reply)\s+(.+?\s+)?(in|with)\s+audio\b",
    r"\b(send|give)\s+(.+?\s+)?me\s+(an?\s+)?audio\b",
    r"\bin\s+audio\s*(please)?\b",
    r"\bvoice\s+(message|note)\s*(please)?\b",
    r"\bspeak\s+(.+?\s+)?(to\s+me|the\s+answer)\b",
    r"\bi\s+want\s+(.+?\s+)?audio\b",
    r"\bprefer\s+(.+?\s+)?audio\b",
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
