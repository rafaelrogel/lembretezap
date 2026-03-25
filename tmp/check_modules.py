import sys
import os
from pathlib import Path
import sqlite3
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

print(f"🐍 Python version: {sys.version}")
print(f"📂 Current Dir: {os.getcwd()}")
print(f"📦 Python Path: {sys.path}")

def check_import(module_path):
    try:
        if "." in module_path:
            pkg, mod = module_path.split(".", 1)
            # Simular importação aninhada
            from importlib import import_module
            import_module(module_path)
        else:
            __import__(module_path)
        print(f"✅ {module_path}: OK")
    except Exception as e:
        print(f"❌ {module_path}: FAILED ({e})")

print("\n🔍 Checking Modules:")
check_import("zapista.clock_drift")
check_import("backend.bookmark")

print("\n🗄️ Checking SQLite:")
print(f"SQLite Version: {sqlite3.sqlite_version}")
v = tuple(map(int, sqlite3.sqlite_version.split(".")))
if v < (3, 9, 0):
    print("⚠️ SQLite < 3.9: Native JSON support might be missing!")
else:
    print("✅ SQLite >= 3.9: Native JSON support is present.")

# Test code drift if present
try:
    from zapista.clock_drift import get_effective_time
    print(f"🕒 Effective Time: {datetime.fromtimestamp(get_effective_time())}")
except Exception as e:
    print(f"❌ Clock Drift test failed: {e}")

# Test bookmark migration if present
try:
    from backend.bookmark import migrate_notes_to_bookmarks
    print("📚 Bookmark module found, migrate_notes_to_bookmarks is present.")
except Exception as e:
    print(f"❌ Bookmark migration test failed: {e}")
