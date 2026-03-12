import sqlite3
import os
from pathlib import Path

db_path = Path.home() / ".zapista" / "organizer.db"
if not db_path.exists():
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- RECENT USERS ---")
cursor.execute("SELECT id, phone_truncated, phone_hash FROM users ORDER BY id DESC LIMIT 5")
users = cursor.fetchall()
for u in users:
    print(f"ID: {u['id']}, Phone: {u['phone_truncated']}, Hash: {u['phone_hash'][:8]}...")

print("\n--- RECENT AUDIT LOGS ---")
cursor.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 20")
logs = cursor.fetchall()
for l in logs:
    print(f"ID: {l['id']}, User: {l['user_id']}, Action: {l['action']}, Resource: {l['resource']}, Payload: {l['payload_json']}")

print("\n--- CURRENT LIST ITEMS ---")
cursor.execute("""
    SELECT li.id, li.text, l.name as list_name, u.phone_truncated 
    FROM list_items li 
    JOIN lists l ON li.list_id = l.id 
    JOIN users u ON l.user_id = u.id 
    WHERE li.done = 0
    ORDER BY li.id DESC LIMIT 20
""")
items = cursor.fetchall()
for i in items:
    print(f"ID: {i['id']}, Text: {i['text']}, List: {i['list_name']}, User: {i['phone_truncated']}")

conn.close()
