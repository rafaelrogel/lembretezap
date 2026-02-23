
import sys
import os
sys.path.append(os.getcwd())
from backend.reminder_flow import is_vague_date_reminder

def test(msg):
    res = is_vague_date_reminder(msg)
    print(f"Message: '{msg}' -> is_vague_date_reminder: {res}")

test("Me lembre de beber água a cada 2 horas")
test("beber água a cada 2 horas")
test("Lembre-me de beber água amanhã às 10h")
test("Lembre-me de beber água às 10h")
