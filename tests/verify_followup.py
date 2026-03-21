
import asyncio
import sys
import os

# Ajustar path para importar backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.pending_confirmation import last_assistant_asked_when, looks_like_time_response

def test_prompts():
    print("--- Testing last_assistant_asked_when ---")
    prompts = [
        "A que horas é?", # PT generic
        "¿A qué hora es?", # ES generic
        "What time is it?", # EN generic
        "Que dia é? Amanhã? Hoje? Segunda?", # PT date generic
        "¿Qué día es? ¿Mañana? ¿Hoy? ¿Lunes?", # ES date generic
        "What day is it? Tomorrow? Today? Monday?", # EN date generic
        "Quando queres o lembrete? Ex: em 10 min, amanhã às 8h, todo dia às 10h ou a cada 2h.", # PT recurrence
        "¿Cuándo quieres el recordatorio? Ej: en 10 min, mañana a las 8h, cada día a las 10h o cada 2h.", # ES recurrence
        "When do you want the reminder? E.g. in 10 min, tomorrow at 8am, every day at 10am or every 2h.", # EN recurrence
    ]
    
    for p in prompts:
        ok = last_assistant_asked_when(p)
        print(f"[{'OK' if ok else 'FAIL'}] Prompt: {p}")

def test_time_responses():
    print("\n--- Testing looks_like_time_response ---")
    responses = [
        "todo dia 8h",
        "cada d[ií]a 10h",
        "tomorrow 9am",
        "mañana a las 15h",
        "every day at 8",
        "at 10:30pm",
        "a cada 2 horas",
    ]
    
    for r in responses:
        ok = looks_like_time_response(r)
        print(f"[{'OK' if ok else 'FAIL'}] Response: {r}")

def test_advance_responses():
    print("\n--- Testing parse_advance_seconds ---")
    from backend.reminder_flow import parse_advance_seconds
    responses = [
        "30 min",
        "1 hora",
        "1 hora antes",
        "meia hora",
        "30 minutos antes",
        "1 hr before",
    ]
    
    for r in responses:
        sec = parse_advance_seconds(r)
        print(f"[{'OK' if sec else 'FAIL'}] Advance: {r} -> {sec}s")

if __name__ == "__main__":
    test_prompts()
    test_time_responses()
    test_advance_responses()
