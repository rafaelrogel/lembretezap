import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add the project root to sys.path
sys.path.append(r"c:\Users\rafae\Documents\Vibecoding\Zapista\lembretezap")

from backend.empathy_positive_messages import get_extra_message_for_reminder

def test_empathy():
    test_cases = [
        ("teste1", "pt-BR", ""),
        ("teste", "pt-BR", "✨ Boa sorte! Concentra-te e vai correr bem."),
        ("médico tomorrow", "pt-BR", "💙 Espero que esteja tudo bem. Se cuide."),
        ("consulta médica", "pt-PT", "💙 Espero que esteja tudo bem. Cuida-te."),
        ("exam results", "en", "💙 Hope the results bring good news. Take care."),
        ("teste de sangue", "pt-PT", ""), # "teste" alone matches, but "teste de sangue" might match "sangue"
        ("sangue", "pt-PT", "💙 Espero que corra tudo bem. Cuida-te."),
    ]

    for content, lang, expected in test_cases:
        result = get_extra_message_for_reminder(content, lang)
        if result == expected:
            print(f"PASS: '{content}' ({lang}) -> '{result}'")
        else:
            print(f"FAIL: '{content}' ({lang}) -> Expected '{expected}', got '{result}'")

if __name__ == "__main__":
    test_empathy()
