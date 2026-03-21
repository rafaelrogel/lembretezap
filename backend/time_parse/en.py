"""English language constants for time parsing."""

DIAS_SEMANA = {
    "monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4, "friday": 5, "saturday": 6, "sunday": 0,
    "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 0,
}

MESES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"
]

RE_IN = r"in\s+(\d+)\s*(minutes?|min|hours?|hr|days?)\b"

AM_PM_MODIFIERS = [
    r"in\s+the\s+(?:morning|afternoon|evening)",
    r"at\s+night",
    r"a\.?m\.?",
    r"p\.?m\.?"
]
