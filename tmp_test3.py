import sys, os
sys.path.insert(0, os.path.abspath("."))
from backend.time_parse.core import parse_lembrete_time

for t in [
    "consulta na segunda-feira às 14h30",
    "consulta na segunda feira às 14h30",
    "médico na segunda às 10h",
    "ir à feira na terça"
]:
    print(t, "->", parse_lembrete_time(t, "America/Sao_Paulo"))
