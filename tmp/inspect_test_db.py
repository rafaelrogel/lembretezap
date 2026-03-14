import sqlite3
import os
from pathlib import Path

db_path = Path("c:/Users/rafae/Documents/Vibecoding/Zapista/lembretezap/test_isolated.db")
if not db_path.exists():
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("\n--- ALL LIST ITEMS (NOT DONE) ---")
cursor.execute("""
    SELECT li.id, li.text, li.done, l.name as list_name, l.user_id 
    FROM list_items li 
    JOIN lists l ON li.list_id = l.id 
    WHERE li.done = 0
""")
for i in cursor.fetchall():
    print(f"ID: {i['id']}, Text: {i['text']}, List: {i['list_name']}, UserID: {i['user_id']}")

print("\n--- ALL AUDIT LOGS (LAST 20) ---")
cursor.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 20")
for l in cursor.fetchall():
    print(f"Action: {l['action']}, User: {l['user_id']}, Payload: {l['payload_json']}")

conn.close()
