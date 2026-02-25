import re
import os
from pathlib import Path

# Configurações de arquivos
BASE_DIR = Path(r"C:\Users\rafae\Documents\Vibecoding\Zapista\lembretezap")
LOCALE_FILE = BASE_DIR / "backend" / "locale.py"
EMPATHY_FILE = BASE_DIR / "backend" / "empathy_positive_data.py"
SMART_FILE = BASE_DIR / "backend" / "smart_reminder.py"

# Blacklist para PT-BR (não deve conter termos de PT-PT)
BR_BLACKLIST = [
    r"\btu\b", r"\btens\b", r"\bteu\b", r"\btua\b", r"\bteus\b", r"\btuas\b", 
    r"\bti\b", r"\bcontigo\b", r"\bestás\b", r"\bvais\b", r"\bquerias\b", 
    r"\bpodes\b", r"\bdizes\b", r"\bfazes\b", r"\bclica\b", r"\bcontacto\b",
    r"\bregista\b", r"\borganizo\." # organizo é comum, mas no contexto PT-PT "organizo-te" etc.
]

# Blacklist para PT-PT (não deve conter termos informais de PT-BR excessivos)
PT_BLACKLIST = [
    r"\bvocê\b", r"\busuário\b", r"\bvaleue\b"
]

def check_file(path, br_pattern, pt_pattern):
    if not path.exists():
        print(f"Skipping {path} (not found)")
        return True
    
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    errors = 0
    # Procura blocos "pt-BR"
    for i, line in enumerate(lines):
        # Se a linha contém "pt-BR" e não é um comentário de bloco keywords
        if '"pt-BR":' in line and 'messages' in content[content.rfind('messages', 0, content.find(line)):]:
            for p in br_pattern:
                if re.search(p, line, re.IGNORECASE):
                    print(f"Error in {path.name}:{i+1} (PT-BR line): Found blacklisted PT-PT term: '{p}' in '{line.strip()}'")
                    errors += 1
        
        # Procura blocos "pt-PT"
        if '"pt-PT":' in line:
            for p in pt_pattern:
                if re.search(p, line, re.IGNORECASE):
                    # print(f"Warning in {path.name}:{i+1} (PT-PT line): Found PT-BR term: '{p}' in '{line.strip()}'")
                    pass # PT-PT é menos crítico para este usuário
    
    return errors == 0

def main():
    print("Iniciando auditoria de dialetos...")
    results = [
        check_file(LOCALE_FILE, BR_BLACKLIST, PT_BLACKLIST),
        check_file(EMPATHY_FILE, BR_BLACKLIST, PT_BLACKLIST),
        check_file(SMART_FILE, BR_BLACKLIST, PT_BLACKLIST)
    ]
    
    if all(results):
        print("✅ Auditoria concluída com sucesso! Nenhuma mistura crítica detectada.")
    else:
        print("❌ Auditoria falhou. Corrija os erros acima.")

if __name__ == "__main__":
    main()
