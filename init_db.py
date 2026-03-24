import os
os.environ["ZAPISTA_ENV"] = "test"
from backend.database import init_db
init_db()
print("DB Initialized")
