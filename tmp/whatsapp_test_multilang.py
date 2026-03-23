"""
Multi-language Integration Test Simulation
==========================================
Verifies that PT, EN, and ES natural language commands are correctly parsed.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.command_parser import parse

def test_pt():
    print("Testing PT...")
    msg = "adiciona café à lista mercado"
    result = parse(msg)
    print(f"  Input: {msg} -> Result: {result}")
    assert result["type"] == "list_add"
    assert result["list_name"] == "mercado"
    print("  PT: PASS")

def test_en():
    print("\nTesting EN...")
    cases = [
        ("add milk to the shopping list", "mercado"),
        ("put bread on the shopping list", "mercado"),
        ("add inception to the movies list", "filmes"),
    ]
    for msg, expected_list in cases:
        result = parse(msg)
        print(f"  Input: {msg} -> Result: {result}")
        assert result["type"] == "list_add"
        assert result["list_name"] == expected_list
    print("  EN: PASS")

def test_es():
    print("\nTesting ES...")
    cases = [
        ("añadir leche a la lista compras", "mercado"),
        ("pon pan en la lista mercado", "mercado"),
        ("agregar el quijote a la lista libros", "livros"),
    ]
    for msg, expected_list in cases:
        result = parse(msg)
        print(f"  Input: {msg} -> Result: {result}")
        assert result["type"] == "list_add"
        assert result["list_name"] == expected_list
    print("  ES: PASS")

if __name__ == "__main__":
    try:
        test_pt()
        test_en()
        test_es()
        print("\nAll multi-language integration tests complete: PASS")
    except Exception as e:
        print(f"\nTests FAILED: {e}")
        sys.exit(1)
