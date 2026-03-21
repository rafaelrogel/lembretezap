from backend.reminder_keywords import ALL_REMINDER_KEYWORDS

t = "o que tenho amanhã?".lower()
matches = [kw for kw in ALL_REMINDER_KEYWORDS if kw in t]
print(f"Matches for '{t}':")
for m in matches:
    print(f" - '{m}'")

t2 = "amanhã".lower()
matches2 = [kw for kw in ALL_REMINDER_KEYWORDS if kw in t2]
print(f"\nMatches for '{t2}':")
for m in matches2:
    print(f" - '{m}'")
