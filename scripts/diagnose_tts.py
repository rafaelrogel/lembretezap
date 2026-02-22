import os
import sys
import subprocess
from pathlib import Path
import re

def load_env(env_path):
    """Simple parser for .env files."""
    env = {}
    if not env_path.exists():
        return env
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip().strip('"').strip("'")
    return env

def diagnose():
    print("=== Zapista TTS Diagnostic (Standalone) ===")
    
    # 1. Load context
    root = Path(__file__).parent.parent
    env_path = root / ".env"
    env = load_env(env_path)
    
    print(f"Project root: {root}")
    print(f"Found .env: {'✅' if env_path.exists() else '❌'}")
    
    # 2. Environment Variables (priority: OS env > .env file)
    enabled = os.environ.get("TTS_ENABLED") or env.get("TTS_ENABLED", "Not Set")
    pbin = os.environ.get("PIPER_BIN") or env.get("PIPER_BIN", "Not Set")
    mbase = os.environ.get("TTS_MODELS_BASE") or env.get("TTS_MODELS_BASE", "Not Set")
    
    print(f"\nConfiguration:")
    print(f"  TTS_ENABLED: {enabled}")
    print(f"  PIPER_BIN: {pbin}")
    print(f"  TTS_MODELS_BASE: {mbase}")
    
    # 3. File System Checks
    print(f"\nFile System:")
    bin_ok = False
    if pbin != "Not Set":
        p = Path(pbin)
        if p.exists():
            print(f"  ✅ Piper binary found: {pbin}")
            if os.access(pbin, os.X_OK):
                bin_ok = True
                print(f"  ✅ Piper binary is executable.")
            else:
                print(f"  ❌ Piper binary is NOT executable! Try: chmod +x {pbin}")
        else:
            print(f"  ❌ Piper binary NOT found at {pbin}")
    else:
        print(f"  ❌ PIPER_BIN is not configured.")
        
    models_ok = False
    if mbase != "Not Set":
        p = Path(mbase)
        if p.exists() and p.is_dir():
            print(f"  ✅ Models directory found: {mbase}")
            onnx_files = list(p.glob("**/*.onnx"))
            print(f"  Found {len(onnx_files)} .onnx models.")
            if len(onnx_files) > 0:
                models_ok = True
        else:
            print(f"  ❌ Models directory NOT found or not a directory: {mbase}")
    
    # 4. Attempt Test Synthesis using SUBPROCESS directly
    is_active = str(enabled).lower() in ("1", "true", "yes")
    
    if bin_ok and models_ok:
        print(f"\nAttempting test synthesis via subprocess...")
        test_text = "Teste de diagnóstico do sistema Zapista."
        output_wav = root / "test_synthesis.wav"
        
        # Try to find a model to use
        onnx_files = list(Path(mbase).glob("**/*.onnx"))
        model_path = str(onnx_files[0])
        config_path = model_path + ".json"
        
        print(f"  Using model: {model_path}")
        
        try:
            cmd = [
                pbin,
                "--model", model_path,
                "--config", config_path,
                "--output_file", str(output_wav)
            ]
            print(f"  Running: {' '.join(cmd)}")
            
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = proc.communicate(input=test_text, timeout=10)
            
            if proc.returncode == 0 and output_wav.exists():
                print(f"  ✅ Success! Generated: {output_wav}")
                print(f"  Size: {output_wav.stat().st_size} bytes")
                # output_wav.unlink() # Cleanup
            else:
                print(f"  ❌ Failed (code {proc.returncode})")
                if stderr:
                    print(f"  Error: {stderr[:500]}")
        except Exception as e:
            print(f"  ❌ Exception during synthesis: {e}")
    else:
        print(f"\n⚠️ Skipping test synthesis because prerequisites are not met.")
        if not is_active:
            print("  Note: TTS_ENABLED is not set to 1.")

    print("\n=== End of Diagnostic ===")

if __name__ == "__main__":
    diagnose()
