import sys
import os
sys.path.insert(0, os.path.abspath("."))
from backend.time_parse.core import parse_lembrete_time
print(parse_lembrete_time("consulta na segunda-feira às 14h30", "America/Sao_Paulo"))
