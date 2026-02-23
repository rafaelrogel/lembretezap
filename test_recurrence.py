
import sys
import os
sys.path.append(os.getcwd())
try:
    from backend.recurring_event_flow import has_recurrence_indicator
except ImportError:
    # If not in that file, try reminder_flow (wait, it's in recurring_event_flow)
    pass

def test(msg):
    try:
        res = has_recurrence_indicator(msg)
        print(f"Message: '{msg}' -> has_recurrence_indicator: {res}")
    except Exception as e:
        print(f"Error: {e}")

test("Me lembre de beber água a cada 2 horas")
test("beber água a cada 2 horas")
test("toda segunda")
test("amanhã")
