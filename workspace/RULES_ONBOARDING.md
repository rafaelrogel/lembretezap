# Onboarding (name, city, timezone)

- **MANDATORY QUESTION**: In the first interaction (after greeting), ALWAYS ask: "What time is it there now?" (or "Que horas são aí agora?").
- Use the answer to validate the timezone AND check if the system clock is correct.
- If the user does not answer the registration questions correctly, the system uses default values and continues.
- City is important for reminder times; if they don't want to provide it, we use the timezone inferred from the phone number.
- /reset allowed to redo registration at any time.
- We respect LGPD/GDPR: we only store the essential.
- **WhatsApp Reminder Reactions:** 👍 = done (confirms with yes); ⏰ = snooze (delay 5 min, max 3x); 👎 = remove (we ask if they want to change the time or cancel). They can also write/send audio (e.g., "done", "remove").
