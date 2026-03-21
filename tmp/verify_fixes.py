
import sys
import os
import re
from datetime import datetime

# Add the project root to sys.path
sys.path.append(r'c:\Users\rafae\Documents\Vibecoding\Zapista\lembretezap')

from backend.recurring_event_flow import parse_recurring_schedule, parse_end_date_response
from backend.handlers.lembrete import _looks_like_new_reminder_request

def test_parse_recurring():
    print("Testing parse_recurring_schedule...")
    cases = [
        ("a cada 2 horas: fazer uma pausa", "fazer uma pausa", "every:7200"),
        ("cada 30 min: tomar água", "tomar água", "every:1800"),
        ("every 2 hours: check email", "check email", "every:7200"),
        ("cada dia beber agua", "beber agua", "every:86400"),
        ("cada vez que 1 hora passa", "passa", "every:3600"), # A bit loose but okay
    ]
    for text, expected_msg, expected_cron in cases:
        res = parse_recurring_schedule(text)
        if res:
            msg, cron, h, m = res
            if msg == expected_msg and cron == expected_cron:
                print(f"PASS: '{text}' -> msg='{msg}', cron='{cron}'")
            else:
                print(f"FAIL: '{text}' -> expected msg='{expected_msg}', cron='{expected_cron}'; got msg='{msg}', cron='{cron}'")
        else:
            print(f"FAIL: '{text}' did not match any pattern")
            # Debug match
            tl = text.lower()
            cadence_pat = r"(?:a\s+)?(?:cada|every|cada\s+vez\s+que)\s+(\d+)\s*(hor[as]|min[uto]s?|seg[undo]s?|hour?s|min?s|day?s|dia[s]|semanas?|weeks?)\b"
            import re
            m = re.search(cadence_pat, tl, re.I)
            if m:
                print(f"  [DEBUG] Regex matched: {m.groups()}")
            else:
                print(f"  [DEBUG] Regex did NOT match: {cadence_pat}")

def test_parse_end_date():
    print("\nTesting parse_end_date_response...")
    cases = [
        ("até o fim de 2028", "year:2028"),
        ("fim de 2028", "year:2028"),
        ("final de 2030", "year:2030"),
        ("until end of 2027", "year:2027"),
        ("até o fim do ano", "fim_ano"),
        ("end of year", "fim_ano"),
    ]
    for text, expected in cases:
        res = parse_end_date_response(text)
        if res == expected:
            print(f"PASS: '{text}' -> {res}")
        else:
            print(f"FAIL: '{text}' -> expected {expected}, got {res}")

def test_looks_like_new():
    print("\nTesting _looks_like_new_reminder_request...")
    cases = [
        ("a cada 2 horas: fazer uma pausa", True),
        ("todo dia às 8h", True),
        ("sim", False),
        ("2 horas", False),
        ("/lembrete algo", True),
    ]
    for text, expected in cases:
        res = _looks_like_new_reminder_request(text)
        if res == expected:
            print(f"PASS: '{text}' -> {res}")
        else:
            print(f"FAIL: '{text}' -> expected {expected}, got {res}")

if __name__ == "__main__":
    test_parse_recurring()
    test_parse_end_date()
    test_looks_like_new()
