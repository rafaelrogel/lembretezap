import sqlite3
import hashlib
import random
from datetime import datetime, timedelta

DB_PATH = "organizer.db"

def generate_test_users(count: int = 100):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for i in range(1, count + 1):
        phone = f"+55{i:011d}"
        phone_hash = hashlib.sha256(phone.encode()).hexdigest()
        phone_truncated = phone[:6] + "***" + phone[-4:]

        cursor.execute("""
            INSERT OR IGNORE INTO users (phone_hash, phone_truncated, created_at)
            VALUES (?, ?, ?)
        """, (phone_hash, phone_truncated, datetime.now()))

    conn.commit()
    conn.close()
    print(f"Generated {count} test users")

def generate_test_lists(user_id: int, count: int = 5):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    list_names = ["Mercado", "Pendentes", "Receitas", "Compras", "Tarefas"]

    for i in range(count):
        name = random.choice(list_names) + f" {i+1}"
        cursor.execute("""
            INSERT INTO lists (user_id, name, created_at)
            VALUES (?, ?, ?)
        """, (user_id, name, datetime.now()))

        list_id = cursor.lastrowid

        for j in range(random.randint(3, 10)):
            text = f"Item {j+1}"
            cursor.execute("""
                INSERT INTO list_items (list_id, text, done, position)
                VALUES (?, ?, ?, ?)
            """, (list_id, text, random.choice([0, 0, 0, 1]), j))

    conn.commit()
    conn.close()
    print(f"Generated {count} test lists for user {user_id}")

def generate_test_events(user_id: int, count: int = 20):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tipos = ["lembrete", "evento", "filme", "livro"]

    for i in range(count):
        tipo = random.choice(tipos)
        data_at = datetime.now() + timedelta(days=random.randint(1, 30))
        payload = {
            "nome": f"Test {tipo} {i+1}",
            "data": data_at.isoformat()
        }

        cursor.execute("""
            INSERT INTO events (user_id, tipo, payload, data_at, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, tipo, str(payload), data_at, datetime.now()))

    conn.commit()
    conn.close()
    print(f"Generated {count} test events for user {user_id}")

if __name__ == "__main__":
    generate_test_users(100)
    for user_id in range(1, 21):
        generate_test_lists(user_id)
        generate_test_events(user_id)
