#!/bin/bash
# 🔧 Zapista WAL Mode Initialization Script
# This script ensures the SQLite database is configured with WAL mode for high concurrency.

DB_FILE=${ZAPISTA_DATA:-/root/.zapista}/organizer.db

echo "🔧 Checking SQLite configuration for: $DB_FILE"

if [ ! -f "$DB_FILE" ]; then
    echo "⚠️ Database file not found at $DB_FILE. It will be created on first start."
    exit 0
fi

# Enable WAL Mode and optimize performance
# WAL: Write-Ahead Logging for concurrency
# synchronous=NORMAL: Balance between speed and safety
# cache_size=10000: Increase cache for frequent reads
sqlite3 "$DB_FILE" "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA cache_size=10000;"

STATUS=$(sqlite3 "$DB_FILE" "PRAGMA journal_mode;")
echo "✅ WAL Mode is currently: $STATUS"
