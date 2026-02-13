"""
Passagens de livros sagrados via APIs gratuitas.
Apenas quando o cliente pede diretamente. Incluir confirmação e lembrete do organizador.

APIs: bible-api.com (Bíblia), api.alquran.cloud (Alcorão).
Bhagavad Gita: bhagavadgita.io requer API key; vedicscriptures.github.io pode ser alternativa.
"""

import random
import re
import urllib.request
import json
from typing import Any

# Bible: bible-api.com (gratuita, sem API key)
# Traduções: almeida (PT), web (EN). Não há espanhol; es → web.
BIBLE_API = "https://bible-api.com"
BIBLE_BY_LANG = {"pt-PT": "almeida", "pt-BR": "almeida", "es": "web", "en": "web"}

# Quran: api.alquran.cloud (gratuita). pt.elhayek, es.cortes, en.sahih. Árabe só se pedir.
QURAN_API = "https://api.alquran.cloud/v1"
QURAN_BY_LANG = {"pt-PT": "pt.elhayek", "pt-BR": "pt.elhayek", "es": "es.cortes", "en": "en.sahih"}
QURAN_ARABIC = "quran-simple"  # só quando cliente pedir em árabe

# Referências para «versículo aleatório» da Bíblia
BIBLE_RANDOM_REFS = [
    "genesis 1:1", "psalms 23:1", "john 3:16", "matthew 5:3-4", "proverbs 3:5",
    "romans 8:28", "philippians 4:13", "isaiah 41:10", "jeremiah 29:11",
    "psalms 46:1", "matthew 11:28", "john 14:27", "colossians 3:23",
]

# Surahs do Alcorão com número de ayahs (para random)
QURAN_SURAHS = [
    (1, 7), (2, 286), (3, 200), (4, 176), (5, 120), (6, 165), (7, 206),
    (8, 75), (9, 129), (10, 109), (18, 110), (19, 98), (36, 83),
    (55, 78), (67, 30), (78, 40), (112, 4), (113, 5), (114, 6),
]


def _fetch_json(url: str, timeout: int = 10) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "zapista/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def fetch_bible_verse(reference: str, translation: str = "web") -> dict | None:
    """
    Obtém versículo da Bíblia. reference: "john 3:16" ou "genesis 1:1".
    translation: web (EN), almeida (PT), kjv, etc.
    Retorna {reference, text} ou None.
    """
    url = f"{BIBLE_API}/{reference.replace(' ', '%20')}?translation={translation}"
    data = _fetch_json(url)
    if not data or "text" not in data:
        return None
    return {
        "reference": data.get("reference", reference),
        "text": (data.get("text") or "").strip(),
    }


def fetch_bible_random(translation: str = "web") -> dict | None:
    """Versículo aleatório da Bíblia. translation: web (EN), almeida (PT)."""
    ref = random.choice(BIBLE_RANDOM_REFS)
    return fetch_bible_verse(ref, translation)


def fetch_quran_verse(surah: int, ayah: int, edition: str = "en.sahih") -> dict | None:
    """
    Obtém versículo do Alcorão. surah 1-114, ayah 1-N.
    edition: en.sahih, pt.elhayek, es.cortes, quran-simple (árabe).
    Retorna {surah, ayah, text, surah_name} ou None.
    """
    url = f"{QURAN_API}/ayah/{surah}/{ayah}/{edition}"
    data = _fetch_json(url)
    if not data or data.get("code") != 200:
        return None
    d = data.get("data") or {}
    text = (d.get("text") or "").strip()
    surah_info = d.get("surah") or {}
    surah_name = surah_info.get("englishName") or f"Surah {surah}"
    return {
        "surah": surah,
        "ayah": ayah,
        "text": text,
        "surah_name": surah_name,
    }


def fetch_quran_random(edition: str = "en.sahih") -> dict | None:
    """Versículo aleatório do Alcorão. edition: en.sahih, pt.elhayek, es.cortes, quran-simple."""
    surah_num, num_ayahs = random.choice(QURAN_SURAHS)
    ayah = random.randint(1, min(num_ayahs, 50))  # evita ayahs muito longas em suras grandes
    return fetch_quran_verse(surah_num, ayah, edition)


def parse_bible_reference(text: str) -> str | None:
    """
    Extrai referência bíblica do texto. Ex: "joão 3 16" -> "john 3:16"
    Mapeamento PT/EN simplificado.
    """
    t = (text or "").strip().lower()
    # Padrão: livro capítulo:verso ou livro capítulo versículo
    m = re.search(r"(?:b[ií]blia|bible)\s+(.+?)(?:\?|$)", t)
    if m:
        ref = m.group(1).strip()
    else:
        m = re.search(r"(?:passagem|vers[ií]culo)\s+(?:da\s+)?(?:b[ií]blia|bible)[:\s]+(.+?)(?:\?|$)", t)
        if m:
            ref = m.group(1).strip()
        else:
            return None
    if not ref:
        return None
    # Normalizar: livro capítulo versículo -> livro capitulo:versiculo
    ref = re.sub(r"\s+", " ", ref)
    parts = re.split(r"[\s:]+", ref, 2)
    if len(parts) >= 2:
        book = parts[0]
        ch = parts[1]
        verse = parts[2] if len(parts) > 2 else "1"
        # Livros PT -> EN (parcial)
        book_map = {
            "gênesis": "genesis", "genesis": "genesis",
            "joão": "john", "john": "john", "joh": "john",
            "mateus": "matthew", "matthew": "matthew", "mat": "matthew",
            "salmos": "psalms", "psalms": "psalms", "psalm": "psalms",
            "provérbios": "proverbs", "proverbs": "proverbs",
            "romanos": "romans", "romans": "romans",
            "filipenses": "philippians", "philippians": "philippians",
            "isaías": "isaiah", "isaiah": "isaiah",
            "jeremias": "jeremiah", "jeremiah": "jeremiah",
        }
        book_lower = book.lower()
        book_en = book_map.get(book_lower, book_lower)
        return f"{book_en} {ch}:{verse}"
    return None


def get_bible_translation(user_lang: str | None) -> str:
    """Retorna identifier da tradução conforme idioma registado."""
    if not user_lang:
        return "web"
    return BIBLE_BY_LANG.get(user_lang, "web")


def get_quran_edition(user_lang: str | None, want_arabic: bool = False) -> str:
    """Retorna identifier da edição conforme idioma. want_arabic=True se cliente pediu em árabe."""
    if want_arabic:
        return QURAN_ARABIC
    if not user_lang:
        return "en.sahih"
    return QURAN_BY_LANG.get(user_lang, "en.sahih")


def wants_quran_arabic(text: str) -> bool:
    """True se o cliente pediu explicitamente em árabe."""
    if not text:
        return False
    t = text.strip().lower()
    return bool(re.search(r"(?:em\s+)?[áa]rabe|(?:in\s+)?arabic|(?:en\s+)?[áa]rabe", t))


def parse_quran_reference(text: str) -> tuple[int, int] | None:
    """
    Extrai referência do Alcorão. Ex: "sura 2 versículo 255" ou "2:255"
    Retorna (surah, ayah) ou None.
    """
    t = (text or "").strip().lower()
    m = re.search(r"(\d{1,3})[:\s]+(\d{1,3})", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(?:sura|surah)\s*(\d{1,3})[,\s]+(?:ayah|vers[ií]culo|verso)\s*(\d{1,3})", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def build_sacred_response(book: str, data: dict | None, reminder: str) -> str:
    """Constrói resposta com passagem + lembrete do organizador."""
    if not data:
        return f"Não consegui obter a passagem agora. Tenta mais tarde. {reminder}"

    if book == "bible":
        ref = data.get("reference", "")
        text = data.get("text", "")
        return f"**Bíblia — {ref}**\n\n{text}\n\n_{reminder}_"
    if book == "quran":
        surah = data.get("surah", "")
        ayah = data.get("ayah", "")
        surah_name = data.get("surah_name", "")
        text = data.get("text", "")
        return f"**Alcorão — {surah_name} {surah}:{ayah}**\n\n{text}\n\n_{reminder}_"
    return reminder
