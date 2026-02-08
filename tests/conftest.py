"""Pytest config: adiciona raiz do projeto ao path para imports backend/nanobot."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
