"""Speech-to-text module for voice message transcription.

Supports:
- whisper.cpp (local, optional)
- Groq / OpenAI as fallback
"""

from zapista.stt.transcriber import transcribe

__all__ = ["transcribe"]
