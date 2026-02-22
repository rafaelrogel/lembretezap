import os
import sys
import subprocess
from pathlib import Path

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

PIPER_VOICES = {
    "pt-BR": {
        "model": "pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx",
        "config": "pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx.json",
    },
    "pt-PT": {
        "model": "pt/pt_PT/tug%C3%A3o/medium/pt_PT-tug%C3%A3o-medium.onnx",
        "config": "pt/pt_PT/tug%C3%A3o/medium/pt_PT-tug%C3%A3o-medium.onnx.json",
        "model_alt": "pt/pt_PT/tugão/medium/pt_PT-tugão-medium.onnx",
        "config_alt": "pt/pt_PT/tugão/medium/pt_PT-tugão-medium.onnx.json",
    },
    "es": {
        "model": "es/es_ES/davefx/medium/es_ES-davefx-medium.onnx",
        "config": "es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json",
    },
    "en": {
        "model": "en/en_US/amy/medium/en_US-amy-medium.onnx",
        "config": "en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    },
}

def diagnose():
    print("=== Zapista TTS Diagnostic (Enhanced) ===")
    
    root = Path(__file__).parent.parent
    env_path = root / ".env"
    env = load_env(env_path)
    
    pbin = os.environ.get("PIPER_BIN") or env.get("PIPER_BIN", "Not Set")
    mbase = os.environ.get("TTS_MODELS_BASE") or env.get("TTS_MODELS_BASE", "Not Set")
    
    print(f"Configuration:")
    print(f"  PIPER_BIN: {pbin}")
    print(f"  TTS_MODELS_BASE: {mbase}")
    
    # Check binary
    bin_ok = False
    if pbin != "Not Set":
        p = Path(pbin)
        if p.exists() and os.access(pbin, os.X_OK):
            bin_ok = True
            print(f"  ✅ Piper binary ok.")
        else:
            print(f"  ❌ Piper binary missing or not executable.")
    
    # Check all models
    print(f"\nModel Files (relative to {mbase}):")
    available_locales = []
    if mbase != "Not Set":
        base = Path(mbase)
        for locale, voice in PIPER_VOICES.items():
            m_path = base / voice["model"]
            c_path = base / voice["config"]
            
            exists = m_path.exists() and c_path.exists()
            
            if not exists and "model_alt" in voice:
                m_path = base / voice["model_alt"]
                c_path = base / voice["config_alt"]
                exists = m_path.exists() and c_path.exists()
            
            if exists:
                print(f"  ✅ {locale}: Found")
                available_locales.append(locale)
            else:
                print(f"  ❌ {locale}: MISSING")
                print(f"     Expected at: {voice['model']}")
    
    # Attempt synthesis for PT-BR and PT-PT if possible
    if bin_ok:
        for locale in available_locales:
            if locale not in ("pt-BR", "pt-PT"): continue
            
            print(f"\nTesting synthesis for {locale}...")
            voice = PIPER_VOICES[locale]
            m_path = Path(mbase) / voice["model"]
            c_path = Path(mbase) / voice["config"]
            if not m_path.exists() and "model_alt" in voice:
                m_path = Path(mbase) / voice["model_alt"]
                c_path = Path(mbase) / voice["config_alt"]
            
            output_wav = root / f"test_{locale.lower()}.wav"
            try:
                test_text = f"Teste de voz para o idioma {locale}."
                cmd = [pbin, "--model", str(m_path), "--config", str(c_path), "--output_file", str(output_wav)]
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = proc.communicate(input=test_text, timeout=10)
                
                if proc.returncode == 0 and output_wav.exists():
                    print(f"  ✅ {locale} synthesis success! ({output_wav.stat().st_size} bytes)")
                    output_wav.unlink()
                else:
                    print(f"  ❌ {locale} synthesis failed (code {proc.returncode})")
                    if stderr: print(f"     Error: {stderr[:200]}")
            except Exception as e:
                print(f"  ❌ {locale} error: {e}")

    print("\n=== End of Diagnostic ===")

if __name__ == "__main__":
    diagnose()
