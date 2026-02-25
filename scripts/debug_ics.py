import icalendar

def _normalize_ics_content(raw: str) -> str:
    if not raw:
        return raw
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    while "\n " in raw:
        raw = raw.replace("\n ", " ")
    raw = raw.replace("\x00", "")
    return raw.strip()

SAMPLE_ICS = """
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
SUMMARY:Consulta medico
DTSTART:20250610T090000Z
DTEND:20250610T093000Z
LOCATION:Clinica Central
DESCRIPTION:Check-up anual
END:VEVENT
END:VCALENDAR
""".strip()

norm = _normalize_ics_content(SAMPLE_ICS)
print(f"Normalized length: {len(norm)}")
cal = icalendar.Calendar.from_ical(norm)
count = 0
for component in cal.walk():
    if component.name == "VEVENT":
        count += 1
print(f"Total VEVENTs after normalization: {count}")
