import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from zapista.tts.config import tts_enabled, piper_bin
    from zapista.tts.service import synthesize_voice_note
    from loguru import logger
except ImportError as e:
    print(f"❌ Error: Could not import zapista modules. Run this from the project root. {e}")
    sys.exit(1)

def diagnose():
    print("=== Zapista TTS Diagnostic ===")
    
    # 1. Environment Variables
    enabled = os.environ.get("TTS_ENABLED", "Not Set")
    pbin = os.environ.get("PIPER_BIN", "Not Set")
    mbase = os.environ.get("TTS_MODELS_BASE", "Not Set")
    
    print(f"Environment:")
    print(f"  TTS_ENABLED: {enabled}")
    print(f"  PIPER_BIN: {pbin}")
    print(f"  TTS_MODELS_BASE: {mbase}")
    
    # 2. config.py Logic
    is_active = tts_enabled()
    bin_path = piper_bin()
    print(f"\nLogic (config.py):")
    print(f"  tts_enabled(): {is_active}")
    print(f"  piper_bin(): {bin_path}")
    
    # 3. File System Checks
    print(f"\nFile System:")
    if bin_path:
        p = Path(bin_path)
        if p.exists():
            print(f"  ✅ Piper binary found: {bin_path}")
            if not os.access(bin_path, os.X_OK):
                print(f"  ❌ Piper binary is NOT executable!")
        else:
            print(f"  ❌ Piper binary NOT found at {bin_path}")
    else:
        print(f"  ❌ PIPER_BIN is empty.")
        
    if mbase != "Not Set":
        p = Path(mbase)
        if p.exists() and p.is_dir():
            print(f"  ✅ Models directory found: {mbase}")
            onnx_files = list(p.glob("**/*.onnx"))
            print(f"  Found {len(onnx_files)} .onnx models.")
        else:
            print(f"  ❌ Models directory NOT found or not a directory: {mbase}")
    
    # 4. Attempt Test Synthesis
    if is_active and bin_path and Path(bin_path).exists():
        print(f"\nAttempting test synthesis...")
        test_text = "Teste de diagnóstico do sistema Zapista."
        # Use a dummy chat_id
        try:
            res = synthesize_voice_note(test_text, "diagnostic_test")
            if res and res.exists():
                print(f"  ✅ Success! Generated: {res}")
                print(f"  Size: {res.stat().st_size} bytes")
                # res.unlink() # Keep it for manual check if needed
            else:
                print(f"  ❌ Failed: synthesize_voice_note returned None or file doesn't exist.")
        except Exception as e:
            print(f"  ❌ Exception during synthesis: {e}")
    else:
        print(f"\n⚠️ Skipping test synthesis because TTS is not fully configured.")

    print("\n=== End of Diagnostic ===")

if __name__ == "__main__":
    diagnose()
