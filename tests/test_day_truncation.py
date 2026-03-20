import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.time_parse import parse_lembrete_time

def test_day_truncation():
    print("\n--- Testing Day Name Truncation Fix ---")
    
    # Test message with "segunda-feira"
    # Original problematic message was likely: "revisão às 10 horas da segunda-feira"
    # or "Tenho revisão do carro às 15 horas da segunda-feira"
    
    text = "Tenho revisão do carro às 15 horas da segunda-feira"
    print(f"Original: {text}")
    
    res = parse_lembrete_time(text)
    msg = res.get("message", "")
    print(f"Extracted message: '{msg}'")
    print(f"Extracted in_seconds: {res.get('in_seconds')}")
    
    # If the bug is fixed, 'segunda-feira' should NOT be partially stripped to '-feira'
    # It should either stay or be removed COMPLETELY if it was part of the time expression.
    
    assert "-feira" not in msg, f"Error: '-feira' suffix left in message: '{msg}'"
    
    # If 'segunda-feira' is used as a date qualifier (which it is here), it might be removed by clean_message.
    # But it must be removed COMPLETELY.
    
    # Test "vontade" vs "vó" (from previous task, just to be sure nothing broke)
    text2 = "lembra que estou com vontade de comer pizza em 1 hora"
    res2 = parse_lembrete_time(text2)
    msg2 = res2.get("message", "")
    print(f"Extracted message 2: '{msg2}'")
    assert "vontade" in msg2, "Error: 'vontade' was accidentally stripped!"

    print("\nVerification Successful: Day names are handled correctly!")

if __name__ == "__main__":
    test_day_truncation()
