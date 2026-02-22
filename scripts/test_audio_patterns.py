import sys
import os
import unicodedata

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from backend.audio_request import detects_audio_request
except ImportError as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

def test(text):
    match = detects_audio_request(text)
    print(f"[{'✅' if match else '❌'}] {text}")

phrases = [
    "mande em áudio",
    "responde por áudio",
    "mande a lista em áudio",
    "manda áudio da cheesecake",
    "envia a receita por áudio",
    "fala comigo",
    "me responde em áudio por favor",
    "quero a resposta em áudio",
    "manda o áudio",
    "mande me um áudio",
    "envia-me áudio", # This might fail due to hyphen
    "Me manda o link em áudio",
]

for p in phrases:
    test(p)
