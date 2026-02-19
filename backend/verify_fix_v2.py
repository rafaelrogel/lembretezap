
import re
import sys
import os

def test_multilingual_reminders():
    # HANDLERS KEYWORDS
    keywords = (
        "avisar", "avisa", "lembrar", "lembra", "lembrete", "lembre", "anota", "anotar",
        "recuerda", "recuérda", "avisa", "avísa", "remind", "remind me", "be reminded",
        "quero ser lembrado", "quiero que me recuerdes", "quiero ser recordado",
        "i want to be reminded"
    )
    
    test_sentences = [
        "me lembre de beber suco",
        "lembre-me de sair",
        "recuerda comprar pan",
        "remind me to call mom",
        "i want to be reminded at 10",
        "quero ser lembrado amanhã",
        "anotar reunião",
        "avísame a las 5"
    ]
    
    print("--- Testing Multilingual Keywords (Handlers) ---")
    for s in test_sentences:
        sl = s.lower()
        is_rem = any(kw in sl for kw in keywords)
        print(f"'{s}': {'MATCH' if is_rem else 'FAIL'}")

def test_time_patterns():
    # TIME_PARSE PATTERNS (Hoje/Amanhã)
    # r"hoje\s+(?:[àa]s?\s*)?(\d{1,2})(?:h|:)?(\d{2})?\b"
    hoje_pat = r"hoje\s+(?:[àa]s?\s*)?(\d{1,2})(?:h|:)?(\d{2})?\b"
    amanha_pat = r"amanh[ãa]\s+(?:[àa]s?\s*)?(\d{1,2})(?:h|:)?(\d{2})?\b"
    
    cases = [
        "hoje 12h00", "hoje 12:00", "hoje 1200", "hoje às 1200", "hoje às 12h45",
        "amanhã 0900", "amanhã às 1530", "amanha 8", "hoje 14h"
    ]
    
    print("\n--- Testing Today/Tomorrow Patterns (time_parse) ---")
    for c in cases:
        pat = hoje_pat if "hoje" in c else amanha_pat
        m = re.search(pat, c, re.I)
        if m:
            h = int(m.group(1))
            mn = int(m.group(2) or 0)
            print(f"'{c}' -> {h:02d}:{mn:02d}")
        else:
            print(f"'{c}' -> NO MATCH")

    # REMINDER_FLOW PATTERNS
    hour_patterns = (
        r"\d{1,2}\s*h(?:oras?)?\b",
        r"\d{1,2}:\d{2}",
        r"\d{1,2}h\d{0,2}\b",
        r"às?\s*\d{1,2}(?:[:h]\d{2})?",
        r"as\s*\d{1,2}(?:[:h]\d{2})?",
        r"(?:às?|as)\s*\d{4}\b",
        r"\b\d{2}h\d{2}?\b",
        r"\b\d{4}\b",
    )
    combined_hour = "|".join(hour_patterns)
    
    test_hours = ["às 1200", "as 1530", "1200", "12h45", "às 5h30", "10:00"]
    print("\n--- Testing Hour Detection (reminder_flow) ---")
    for th in test_hours:
        m = re.search(combined_hour, th, re.I)
        print(f"'{th}': {'MATCH' if m else 'FAIL'}")

    # TIME RESPONSE EXTRACTION
    # (r"^(\d{4})$", lambda m: (int(m.group(1)[:2]), int(m.group(1)[2:])))
    response_pats = [
        (r"(?:às?|as)\s*(\d{1,2})(?:[:h])?(\d{2})?\b", lambda m: (int(m.group(1)), int(m.group(2) or 0))),
        (r"^(\d{4})$", lambda m: (int(m.group(1)[:2]), int(m.group(1)[2:]))),
    ]
    
    print("\n--- Testing Response Extraction ---")
    extract_cases = ["às 1200", "as 0830", "1200", "0945"]
    for ec in extract_cases:
        matched = False
        for p, ex in response_pats:
            m = re.search(p, ec, re.I)
            if m:
                h, mn = ex(m)
                print(f"'{ec}' -> {h:02d}:{mn:02d}")
                matched = True
                break
        if not matched:
            print(f"'{ec}' -> NO MATCH")

if __name__ == "__main__":
    test_multilingual_reminders()
    test_time_patterns()
