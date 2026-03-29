import asyncio
from backend.time_parse.core import parse_lembrete_time

def test():
    cases = [
        "amanha tenho dentista as 10h00",
        "dia 12 de maio vou ao médico às 15h30",
        "terça-feira tenho uma call às 14h00",
        "quinta-feira trabalho em casa às 9h",
        "toda sexta-feira tomo uma cerveja às 18h",
        "hoje vou correr as 18h" # rule 1 or 2
    ]
    
    for case in cases:
        out = parse_lembrete_time(case, "Europe/Lisbon")
        print(f"[{case}] =>", out)

if __name__ == "__main__":
    test()
