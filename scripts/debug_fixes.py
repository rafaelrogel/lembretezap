import os
import shutil
from pathlib import Path
from zapista.tts.config import tts_enabled, piper_bin, tts_max_words
from zapista.config.loader import get_data_dir
from zapista.utils.helpers import safe_filename, ensure_dir

def check_tts():
    print(f"TTS_ENABLED: {os.environ.get('TTS_ENABLED')}")
    print(f"PIPER_BIN: {os.environ.get('PIPER_BIN')}")
    print(f"TTS_MODELS_BASE: {os.environ.get('TTS_MODELS_BASE')}")
    print(f"tts_enabled() result: {tts_enabled()}")
    print(f"piper_bin() result: {piper_bin()}")
    
    bin_path = piper_bin()
    if bin_path:
        p = Path(bin_path)
        print(f"Piper binary exists: {p.exists()}")
    else:
        print("Piper binary not configured in env.")

def check_nuke_logic():
    workspace = get_data_dir()
    chat_id = "test_user_123@s.whatsapp.net"
    session_key = f"whatsapp:{chat_id}"
    
    # 1. Simulate file creation
    safe_key = safe_filename(str(session_key).strip().replace(":", "_"))
    memory_dir = workspace / "memory" / safe_key
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "MEMORY.md").write_text("dummy memory")
    
    from backend.client_memory import get_client_memory_file_path
    user_file = get_client_memory_file_path(workspace, chat_id)
    user_file.parent.mkdir(parents=True, exist_ok=True)
    user_file.write_text("dummy profile")
    
    print(f"Memory dir exists before: {memory_dir.exists()}")
    print(f"User file exists before: {user_file.exists()}")
    
    # 2. Simulate deletion (subset of nuke_all logic)
    if safe_key:
        if memory_dir.exists() and memory_dir.is_dir():
            shutil.rmtree(memory_dir, ignore_errors=True)
    
    if user_file.exists():
        user_file.unlink()
        
    print(f"Memory dir exists after: {memory_dir.exists()}")
    print(f"User file exists after: {user_file.exists()}")

if __name__ == "__main__":
    print("--- TTS Status ---")
    check_tts()
    print("\n--- Nuke Logic Verification ---")
    check_nuke_logic()
