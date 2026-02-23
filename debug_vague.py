
import sys
import os
sys.path.append(os.getcwd())
from backend.guardrails import is_vague_reminder_message

def test(msg):
    vague = is_vague_reminder_message(msg)
    print(f"Message: '{msg}' -> Vague: {vague}")

test("Beba água!")
test("Beba água")
test("Lembrete")
test("Lembrete amanhã")
test("Remind me to ir ao médico")
