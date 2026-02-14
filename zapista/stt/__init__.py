"""Speech-to-text module for voice message transcription.

Supports:
- whisper.cpp (local, optional)
- OpenAI (fallback quando local falha; mesma API do install)
"""

from zapista.stt.transcriber import transcribe

__all__ = ["transcribe"]
