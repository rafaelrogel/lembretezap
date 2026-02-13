# Available Tools

This document describes the tools available to zapista.

## Communication

### message
Send a message to the user (used internally).
```
message(content: str, channel: str = None, chat_id: str = None) -> str
```

## Scheduled Reminders (Cron)

Use `zapista cron` commands to create and manage scheduled reminders:

### Set a recurring reminder
```bash
# Every day at 9am
zapista cron add --name "morning" --message "Good morning! ☀️" --cron "0 9 * * *"

# Every 2 hours
zapista cron add --name "water" --message "Drink water! 💧" --every 7200
```

### Set a one-time reminder
```bash
# At a specific time (ISO format)
zapista cron add --name "meeting" --message "Meeting starts now!" --at "2025-01-31T15:00:00"
```

### Manage reminders
```bash
zapista cron list              # List all jobs
zapista cron remove <job_id>   # Remove a job
```

## Heartbeat

The `HEARTBEAT.md` file in the workspace is checked every 30 minutes by the service. Edit this file manually on disk to add or remove periodic tasks.
