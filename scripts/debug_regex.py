import re
import unicodedata

patterns = [
    r"\b(manda|envia|mande|envie)\s+(.+?\s+)?(me\s+)?[a\xe1\xe0\xe2\u00e3]?udio\b",
    r"\b(manda|envia|mande|envie)\b.*?\b[a\xe1\xe0\xe2\u00e3]?udio\b"
]

text = "manda o áudio"
text_norm = unicodedata.normalize("NFC", text.strip())

for p in patterns:
    match = re.search(p, text_norm, re.I)
    print(f"Pattern: {p}")
    print(f"Match: {bool(match)}")
    if match:
        print(f"Groups: {match.groups()}")
