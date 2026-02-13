#!/usr/bin/env python3
"""
Stress test total do sistema Zapista.

Executa a suite completa de testes (unitários, integração, carga) com opção
de múltiplas iterações. Uso:
  python scripts/run_stress_test.py
  python scripts/run_stress_test.py --rounds 3
"""
import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Stress test total do Zapista")
    parser.add_argument("--rounds", type=int, default=1, help="Número de iterações da suite (default: 1)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Modo verboso (pytest -v)")
    parser.add_argument("-s", "--capture", action="store_true", help="Mostrar output (pytest -s)")
    args = parser.parse_args()

    cmd = [sys.executable, "-m", "pytest", "tests/", "--tb=short"]
    if args.verbose:
        cmd.append("-v")
    if args.capture:
        cmd.append("-s")

    passed = 0
    failed = 0

    for r in range(args.rounds):
        label = f" [Ronda {r + 1}/{args.rounds}]" if args.rounds > 1 else ""
        print(f"\n{'='*60}\n  Stress test total{label}\n{'='*60}\n")
        result = subprocess.run(cmd)
        if result.returncode == 0:
            passed += 1
        else:
            failed += 1

    if args.rounds > 1:
        print(f"\n{'='*60}")
        print(f"  Resumo: {passed} rondas OK, {failed} falharam (total {args.rounds})")
        print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
