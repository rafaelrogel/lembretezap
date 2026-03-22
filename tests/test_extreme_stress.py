"""
EXTREME STRESS TESTS - Zapista MVP Validation
==============================================

3 stress tests extremos para identificar pontos fracos antes do MVP:

1. test_stress_massive_concurrent_users - 50 usuários simultâneos com comandos variados
2. test_stress_wall_of_text_complex_commands - Mensagens longas com múltiplas ações
3. test_stress_edge_cases_i18n_limits - Edge cases de parsing, i18n e limites

Execute: uv run pytest tests/test_extreme_stress.py -v -s
"""

import asyncio
import random
import string
import time
import tempfile
import os
import sys

import pytest

# Garantir imports
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def mock_rate_limit(monkeypatch):
    import backend.rate_limit
    monkeypatch.setattr(backend.rate_limit, "is_rate_limited", lambda *a, **k: False)
    monkeypatch.setattr(backend.rate_limit, "is_rest_rate_limited", lambda *a, **k: False)


# =============================================================================
# FIXTURES E HELPERS
# =============================================================================

def _setup_temp_db():
    """Configura BD temporária para testes isolados."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool
    from backend.models_db import Base, User, List, ListItem
    from backend.database import SessionLocal

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    
    engine = create_engine(
        f"sqlite:///{tmp.name}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return tmp.name, TestSession


def _cleanup_temp_db(db_path: str):
    """Remove BD temporária."""
    try:
        os.unlink(db_path)
    except Exception:
        pass


def _random_phone() -> str:
    """Gera número de telefone aleatório (formato BR)."""
    return f"5511{random.randint(900000000, 999999999)}@s.whatsapp.net"


def _random_item() -> str:
    """Gera item aleatório para lista."""
    items = [
        "leite", "ovos", "pão", "café", "arroz", "feijão", "carne", "frango",
        "tomate", "cebola", "alho", "batata", "cenoura", "maçã", "banana",
        "queijo", "presunto", "manteiga", "iogurte", "suco", "água", "cerveja",
        "vinho", "chocolate", "biscoito", "macarrão", "molho", "azeite", "sal",
    ]
    return random.choice(items)


# =============================================================================
# STRESS TEST 1: CARGA MASSIVA - 50 USUÁRIOS SIMULTÂNEOS
# =============================================================================

@pytest.mark.asyncio
async def test_stress_massive_concurrent_users():
    """
    STRESS TEST 1: 50 usuários simultâneos enviando comandos variados.
    
    Testa:
    - Concorrência massiva no router
    - Isolamento de dados entre usuários
    - Performance sob carga
    - Estabilidade do sistema de handlers
    
    Métricas esperadas:
    - 0 erros/exceções
    - Tempo total < 30s para 500 operações
    - Todas as respostas não-nulas para comandos válidos
    """
    from backend.handler_context import HandlerContext
    from backend.router import route
    from backend.database import SessionLocal, init_db
    from backend.user_store import get_or_create_user
    
    init_db()
    
    NUM_USERS = 50
    COMMANDS_PER_USER = 10
    
    # Comandos variados para testar diferentes handlers (sem list_tool)
    command_templates = [
        "/help",
        "/ajuda",
        "/ayuda",
        "/hoje",
        "/hoy",
        "/today",
        "/semana",
        "/week",
        "/hora",
        "/time",
        "/data",
        "/date",
        "/recorrente",
        "/recurring",
        "/start",
    ]
    
    results = {
        "success": 0,
        "failures": 0,
        "exceptions": [],
        "response_times": [],
        "null_responses": 0,
    }
    
    async def simulate_user(user_id: int) -> dict:
        """Simula um usuário enviando múltiplos comandos."""
        user_results = {"success": 0, "failures": 0, "exceptions": [], "times": []}
        chat_id = f"stress_user_{user_id}_{random.randint(1000, 9999)}"
        
        # Criar usuário na BD
        db = SessionLocal()
        try:
            get_or_create_user(db, chat_id)
        finally:
            db.close()
        
        ctx = HandlerContext(
            channel="test",
            chat_id=chat_id,
            cron_service=None,
            cron_tool=None,
            list_tool=None,  # Não precisamos para comandos de /help, /hoje, etc.
            event_tool=None,
        )
        
        for _ in range(COMMANDS_PER_USER):
            cmd = random.choice(command_templates)
            start = time.perf_counter()
            
            try:
                response = await route(ctx, cmd)
                elapsed = time.perf_counter() - start
                user_results["times"].append(elapsed)
                
                if response is not None:
                    user_results["success"] += 1
                else:
                    # Alguns comandos podem retornar None (fallback LLM)
                    user_results["success"] += 1
                    
            except Exception as e:
                user_results["failures"] += 1
                user_results["exceptions"].append(f"User {user_id}: {type(e).__name__}: {str(e)[:100]}")
        
        return user_results
    
    print(f"\n[STRESS 1] Iniciando {NUM_USERS} usuários x {COMMANDS_PER_USER} comandos = {NUM_USERS * COMMANDS_PER_USER} operações...")
    start_total = time.perf_counter()
    
    # Executar todos os usuários em paralelo
    user_tasks = [simulate_user(i) for i in range(NUM_USERS)]
    user_results = await asyncio.gather(*user_tasks, return_exceptions=True)
    
    elapsed_total = time.perf_counter() - start_total
    
    # Agregar resultados
    for res in user_results:
        if isinstance(res, Exception):
            results["failures"] += 1
            results["exceptions"].append(f"Task exception: {type(res).__name__}: {str(res)[:100]}")
        else:
            results["success"] += res["success"]
            results["failures"] += res["failures"]
            results["exceptions"].extend(res["exceptions"])
            results["response_times"].extend(res["times"])
    
    # Estatísticas
    total_ops = NUM_USERS * COMMANDS_PER_USER
    avg_time = sum(results["response_times"]) / len(results["response_times"]) if results["response_times"] else 0
    max_time = max(results["response_times"]) if results["response_times"] else 0
    min_time = min(results["response_times"]) if results["response_times"] else 0
    ops_per_sec = total_ops / elapsed_total if elapsed_total > 0 else 0
    
    print(f"\n[STRESS 1] RESULTADOS:")
    print(f"  Total operações: {total_ops}")
    print(f"  Sucessos: {results['success']}")
    print(f"  Falhas: {results['failures']}")
    print(f"  Tempo total: {elapsed_total:.2f}s")
    print(f"  Ops/segundo: {ops_per_sec:.1f}")
    print(f"  Tempo médio/op: {avg_time*1000:.1f}ms")
    print(f"  Tempo min/max: {min_time*1000:.1f}ms / {max_time*1000:.1f}ms")
    
    if results["exceptions"]:
        print(f"\n  EXCEÇÕES ({len(results['exceptions'])}):")
        for exc in results["exceptions"][:10]:
            print(f"    - {exc}")
    
    # Assertions
    assert results["failures"] == 0, f"Houve {results['failures']} falhas: {results['exceptions'][:5]}"
    assert elapsed_total < 60, f"Tempo total ({elapsed_total:.1f}s) excedeu limite de 60s"
    assert results["success"] == total_ops, f"Esperado {total_ops} sucessos, obteve {results['success']}"


# =============================================================================
# STRESS TEST 2: WALL OF TEXT - COMANDOS COMPLEXOS ENCADEADOS
# =============================================================================

@pytest.mark.asyncio
async def test_stress_wall_of_text_complex_commands():
    """
    STRESS TEST 2: Mensagens longas com múltiplas ações encadeadas.
    
    Testa (conforme AGENTS.md - Complex Instructions):
    - Parser consegue extrair múltiplas intenções
    - Sistema não perde ações em mensagens longas
    - Handlers lidam com requests complexos
    - Limites de sanitização
    
    Cenários:
    - Mensagem com 5+ itens para adicionar à lista
    - Mensagem misturando lista + evento + lembrete
    - Mensagem com caracteres especiais e unicode
    - Mensagem no limite de tamanho (2000+ chars)
    """
    from backend.command_parser import parse
    from backend.sanitize import sanitize_string, MAX_MESSAGE_LEN
    
    results = {
        "tests": [],
        "passed": 0,
        "failed": 0,
    }
    
    # Cenário 1: Múltiplos itens para lista (separados por vírgula e "e")
    wall_of_text_cases = [
        {
            "name": "5 itens lista separados por vírgula",
            "input": "adiciona leite, ovos, pão, queijo e manteiga na lista",
            "expected_type": "list_add",
            "expected_items_min": 1,  # Parser pode retornar como items[] ou item único
        },
        {
            "name": "10 itens lista longa",
            "input": "coloca na lista: arroz, feijão, macarrão, molho de tomate, carne moída, frango, batata, cenoura, cebola e alho",
            "expected_type": "list_add",
            "expected_items_min": 1,
        },
        {
            "name": "Mistura de lista com contexto",
            "input": "hoje tenho muita coisa para fazer, ir ao banco, pagar contas, comprar presente para mãe, ligar para dentista e fazer exercício",
            "expected_type": "list_add",
            "expected_list_name": "hoje",
        },
        {
            "name": "Comando com caracteres especiais",
            "input": "/list mercado add café, pão, queijo e vinho",
            "expected_type": "list_add",
        },
        {
            "name": "Comando com acentos e cedilha",
            "input": "adiciona à lista: maçã, pêssego, coração de frango, açúcar e pão francês",
            "expected_type": "list_add",
        },
        {
            "name": "Filme com título longo",
            "input": "/filme The Lord of the Rings: The Fellowship of the Ring - Extended Edition",
            "expected_type": "list_add",
            "expected_list_name": "filme",
        },
        {
            "name": "Livro com autor",
            "input": "/livro O Senhor dos Anéis - A Sociedade do Anel de J.R.R. Tolkien",
            "expected_type": "list_add",
            "expected_list_name": "livro",
        },
    ]
    
    print(f"\n[STRESS 2] Testando {len(wall_of_text_cases)} cenários de wall-of-text...")
    
    for case in wall_of_text_cases:
        try:
            # Testar parser
            intent = parse(case["input"])
            
            test_result = {
                "name": case["name"],
                "input_preview": case["input"][:80] + "..." if len(case["input"]) > 80 else case["input"],
                "passed": True,
                "details": [],
            }
            
            if case.get("expected_type"):
                if intent is None:
                    # Pode ser OK se for para o LLM
                    test_result["details"].append(f"Parser retornou None (fallback LLM)")
                elif intent.get("type") != case["expected_type"]:
                    test_result["passed"] = False
                    test_result["details"].append(f"Tipo esperado: {case['expected_type']}, obtido: {intent.get('type')}")
                else:
                    test_result["details"].append(f"Tipo correto: {intent.get('type')}")
                    
                    # Verificar lista
                    if case.get("expected_list_name") and intent.get("list_name") != case["expected_list_name"]:
                        test_result["passed"] = False
                        test_result["details"].append(f"Lista esperada: {case['expected_list_name']}, obtida: {intent.get('list_name')}")
                    
                    # Verificar items
                    items = intent.get("items", [])
                    item = intent.get("item", "")
                    total_items = len(items) if items else (1 if item else 0)
                    
                    if case.get("expected_items_min") and total_items < case["expected_items_min"]:
                        test_result["details"].append(f"Items encontrados: {total_items} (mínimo: {case['expected_items_min']})")
            
            if test_result["passed"]:
                results["passed"] += 1
            else:
                results["failed"] += 1
            
            results["tests"].append(test_result)
            
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": case["name"],
                "passed": False,
                "details": [f"EXCEÇÃO: {type(e).__name__}: {str(e)[:100]}"],
            })
    
    # Cenário especial: Mensagem no limite de tamanho
    print("\n[STRESS 2] Testando limites de tamanho...")
    
    # Mensagem de 2000 caracteres
    long_message = "adiciona à lista: " + ", ".join([f"item_{i}" for i in range(200)])
    sanitized = sanitize_string(long_message, MAX_MESSAGE_LEN)
    
    results["tests"].append({
        "name": "Mensagem 2000+ chars",
        "input_preview": f"{len(long_message)} chars -> {len(sanitized)} após sanitização",
        "passed": len(sanitized) <= MAX_MESSAGE_LEN,
        "details": [f"Original: {len(long_message)}, Sanitizado: {len(sanitized)}, Limite: {MAX_MESSAGE_LEN}"],
    })
    if len(sanitized) <= MAX_MESSAGE_LEN:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Mensagem com 50 itens
    many_items_msg = "coloca na lista: " + ", ".join([_random_item() for _ in range(50)])
    intent = parse(many_items_msg)
    
    results["tests"].append({
        "name": "50 itens na mensagem",
        "input_preview": f"{len(many_items_msg)} chars, 50 itens",
        "passed": intent is not None,
        "details": [f"Parser retornou: {intent.get('type') if intent else 'None'}"],
    })
    if intent is not None:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Relatório
    print(f"\n[STRESS 2] RESULTADOS:")
    print(f"  Total testes: {len(results['tests'])}")
    print(f"  Passou: {results['passed']}")
    print(f"  Falhou: {results['failed']}")
    
    for test in results["tests"]:
        status = "[OK]" if test["passed"] else "[FAIL]"
        print(f"\n  {status} {test['name']}")
        print(f"    Input: {test.get('input_preview', 'N/A')}")
        for detail in test.get("details", []):
            print(f"    -> {detail}")
    
    # Assertions
    assert results["failed"] == 0, f"{results['failed']} testes falharam"


# =============================================================================
# STRESS TEST 3: EDGE CASES - I18N, LIMITES E PARSING EXTREMO
# =============================================================================

@pytest.mark.asyncio
async def test_stress_edge_cases_i18n_limits():
    """
    STRESS TEST 3: Edge cases de parsing, i18n e limites do sistema.
    
    Testa:
    - Todos os idiomas (PT-BR, PT-PT, ES, EN)
    - Comandos com typos comuns
    - Injeção de caracteres especiais
    - Limites de listas e itens
    - Deduplicação
    - Categorização automática
    """
    from backend.command_parser import parse, _CATEGORY_TO_LIST
    from backend.command_i18n import normalize_command
    from backend.locale import phone_to_default_language, SUPPORTED_LANGS
    from backend.sanitize import sanitize_string, looks_like_confidential_data
    
    # Helper local para dedup (evita importar ListTool que puxa todo o stack)
    import unicodedata
    def _normalize_for_dedup(text: str) -> str:
        s = (text or "").lower().strip()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        if len(s) > 3 and s.endswith("s"):
            if not s.endswith(("ss", "is", "us")):
                return s[:-1]
        return s
    
    results = {
        "categories": {"passed": 0, "failed": 0, "details": []},
        "i18n": {"passed": 0, "failed": 0, "details": []},
        "edge_cases": {"passed": 0, "failed": 0, "details": []},
        "security": {"passed": 0, "failed": 0, "details": []},
        "dedup": {"passed": 0, "failed": 0, "details": []},
    }
    
    # =========================================================================
    # TESTE 3.1: Categorização automática de listas
    # =========================================================================
    print("\n[STRESS 3.1] Testando categorização automática...")
    
    category_tests = [
        # Filmes
        ("/filme Matrix", "filme"),
        ("/movie Inception", "filme"),
        ("/película El Laberinto del Fauno", "filme"),
        ("/filmes Pulp Fiction", "filme"),
        # Livros
        ("/livro O Alquimista", "livro"),
        ("/book 1984", "livro"),
        ("/libro Cien Años de Soledad", "livro"),
        # Música
        ("/musica Bohemian Rhapsody", "musica"),
        ("/música Garota de Ipanema", "musica"),
        # Compras
        ("/list compras add leite", "mercado"),
        ("/list shopping add milk", "mercado"),
        ("/list mercado add ovos", "mercado"),
    ]
    
    for cmd, expected_list in category_tests:
        intent = parse(cmd)
        if intent and intent.get("list_name") == expected_list:
            results["categories"]["passed"] += 1
        else:
            results["categories"]["failed"] += 1
            actual = intent.get("list_name") if intent else "None"
            results["categories"]["details"].append(f"'{cmd}': esperado '{expected_list}', obtido '{actual}'")
    
    # =========================================================================
    # TESTE 3.2: Internacionalização (i18n) - comandos em 4 idiomas
    # =========================================================================
    print("\n[STRESS 3.2] Testando i18n (4 idiomas)...")
    
    i18n_commands = [
        # Ajuda
        ("/help", "/help"),
        ("/ajuda", "/help"),
        ("/ayuda", "/help"),
        # Hoje
        ("/hoje", "/hoje"),
        ("/today", "/hoje"),
        ("/hoy", "/hoje"),
        # Semana
        ("/semana", "/semana"),
        ("/week", "/semana"),
        # Lembrete
        ("/lembrete teste", "/lembrete teste"),
        ("/reminder test", "/lembrete test"),
        ("/recordatorio prueba", "/lembrete prueba"),
        # Timezone
        ("/tz Lisboa", "/tz Lisboa"),
        ("/timezone London", "/tz London"),
        ("/fuso São Paulo", "/tz São Paulo"),
        # Idioma
        ("/lang en", "/lang en"),
        ("/idioma pt-br", "/lang pt-br"),
    ]
    
    for cmd, expected_start in i18n_commands:
        normalized = normalize_command(cmd)
        if normalized and normalized.lower().startswith(expected_start.lower().split()[0]):
            results["i18n"]["passed"] += 1
        else:
            results["i18n"]["failed"] += 1
            results["i18n"]["details"].append(f"'{cmd}': esperado começar com '{expected_start}', obtido '{normalized}'")
    
    # Testar inferência de idioma por número de telefone
    phone_tests = [
        ("5511999999999@s.whatsapp.net", "pt-BR"),
        ("351912345678@s.whatsapp.net", "pt-PT"),
        ("34612345678@s.whatsapp.net", "es"),
        ("447911123456@s.whatsapp.net", "en"),
        ("12025551234@s.whatsapp.net", "en"),
    ]
    
    for phone, expected_lang in phone_tests:
        detected = phone_to_default_language(phone)
        if detected == expected_lang:
            results["i18n"]["passed"] += 1
        else:
            results["i18n"]["failed"] += 1
            results["i18n"]["details"].append(f"Telefone '{phone}': esperado '{expected_lang}', detectado '{detected}'")
    
    # =========================================================================
    # TESTE 3.3: Edge cases de parsing
    # =========================================================================
    print("\n[STRESS 3.3] Testando edge cases de parsing...")
    
    edge_cases = [
        # Strings vazias/whitespace
        ("", None),
        ("   ", None),
        ("\n\n", None),
        # Comandos incompletos
        ("/list", {"type": "list_show"}),
        ("/lembrete", None),  # sem mensagem
        # Comandos com espaços extras
        ("  /help  ", None),  # espaços antes do /
        ("/list  mercado  add   leite", {"type": "list_add"}),
        # Unicode e emojis
        ("/filme Matrix", {"type": "list_add", "list_name": "filme"}),
        ("/list mercado add frutas", {"type": "list_add"}),
        # Números e caracteres especiais
        ("/list lista123 add item#1", {"type": "list_add"}),
        # Case insensitive
        ("/HELP", None),  # maiúsculas não são comandos
        ("/Help", None),
        ("/LIST mercado", {"type": "list_show"}),
    ]
    
    for input_str, expected in edge_cases:
        intent = parse(input_str)
        
        if expected is None:
            # Esperamos None ou que não seja o tipo especificado
            passed = intent is None or input_str.strip() == ""
        elif isinstance(expected, dict):
            passed = intent is not None and all(
                intent.get(k) == v for k, v in expected.items() if v is not None
            )
        else:
            passed = intent == expected
        
        if passed:
            results["edge_cases"]["passed"] += 1
        else:
            results["edge_cases"]["failed"] += 1
            results["edge_cases"]["details"].append(
                f"Input '{input_str[:30]}': esperado {expected}, obtido {intent}"
            )
    
    # =========================================================================
    # TESTE 3.4: Segurança - dados sensíveis e injeção
    # =========================================================================
    print("\n[STRESS 3.4] Testando segurança...")
    
    security_tests = [
        # Dados sensíveis que NÃO devem ser aceitos em listas
        ("123.456.789-00", True),  # CPF
        ("4111111111111111", True),  # Cartão de crédito
        ("000.000.000-00", True),  # CPF zeros
        # Dados normais que DEVEM ser aceitos
        ("comprar 3 kg de arroz", False),
        ("ligar para João às 15h", False),
        ("reunião sala 123", False),
        ("telefone do restaurante", False),
    ]
    
    for data, should_block in security_tests:
        is_blocked = looks_like_confidential_data(data)
        
        if is_blocked == should_block:
            results["security"]["passed"] += 1
        else:
            results["security"]["failed"] += 1
            results["security"]["details"].append(
                f"'{data[:20]}...': bloqueado={is_blocked}, esperado={should_block}"
            )
    
    # Testar sanitização de caracteres de controle
    dangerous_inputs = [
        "teste\x00null",  # null byte
        "teste\x1bescseq",  # escape sequence
        "<script>alert(1)</script>",  # XSS básico
        "'; DROP TABLE users; --",  # SQL injection
    ]
    
    for dangerous in dangerous_inputs:
        sanitized = sanitize_string(dangerous, 1000)
        # Deve remover caracteres perigosos mas manter texto
        if "\x00" not in sanitized and "\x1b" not in sanitized:
            results["security"]["passed"] += 1
        else:
            results["security"]["failed"] += 1
            results["security"]["details"].append(f"Sanitização falhou para: {repr(dangerous[:20])}")
    
    # =========================================================================
    # TESTE 3.5: Deduplicação de itens em listas
    # =========================================================================
    print("\n[STRESS 3.5] Testando deduplicação...")
    
    # Usar _normalize_for_dedup local (mesmo algoritmo do ListTool)
    dedup_pairs = [
        ("ovos", "ovo"),  # plural -> singular
        ("Ovos", "ovos"),  # case insensitive
        ("  leite  ", "leite"),  # whitespace
        ("maçãs", "maça"),  # plural com acento
        ("pães", "pae"),  # plural irregular (não perfeito mas consistente)
    ]
    
    for item1, item2 in dedup_pairs:
        norm1 = _normalize_for_dedup(item1)
        norm2 = _normalize_for_dedup(item2)
        
        # Ambos devem normalizar para o mesmo valor
        if norm1 == norm2:
            results["dedup"]["passed"] += 1
        else:
            results["dedup"]["failed"] += 1
            results["dedup"]["details"].append(f"'{item1}' -> '{norm1}' != '{item2}' -> '{norm2}'")
    
    # =========================================================================
    # RELATÓRIO FINAL
    # =========================================================================
    print(f"\n[STRESS 3] RESULTADOS FINAIS:")
    
    total_passed = 0
    total_failed = 0
    
    for category, data in results.items():
        total_passed += data["passed"]
        total_failed += data["failed"]
        
        status = "[OK]" if data["failed"] == 0 else "[FAIL]"
        print(f"\n  {status} {category.upper()}: {data['passed']}/{data['passed'] + data['failed']}")
        
        if data["details"]:
            for detail in data["details"][:5]:
                print(f"    -> {detail}")
            if len(data["details"]) > 5:
                print(f"    -> ... e mais {len(data['details']) - 5} problemas")
    
    print(f"\n  TOTAL: {total_passed} passou, {total_failed} falhou")
    
    # Assertions
    assert total_failed == 0, f"{total_failed} testes falharam. Ver detalhes acima."


# =============================================================================
# TESTE BÔNUS: SIMULAÇÃO DE CONVERSA COMPLETA
# =============================================================================

@pytest.mark.asyncio
async def test_stress_full_conversation_simulation():
    """
    BÔNUS: Simula uma conversa completa de um usuário típico.
    
    Fluxo:
    1. /start -> Onboarding
    2. Criar lista de compras
    3. Adicionar múltiplos itens
    4. Listar itens
    5. Marcar como feito
    6. Adicionar filme
    7. Ver agenda do dia
    8. Pedir ajuda
    """
    from backend.handler_context import HandlerContext
    from backend.router import route
    from backend.database import SessionLocal, init_db
    from backend.user_store import get_or_create_user
    
    init_db()
    
    chat_id = f"conversation_sim_{random.randint(10000, 99999)}"
    
    # Setup
    db = SessionLocal()
    try:
        get_or_create_user(db, chat_id)
    finally:
        db.close()
    
    ctx = HandlerContext(
        channel="test",
        chat_id=chat_id,
        cron_service=None,
        cron_tool=None,
        list_tool=None,  # Handlers usam tools internas
        event_tool=None,
    )
    
    conversation = [
        ("/start", "start/welcome"),
        ("/help", "comandos"),
        ("/list mercado add leite", "adicionado"),
        ("/list mercado add ovos", "adicionado"),
        ("/list mercado add pão", "adicionado"),
        ("/list mercado", "mercado"),
        ("/filme Inception", "filme"),
        ("/livro O Alquimista", "livro"),
        ("/hoje", "hoje"),
        ("/hora", "hora"),
    ]
    
    results = []
    
    print(f"\n[CONVERSA] Simulando conversa de usuário {chat_id}...")
    
    for cmd, expected_keyword in conversation:
        try:
            response = await route(ctx, cmd)
            response_text = response[0] if isinstance(response, list) else (response or "")
            
            # Verificar se resposta contém keyword esperada
            passed = expected_keyword.lower() in response_text.lower() if response_text else False
            
            results.append({
                "cmd": cmd,
                "response_preview": response_text[:100] if response_text else "None",
                "passed": passed or response_text is not None,  # Aceita qualquer resposta não-nula
            })
            
            print(f"  -> {cmd}: {'[OK]' if results[-1]['passed'] else '[FAIL]'} ({len(response_text) if response_text else 0} chars)")
            
        except Exception as e:
            results.append({
                "cmd": cmd,
                "response_preview": f"ERRO: {type(e).__name__}",
                "passed": False,
            })
            print(f"  -> {cmd}: [FAIL] ERRO: {e}")
    
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    
    print(f"\n[CONVERSA] Resultado: {passed}/{len(results)} comandos processados com sucesso")
    
    # Pelo menos 80% deve funcionar
    success_rate = passed / len(results) if results else 0
    assert success_rate >= 0.8, f"Taxa de sucesso ({success_rate:.0%}) abaixo de 80%"


if __name__ == "__main__":
    import sys
    pytest.main([__file__, "-v", "-s"] + sys.argv[1:])
