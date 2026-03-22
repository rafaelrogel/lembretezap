import re

def test(text, word):
    pat = rf"\b{re.escape(word)}\b"
    m = re.search(pat, text, re.I)
    print(f"Text: '{text}', Word: '{word}' -> Match: {bool(m)}")

test("consulta na segunda-feira às 14h30", "segunda-feira")
test("consulta na segunda-feira às 14h30", "segunda")
test("consulta na segunda feira às 14h30", "segunda-feira")
test("consulta na segunda feira às 14h30", "segunda")
