"""
Final functional test for backend/time_parse/core.py after the fix.
Run from inside the lembretezap directory with:
    python -X utf8 final_test.py
"""
import sys, os
sys.path.insert(0, os.getcwd())

# Patch clock_drift to avoid DB/network calls
import types
mock_module = types.ModuleType("zapista.clock_drift")
import time as _time
mock_module.get_effective_time = _time.time
sys.modules["zapista"] = types.ModuleType("zapista")
sys.modules["zapista.clock_drift"] = mock_module

from backend.time_parse.core import parse_lembrete_time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time

tz = "Europe/Lisbon"
now = datetime.fromtimestamp(time.time(), tz=ZoneInfo(tz))

tests = [
    # (text,                           exp_h, exp_m,   day_offset, description)
    ("amanh\u00e3 \u00e0s 06h50",        6, 50, 1,  "PT: amanha + time after"),
    ("cedo amanh\u00e3, \u00e0s 08h00",  8,  0, 1,  "PT: adjective + amanha + comma + time"),
    ("\u00e0s 04h00 amanh\u00e3",         4,  0, 1,  "PT: time before amanha"),
    ("ma\u00f1ana a las 10:30",          10, 30, 1,  "ES: manana + time after"),
    ("a las 10:30 ma\u00f1ana",          10, 30, 1,  "ES: time before manana"),
    ("tomorrow at 08:00",               8,  0, 1,  "EN: tomorrow + time after"),
    ("at 08:00 tomorrow",               8,  0, 1,  "EN: time before tomorrow"),
    ("tomorrow at 8pm",                20,  0, 1,  "EN: tomorrow + 8pm"),
]

all_ok = True
print(f"Current time in Lisbon: {now.strftime('%Y-%m-%d %H:%M %Z')}\n")

for text, exp_h, exp_m, day_offset, desc in tests:
    try:
        res = parse_lembrete_time(text, tz_iana=tz)
        if "in_seconds" in res:
            target = now + timedelta(seconds=res["in_seconds"])
            ok = (target.hour == exp_h and target.minute == exp_m)
            status = "\u2705" if ok else "\u274c"
            info = f"-> {target.strftime('%Y-%m-%d %H:%M')} (expected tomorrow {exp_h:02d}:{exp_m:02d})"
        else:
            ok = False
            status = "\u274c"
            info = f"-> no in_seconds: {res}"
        print(f"  {status} [{desc}] '{text}' {info}")
        if not ok:
            all_ok = False
    except Exception as e:
        print(f"  \u274c [{desc}] '{text}' -> ERROR: {e}")
        all_ok = False

print()
print("\u2705 All tests passed!" if all_ok else "\u274c SOME TESTS FAILED!")
sys.exit(0 if all_ok else 1)
