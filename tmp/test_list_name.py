import sys
import os

# Adiciona o diretório atual ao sys.path para importar os módulos do projeto
sys.path.append(os.getcwd())

from backend.command_parser import parse

def test_list_parsing():
    test_cases = [
        "faça uma lista denominada Mercado",
        "faça uma lista chamada Compras",
        "crie uma lista nomeada Tarefas",
        "create a list called Movies",
        "create a list named Tasks",
        "haz una lista llamada Comida",
        "haz una lista denominada Supermercado",
        "fais une liste nommée Courses",
        "fais une liste appelée Travail",
        "mostre a lista denominada Mercado",
        "ver a lista chamada Compras"
    ]
    
    print("-" * 50)
    for text in test_cases:
        intent = parse(text)
        if intent:
            list_name = intent.get("list_name")
            items = intent.get("items")
            print(f"Input: '{text}'")
            print(f"  Type: {intent.get('type')}")
            print(f"  List: {list_name}")
            print(f"  Items: {items}")
        else:
            print(f"Input: '{text}' -> Intent: None")
        print("-" * 50)

if __name__ == "__main__":
    test_list_parsing()
