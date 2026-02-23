
import sys
import os
sys.path.append(os.getcwd())
from backend.time_parse import parse_lembrete_time

def test(msg):
    res = parse_lembrete_time(msg)
    print(f"Message: '{msg}' -> parse_lembrete_time: {res}")

test("Me lembre de beber água a cada 2 horas")
test("beber água a cada 2 horas")
test("beber água amanhã às 10h")
