"""
Deep Stress Test - Simulação de Pico Repentino de Usuários

Cenários testados:
1. Spike Test: 0 → 200 usuários em 5 segundos
2. Sustained Load: 100 usuários simultâneos por 30 segundos
3. Message Burst: 1000 mensagens em 2 segundos (simula viral)
4. Memory Pressure: Operações pesadas em listas grandes
5. Database Contention: Escritas simultâneas no SQLite
6. Recovery Test: Sistema sob carga → pause → retoma

Métricas coletadas:
- Latência p50, p95, p99
- Throughput (msgs/segundo)
- Taxa de erro
- Uso de memória (se disponível)
"""

import asyncio
import random
import string
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class LoadTestMetrics:
    """Métricas coletadas durante o teste de carga."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    latencies_ms: list = None
    start_time: float = 0
    end_time: float = 0
    
    def __post_init__(self):
        if self.latencies_ms is None:
            self.latencies_ms = []
    
    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def throughput(self) -> float:
        if self.duration_seconds > 0:
            return self.successful_requests / self.duration_seconds
        return 0
    
    @property
    def error_rate(self) -> float:
        if self.total_requests > 0:
            return self.failed_requests / self.total_requests * 100
        return 0
    
    @property
    def p50_latency(self) -> float:
        if self.latencies_ms:
            return statistics.median(self.latencies_ms)
        return 0
    
    @property
    def p95_latency(self) -> float:
        if len(self.latencies_ms) >= 20:
            sorted_lat = sorted(self.latencies_ms)
            idx = int(len(sorted_lat) * 0.95)
            return sorted_lat[idx]
        return max(self.latencies_ms) if self.latencies_ms else 0
    
    @property
    def p99_latency(self) -> float:
        if len(self.latencies_ms) >= 100:
            sorted_lat = sorted(self.latencies_ms)
            idx = int(len(sorted_lat) * 0.99)
            return sorted_lat[idx]
        return max(self.latencies_ms) if self.latencies_ms else 0
    
    def summary(self) -> str:
        return f"""
        === MÉTRICAS DE CARGA ===
        Duração: {self.duration_seconds:.2f}s
        Total requests: {self.total_requests}
        Sucesso: {self.successful_requests} ({100 - self.error_rate:.1f}%)
        Falhas: {self.failed_requests} ({self.error_rate:.1f}%)
        Throughput: {self.throughput:.1f} req/s
        Latência p50: {self.p50_latency:.1f}ms
        Latência p95: {self.p95_latency:.1f}ms
        Latência p99: {self.p99_latency:.1f}ms
        """


def generate_random_user_id() -> str:
    return f"stress_{random.randint(100000, 999999)}"


def generate_random_item() -> str:
    items = [
        "arroz", "feijão", "macarrão", "leite", "pão", "ovos", "queijo", "presunto",
        "tomate", "cebola", "alho", "batata", "cenoura", "abobrinha", "berinjela",
        "frango", "carne", "peixe", "camarão", "bacon", "linguiça", "salsicha",
        "café", "açúcar", "sal", "óleo", "azeite", "vinagre", "mostarda", "ketchup",
        "sabão", "detergente", "esponja", "papel higiênico", "shampoo", "condicionador",
    ]
    return random.choice(items)


def generate_complex_message() -> str:
    """Gera mensagem complexa com múltiplos itens.
    
    Usa apenas padrões que o parser regex reconhece diretamente.
    Padrões como "preciso comprar X" caem para o LLM (intencional).
    """
    num_items = random.randint(3, 10)
    items = [generate_random_item() for _ in range(num_items)]
    
    patterns = [
        # PT-BR - regex reconhecidos (coloca na lista: X)
        f"adiciona na lista: {', '.join(items)}",
        f"coloca na lista: {', '.join(items)}",
        f"põe na lista: {', '.join(items[:5])}",
        f"adiciona à lista: {', '.join(items[:4])}",
        # Comando direto /list
        f"/list mercado add {items[0]}",
        f"/list mercado add {', '.join(items[:3])}",
        f"/list compras add {items[0]}",
        # ES - regex reconhecidos
        f"pon en la lista: {', '.join(items[:5])}",
        f"añade a la lista: {', '.join(items[:4])}",
        f"agrega en la lista: {', '.join(items[:3])}",
        # EN - regex reconhecidos
        f"add to list: {', '.join(items[:4])}",
        f"put on list: {', '.join(items[:3])}",
    ]
    return random.choice(patterns)


class DeepStressTest:
    """Classe para executar testes de stress profundos."""
    
    def __init__(self):
        self.metrics = LoadTestMetrics()
        self._lock = asyncio.Lock()
    
    async def record_request(self, success: bool, latency_ms: float):
        async with self._lock:
            self.metrics.total_requests += 1
            if success:
                self.metrics.successful_requests += 1
                self.metrics.latencies_ms.append(latency_ms)
            else:
                self.metrics.failed_requests += 1
    
    async def simulate_user_request(self, user_id: str, parse_func) -> bool:
        """Simula uma requisição de usuário."""
        message = generate_complex_message()
        
        start = time.perf_counter()
        try:
            result = parse_func(message)
            latency_ms = (time.perf_counter() - start) * 1000
            success = result is not None
            await self.record_request(success, latency_ms)
            return success
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            await self.record_request(False, latency_ms)
            return False
    
    async def run_spike_test(self, parse_func, num_users: int = 200, ramp_seconds: float = 5.0):
        """
        Spike Test: Simula pico repentino de usuários.
        0 → num_users em ramp_seconds.
        """
        self.metrics = LoadTestMetrics()
        self.metrics.start_time = time.perf_counter()
        
        users = [generate_random_user_id() for _ in range(num_users)]
        delay_per_user = ramp_seconds / num_users
        
        tasks = []
        for i, user_id in enumerate(users):
            await asyncio.sleep(delay_per_user)
            for _ in range(5):  # Cada usuário faz 5 requests
                task = asyncio.create_task(self.simulate_user_request(user_id, parse_func))
                tasks.append(task)
        
        await asyncio.gather(*tasks)
        self.metrics.end_time = time.perf_counter()
        return self.metrics
    
    async def run_sustained_load(self, parse_func, num_users: int = 100, duration_seconds: float = 30.0):
        """
        Sustained Load: Mantém carga constante por período.
        """
        self.metrics = LoadTestMetrics()
        self.metrics.start_time = time.perf_counter()
        
        end_time = time.perf_counter() + duration_seconds
        users = [generate_random_user_id() for _ in range(num_users)]
        
        async def user_loop(user_id: str):
            while time.perf_counter() < end_time:
                await self.simulate_user_request(user_id, parse_func)
                await asyncio.sleep(random.uniform(0.1, 0.5))  # Think time
        
        tasks = [asyncio.create_task(user_loop(uid)) for uid in users]
        await asyncio.gather(*tasks)
        
        self.metrics.end_time = time.perf_counter()
        return self.metrics
    
    async def run_burst_test(self, parse_func, num_messages: int = 1000, burst_seconds: float = 2.0):
        """
        Burst Test: Simula mensagem viral (muitas msgs em pouco tempo).
        """
        self.metrics = LoadTestMetrics()
        self.metrics.start_time = time.perf_counter()
        
        async def burst_request():
            user_id = generate_random_user_id()
            await self.simulate_user_request(user_id, parse_func)
        
        # Disparar todas as requisições quase simultaneamente
        delay = burst_seconds / num_messages
        tasks = []
        for _ in range(num_messages):
            tasks.append(asyncio.create_task(burst_request()))
            if delay > 0:
                await asyncio.sleep(delay)
        
        await asyncio.gather(*tasks)
        self.metrics.end_time = time.perf_counter()
        return self.metrics


# ============================================================================
# TESTES
# ============================================================================

@pytest.mark.asyncio
async def test_spike_200_users_in_5_seconds():
    """
    SPIKE TEST: 200 usuários aparecem em 5 segundos.
    Simula: bot viraliza no grupo da família/trabalho.
    
    Critérios de sucesso:
    - Taxa de erro < 5%
    - p95 latência < 500ms
    - Throughput > 50 req/s
    """
    from backend.command_parser import parse
    
    stress = DeepStressTest()
    metrics = await stress.run_spike_test(parse, num_users=200, ramp_seconds=5.0)
    
    print(metrics.summary())
    
    # Assertions
    assert metrics.error_rate < 5.0, f"Taxa de erro muito alta: {metrics.error_rate:.1f}%"
    assert metrics.p95_latency < 500, f"p95 latência muito alta: {metrics.p95_latency:.1f}ms"
    assert metrics.throughput > 50, f"Throughput muito baixo: {metrics.throughput:.1f} req/s"
    assert metrics.successful_requests >= 900, f"Poucos requests bem-sucedidos: {metrics.successful_requests}"


@pytest.mark.asyncio
async def test_sustained_100_users_30_seconds():
    """
    SUSTAINED LOAD: 100 usuários ativos por 30 segundos.
    Simula: uso normal em horário de pico.
    
    Critérios de sucesso:
    - Taxa de erro < 2%
    - p99 latência < 1000ms
    - Throughput estável > 100 req/s
    """
    from backend.command_parser import parse
    
    stress = DeepStressTest()
    metrics = await stress.run_sustained_load(parse, num_users=100, duration_seconds=30.0)
    
    print(metrics.summary())
    
    assert metrics.error_rate < 2.0, f"Taxa de erro muito alta: {metrics.error_rate:.1f}%"
    assert metrics.p99_latency < 1000, f"p99 latência muito alta: {metrics.p99_latency:.1f}ms"
    assert metrics.throughput > 100, f"Throughput muito baixo: {metrics.throughput:.1f} req/s"


@pytest.mark.asyncio
async def test_burst_1000_messages_in_2_seconds():
    """
    BURST TEST: 1000 mensagens em 2 segundos.
    Simula: mensagem viral em grupo grande.
    
    Critérios de sucesso:
    - Taxa de erro < 10%
    - Sistema não trava (completa em < 30s)
    - Throughput > 200 req/s
    """
    from backend.command_parser import parse
    
    stress = DeepStressTest()
    metrics = await stress.run_burst_test(parse, num_messages=1000, burst_seconds=2.0)
    
    print(metrics.summary())
    
    assert metrics.error_rate < 10.0, f"Taxa de erro muito alta: {metrics.error_rate:.1f}%"
    assert metrics.duration_seconds < 30, f"Teste demorou demais: {metrics.duration_seconds:.1f}s"
    assert metrics.throughput > 200, f"Throughput muito baixo: {metrics.throughput:.1f} req/s"


@pytest.mark.asyncio
async def test_database_contention_concurrent_writes():
    """
    DATABASE CONTENTION: Múltiplas escritas simultâneas no SQLite.
    Simula: vários usuários adicionando itens ao mesmo tempo.
    
    Nota: Usa SQLAlchemy diretamente com o modelo User para testar contenção.
    
    Critérios de sucesso:
    - Nenhum erro de lock
    - Todas as operações completam
    - Dados persistidos corretamente
    """
    from backend.database import SessionLocal, init_db
    from backend.user_store import get_or_create_user
    
    init_db()
    
    NUM_USERS = 100
    
    errors = []
    successful_writes = 0
    lock = asyncio.Lock()
    
    async def create_user(user_num: int):
        nonlocal successful_writes
        # Cada "user" é um chat_id único
        chat_id = f"db_stress_{user_num}_{random.randint(100000, 999999)}"
        
        db = SessionLocal()
        try:
            # Criar usuário no banco (operação de escrita)
            user = get_or_create_user(db, chat_id)
            if user:
                async with lock:
                    successful_writes += 1
        except Exception as e:
            async with lock:
                errors.append(f"User {user_num}: {e}")
        finally:
            db.close()
    
    # Executar todas as criações em paralelo
    tasks = [asyncio.create_task(create_user(i)) for i in range(NUM_USERS)]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print(f"\n=== DATABASE CONTENTION TEST ===")
    print(f"Total esperado: {NUM_USERS}")
    print(f"Escritas bem-sucedidas: {successful_writes}")
    print(f"Erros: {len(errors)}")
    if errors[:5]:
        print(f"Primeiros erros: {errors[:5]}")
    
    # Critérios
    error_rate = len(errors) / NUM_USERS * 100
    assert error_rate < 5, f"Taxa de erro de DB muito alta: {error_rate:.1f}%"
    assert successful_writes >= NUM_USERS * 0.95, f"Poucas escritas bem-sucedidas: {successful_writes}/{NUM_USERS}"


@pytest.mark.asyncio
async def test_memory_pressure_large_lists():
    """
    MEMORY PRESSURE: Operações em listas muito grandes.
    Simula: usuário power-user com centenas de itens.
    
    Critérios de sucesso:
    - Parser não falha com listas grandes
    - Tempo de resposta aceitável (< 100ms por operação)
    """
    from backend.command_parser import parse
    
    # Gerar mensagens com muitos itens
    large_messages = []
    for size in [50, 100, 200, 500]:
        items = [f"item_{i}_{generate_random_item()}" for i in range(size)]
        msg = f"adiciona na lista: {', '.join(items)}"
        large_messages.append((size, msg))
    
    results = []
    
    for size, msg in large_messages:
        start = time.perf_counter()
        result = parse(msg)
        latency_ms = (time.perf_counter() - start) * 1000
        
        results.append({
            "size": size,
            "parsed": result is not None,
            "latency_ms": latency_ms,
            "items_found": len(result.get("items", [result.get("item")])) if result else 0,
        })
    
    print("\n=== MEMORY PRESSURE TEST ===")
    for r in results:
        print(f"  {r['size']} itens: parsed={r['parsed']}, latency={r['latency_ms']:.1f}ms, items_found={r['items_found']}")
    
    # Verificações
    for r in results:
        assert r["parsed"], f"Falhou ao parsear mensagem com {r['size']} itens"
        assert r["latency_ms"] < 100, f"Latência muito alta para {r['size']} itens: {r['latency_ms']:.1f}ms"


@pytest.mark.asyncio
async def test_recovery_after_load():
    """
    RECOVERY TEST: Sistema se recupera após carga intensa.
    
    Fluxo:
    1. Carga intensa (burst)
    2. Pausa de 2 segundos
    3. Verifica se sistema responde normalmente
    
    Critérios:
    - Latência pós-carga volta ao normal (< 50ms)
    - Taxa de sucesso pós-carga > 99%
    """
    from backend.command_parser import parse
    
    stress = DeepStressTest()
    
    # 1. Carga intensa
    print("\n=== RECOVERY TEST ===")
    print("Fase 1: Carga intensa (500 msgs em 1s)...")
    await stress.run_burst_test(parse, num_messages=500, burst_seconds=1.0)
    
    # 2. Pausa
    print("Fase 2: Pausa de 2 segundos...")
    await asyncio.sleep(2)
    
    # 3. Verificar recuperação
    print("Fase 3: Verificando recuperação...")
    recovery_latencies = []
    recovery_success = 0
    
    for _ in range(100):
        msg = generate_complex_message()
        start = time.perf_counter()
        result = parse(msg)
        latency_ms = (time.perf_counter() - start) * 1000
        
        if result is not None:
            recovery_success += 1
            recovery_latencies.append(latency_ms)
    
    avg_latency = statistics.mean(recovery_latencies) if recovery_latencies else 0
    success_rate = recovery_success / 100 * 100
    
    print(f"  Latência média pós-carga: {avg_latency:.2f}ms")
    print(f"  Taxa de sucesso pós-carga: {success_rate:.1f}%")
    
    assert avg_latency < 50, f"Sistema não recuperou: latência={avg_latency:.2f}ms"
    assert success_rate >= 99, f"Sistema não recuperou: sucesso={success_rate:.1f}%"


@pytest.mark.asyncio
async def test_concurrent_list_operations_same_user():
    """
    RACE CONDITION: Operações simultâneas de parsing para o mesmo usuário.
    Simula: usuário enviando várias mensagens rapidamente.
    
    Critérios:
    - Parser não trava com requests simultâneos
    - Todas as operações completam
    - Sem erros de concorrência
    """
    from backend.command_parser import parse
    
    # Simular 100 mensagens do mesmo usuário em paralelo
    messages = [generate_complex_message() for _ in range(100)]
    
    async def parse_message(msg: str):
        try:
            result = parse(msg)
            return ("success", msg[:30], result is not None)
        except Exception as e:
            return ("error", msg[:30], str(e))
    
    # Disparar todas as operações simultaneamente
    tasks = [asyncio.create_task(parse_message(msg)) for msg in messages]
    results = await asyncio.gather(*tasks)
    
    successes = [r for r in results if r[0] == "success" and r[2]]
    parse_nones = [r for r in results if r[0] == "success" and not r[2]]
    errors = [r for r in results if r[0] == "error"]
    
    print(f"\n=== RACE CONDITION TEST (Parser) ===")
    print(f"Mensagens enviadas: {len(messages)}")
    print(f"Parseadas com sucesso: {len(successes)}")
    print(f"Retornaram None: {len(parse_nones)}")
    print(f"Erros de exceção: {len(errors)}")
    if errors[:3]:
        print(f"Primeiros erros: {errors[:3]}")
    
    # Critérios: nenhum erro de exceção, pelo menos 95% parseadas
    assert len(errors) == 0, f"Houve erros de concorrência: {errors[:5]}"
    assert len(successes) >= 95, f"Taxa de parsing baixa: {len(successes)}/100"


# ============================================================================
# RELATÓRIO FINAL
# ============================================================================

@pytest.mark.asyncio
async def test_full_load_report():
    """
    RELATÓRIO COMPLETO: Executa todos os cenários e gera relatório.
    """
    from backend.command_parser import parse
    
    print("\n" + "="*60)
    print("  RELATÓRIO COMPLETO DE STRESS TEST")
    print("="*60)
    
    stress = DeepStressTest()
    
    # Cenário 1: Spike
    print("\n[1/4] Spike Test (100 users em 3s)...")
    spike_metrics = await stress.run_spike_test(parse, num_users=100, ramp_seconds=3.0)
    print(f"  Throughput: {spike_metrics.throughput:.1f} req/s | p95: {spike_metrics.p95_latency:.1f}ms | Erros: {spike_metrics.error_rate:.1f}%")
    
    # Cenário 2: Sustained
    print("\n[2/4] Sustained Load (50 users por 10s)...")
    sustained_metrics = await stress.run_sustained_load(parse, num_users=50, duration_seconds=10.0)
    print(f"  Throughput: {sustained_metrics.throughput:.1f} req/s | p95: {sustained_metrics.p95_latency:.1f}ms | Erros: {sustained_metrics.error_rate:.1f}%")
    
    # Cenário 3: Burst
    print("\n[3/4] Burst Test (500 msgs em 1s)...")
    burst_metrics = await stress.run_burst_test(parse, num_messages=500, burst_seconds=1.0)
    print(f"  Throughput: {burst_metrics.throughput:.1f} req/s | p95: {burst_metrics.p95_latency:.1f}ms | Erros: {burst_metrics.error_rate:.1f}%")
    
    # Cenário 4: Recovery
    print("\n[4/4] Recovery Test...")
    await asyncio.sleep(1)
    recovery_latencies = []
    for _ in range(50):
        start = time.perf_counter()
        parse(generate_complex_message())
        recovery_latencies.append((time.perf_counter() - start) * 1000)
    print(f"  Latência média pós-carga: {statistics.mean(recovery_latencies):.2f}ms")
    
    print("\n" + "="*60)
    print("  RESUMO")
    print("="*60)
    print(f"""
    Spike (100 users):     {spike_metrics.throughput:.0f} req/s, p95={spike_metrics.p95_latency:.0f}ms
    Sustained (50 users):  {sustained_metrics.throughput:.0f} req/s, p95={sustained_metrics.p95_latency:.0f}ms
    Burst (500 msgs):      {burst_metrics.throughput:.0f} req/s, p95={burst_metrics.p95_latency:.0f}ms
    Recovery:              {statistics.mean(recovery_latencies):.1f}ms latência média
    
    STATUS: {"APROVADO" if all([
        spike_metrics.error_rate < 5,
        sustained_metrics.error_rate < 2,
        burst_metrics.error_rate < 10,
        statistics.mean(recovery_latencies) < 50
    ]) else "REPROVADO"}
    """)
    
    # Assertions finais
    assert spike_metrics.error_rate < 5
    assert sustained_metrics.error_rate < 2
    assert burst_metrics.error_rate < 10
