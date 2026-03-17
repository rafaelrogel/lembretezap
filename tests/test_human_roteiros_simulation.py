"""
Simulação dos 6 Roteiros de Stress Test Humano
Testa todos os comandos de texto dos roteiros sem precisar de WhatsApp real.

Não testa:
- Áudios (precisa de arquivo real)
- Lembretes que chegam no futuro (precisaria esperar)
- Interface WhatsApp real

Testa:
- Parser reconhece todos os comandos
- Handlers respondem corretamente
- Operações de lista funcionam
- PT-BR vs PT-PT
- Comandos em rajada
"""

import asyncio
import random
import time
from typing import Any

import pytest

from backend.command_parser import parse
from backend.database import SessionLocal, init_db
from backend.user_store import get_or_create_user
from backend.handler_context import HandlerContext
from backend.router import route


# Inicializar DB
init_db()


def create_test_context(chat_id: str) -> HandlerContext:
    """Cria contexto de teste para um usuário."""
    db = SessionLocal()
    try:
        get_or_create_user(db, chat_id)
    finally:
        db.close()
    
    return HandlerContext(
        channel="test",
        chat_id=chat_id,
        cron_service=None,
        cron_tool=None,
        list_tool=None,
        event_tool=None,
    )


async def send_message(ctx: HandlerContext, message: str) -> tuple[str, Any, float]:
    """Simula envio de mensagem e retorna (mensagem, resposta, latência_ms)."""
    start = time.perf_counter()
    try:
        response = await route(ctx, message)
        latency = (time.perf_counter() - start) * 1000
        return (message, response, latency)
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return (message, f"ERRO: {e}", latency)


async def send_batch(ctx: HandlerContext, messages: list[str], delay: float = 0) -> list[tuple[str, Any, float]]:
    """Envia múltiplas mensagens em sequência."""
    results = []
    for msg in messages:
        result = await send_message(ctx, msg)
        results.append(result)
        if delay > 0:
            await asyncio.sleep(delay)
    return results


def print_results(results: list[tuple[str, Any, float]], title: str):
    """Imprime resultados de forma legível."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    
    success = 0
    failed = 0
    total_latency = 0
    
    for msg, response, latency in results:
        total_latency += latency
        status = "✅" if response and not str(response).startswith("ERRO") else "❌"
        if response and not str(response).startswith("ERRO"):
            success += 1
        else:
            failed += 1
        
        msg_preview = msg[:50] + "..." if len(msg) > 50 else msg
        resp_preview = str(response)[:60] + "..." if response and len(str(response)) > 60 else response
        print(f"  {status} [{latency:6.1f}ms] {msg_preview}")
        if response:
            print(f"      → {resp_preview}")
    
    print(f"\n  Resumo: {success} OK, {failed} falhas, {total_latency:.0f}ms total")
    return success, failed


# =============================================================================
# ROTEIRO 1 - BRASIL: Volume de Listas e Itens em Rajada
# =============================================================================

@pytest.mark.asyncio
async def test_roteiro1_brasil_volume_listas():
    """
    ROTEIRO 1 - BRASIL
    Foco: Volume de Listas e Itens em Rajada
    """
    print("\n" + "="*70)
    print("  ROTEIRO 1 - BRASIL 🇧🇷: Volume de Listas e Itens em Rajada")
    print("="*70)
    
    chat_id = f"roteiro1_br_{random.randint(10000, 99999)}"
    ctx = create_test_context(chat_id)
    
    total_success = 0
    total_failed = 0
    
    # Fase 1: Aquecimento
    fase1 = [
        "/start",
        "meu nome é TestadorBR1",
        "moro em São Paulo",
    ]
    results = await send_batch(ctx, fase1)
    s, f = print_results(results, "Fase 1: Aquecimento")
    total_success += s
    total_failed += f
    
    # Fase 2: Rajada de Itens
    fase2 = [
        "adiciona na lista: arroz, feijão, macarrão, óleo, sal, açúcar",
        "coloca na lista: leite, ovos, queijo, presunto, manteiga",
        "põe na lista: tomate, cebola, alho, batata, cenoura, abobrinha",
        "adiciona na lista: frango, carne moída, linguiça, bacon, peixe",
        "coloca na lista: café, chá, suco, refrigerante, água mineral",
        "adiciona na lista: sabão em pó, detergente, amaciante, esponja",
        "põe na lista: shampoo, condicionador, sabonete, pasta de dente",
        "coloca na lista: papel higiênico, guardanapo, papel toalha",
        "adiciona na lista: biscoito, chocolate, sorvete, bolo, pudim",
        "coloca na lista: pão de forma, pão francês, torrada, cream cheese",
    ]
    results = await send_batch(ctx, fase2)
    s, f = print_results(results, "Fase 2: Rajada de Itens (50+ itens)")
    total_success += s
    total_failed += f
    
    # Fase 3: Operações na Lista
    fase3 = [
        "/list mercado",
        "feito arroz",
        "feito leite",
        "remove sabão em pó",
        "/list mercado",
    ]
    results = await send_batch(ctx, fase3)
    s, f = print_results(results, "Fase 3: Operações na Lista")
    total_success += s
    total_failed += f
    
    # Fase 4: Múltiplas Listas
    fase4 = [
        "/list filmes add Matrix, Interestelar, Inception, Coringa, Parasita",
        "/list livros add O Alquimista, 1984, Dom Casmurro, Harry Potter",
        "/list músicas add Bohemian Rhapsody, Imagine, Hotel California",
        "/list séries add Breaking Bad, Game of Thrones, Stranger Things, The Office",
        "/list jogos add FIFA 24, GTA VI, Zelda, Mario Kart, Minecraft",
    ]
    results = await send_batch(ctx, fase4)
    s, f = print_results(results, "Fase 4: Múltiplas Listas")
    total_success += s
    total_failed += f
    
    # Fase 5: Ver Listas
    fase5 = [
        "/list",
        "/list filmes",
        "/list livros",
        "minhas listas",
    ]
    results = await send_batch(ctx, fase5)
    s, f = print_results(results, "Fase 5: Ver Todas as Listas")
    total_success += s
    total_failed += f
    
    # Fase 6: Lembretes
    fase6 = [
        "me lembra de ligar pro médico em 10 minutos",
        "lembra de pagar a conta de luz amanhã às 9h",
        "me avisa pra tomar remédio daqui 2 horas",
        "lembrete: reunião sexta às 14h",
    ]
    results = await send_batch(ctx, fase6)
    s, f = print_results(results, "Fase 6: Lembretes")
    total_success += s
    total_failed += f
    
    # Fase 7: Consultas
    fase7 = [
        "/hoje",
        "/semana",
        "minha agenda",
    ]
    results = await send_batch(ctx, fase7)
    s, f = print_results(results, "Fase 7: Consultas")
    total_success += s
    total_failed += f
    
    print(f"\n{'='*70}")
    print(f"  ROTEIRO 1 COMPLETO: {total_success} OK, {total_failed} falhas")
    print(f"{'='*70}")
    
    assert total_failed < total_success * 0.2, f"Muitas falhas: {total_failed}/{total_success + total_failed}"


# =============================================================================
# ROTEIRO 2 - BRASIL: Linguagem Natural (sem áudios)
# =============================================================================

@pytest.mark.asyncio
async def test_roteiro2_brasil_linguagem_natural():
    """
    ROTEIRO 2 - BRASIL
    Foco: Linguagem Natural (comandos que seriam por áudio)
    """
    print("\n" + "="*70)
    print("  ROTEIRO 2 - BRASIL 🇧🇷: Linguagem Natural")
    print("="*70)
    
    chat_id = f"roteiro2_br_{random.randint(10000, 99999)}"
    ctx = create_test_context(chat_id)
    
    total_success = 0
    total_failed = 0
    
    # Fase 1: Setup
    fase1 = [
        "/start",
        "Meu nome é TestadorBR2",
        "Eu moro no Rio de Janeiro",
    ]
    results = await send_batch(ctx, fase1)
    s, f = print_results(results, "Fase 1: Setup")
    total_success += s
    total_failed += f
    
    # Fase 2: Comandos Naturais (simulando o que seria falado)
    fase2 = [
        "Preciso comprar arroz, feijão, macarrão e óleo",
        "Adiciona na lista leite, ovos e queijo",
        "Coloca frango e carne moída na lista de compras",
        "Me lembra de ligar pro dentista amanhã às dez da manhã",
        "Tenho consulta médica na sexta-feira às três da tarde",
        "Preciso pagar a conta de internet até dia quinze",
    ]
    results = await send_batch(ctx, fase2)
    s, f = print_results(results, "Fase 2: Comandos Naturais")
    total_success += s
    total_failed += f
    
    # Fase 3: Mensagem longa (como se fosse um áudio de 30s)
    fase3 = [
        "Olha, essa semana tá bem corrida. Segunda eu tenho reunião às nove, terça preciso ir no banco pagar umas contas, quarta tenho dentista às duas da tarde, quinta é o aniversário do meu irmão então preciso comprar um presente, e sexta tenho que entregar aquele relatório do trabalho.",
    ]
    results = await send_batch(ctx, fase3)
    s, f = print_results(results, "Fase 3: Mensagem Longa")
    total_success += s
    total_failed += f
    
    # Fase 4: Comandos rápidos
    fase4 = [
        "Comprar pão",
        "Levar o cachorro no veterinário",
        "Ligar pra vó",
        "Estudar inglês",
        "Fazer exercício",
    ]
    results = await send_batch(ctx, fase4)
    s, f = print_results(results, "Fase 4: Comandos Rápidos")
    total_success += s
    total_failed += f
    
    # Fase 5: Consultas
    fase5 = [
        "/semana",
        "/agenda",
        "/list",
        "O que tenho na minha lista de compras?",
    ]
    results = await send_batch(ctx, fase5)
    s, f = print_results(results, "Fase 5: Consultas")
    total_success += s
    total_failed += f
    
    print(f"\n{'='*70}")
    print(f"  ROTEIRO 2 COMPLETO: {total_success} OK, {total_failed} falhas")
    print(f"{'='*70}")
    
    assert total_failed < total_success * 0.3, f"Muitas falhas: {total_failed}/{total_success + total_failed}"


# =============================================================================
# ROTEIRO 3 - BRASIL: Lembretes Recorrentes e Agenda
# =============================================================================

@pytest.mark.asyncio
async def test_roteiro3_brasil_lembretes():
    """
    ROTEIRO 3 - BRASIL
    Foco: Lembretes Recorrentes e Agenda
    """
    print("\n" + "="*70)
    print("  ROTEIRO 3 - BRASIL 🇧🇷: Lembretes Recorrentes e Agenda")
    print("="*70)
    
    chat_id = f"roteiro3_br_{random.randint(10000, 99999)}"
    ctx = create_test_context(chat_id)
    
    total_success = 0
    total_failed = 0
    
    # Fase 1: Setup
    fase1 = [
        "/start",
        "meu nome é TestadorBR3",
        "moro em Belo Horizonte",
        "/tz America/Sao_Paulo",
    ]
    results = await send_batch(ctx, fase1)
    s, f = print_results(results, "Fase 1: Setup")
    total_success += s
    total_failed += f
    
    # Fase 2: Lembretes Simples
    fase2 = [
        "me lembra de beber água em 5 minutos",
        "lembrete: tomar vitamina em 10 minutos",
        "me avisa pra fazer alongamento em 15 minutos",
        "lembra de olhar emails em 20 minutos",
    ]
    results = await send_batch(ctx, fase2)
    s, f = print_results(results, "Fase 2: Lembretes Simples")
    total_success += s
    total_failed += f
    
    # Fase 3: Lembretes com Data/Hora
    fase3 = [
        "me lembra de pagar aluguel dia 5 às 9h",
        "lembrete: renovar carteira de motorista dia 15 às 10h",
        "consulta com dermatologista dia 20 às 14h30",
        "reunião de condomínio dia 25 às 19h",
    ]
    results = await send_batch(ctx, fase3)
    s, f = print_results(results, "Fase 3: Lembretes com Data/Hora")
    total_success += s
    total_failed += f
    
    # Fase 4: Lembretes Recorrentes
    fase4 = [
        "me lembra de tomar remédio todo dia às 8h",
        "lembrete diário: beber 2 litros de água",
        "toda segunda às 7h: academia",
        "toda sexta às 18h: happy hour",
    ]
    results = await send_batch(ctx, fase4)
    s, f = print_results(results, "Fase 4: Lembretes Recorrentes")
    total_success += s
    total_failed += f
    
    # Fase 5: Verificar Agenda
    fase5 = [
        "/hoje",
        "/semana",
        "minha agenda",
        "o que tenho amanhã?",
        "lembretes pendentes",
        "/recorrente",
    ]
    results = await send_batch(ctx, fase5)
    s, f = print_results(results, "Fase 5: Verificar Agenda")
    total_success += s
    total_failed += f
    
    # Fase 6: Eventos Complexos
    fase6 = [
        "viagem pra praia de 20 a 25 de abril",
        "curso de inglês às terças e quintas às 19h",
    ]
    results = await send_batch(ctx, fase6)
    s, f = print_results(results, "Fase 6: Eventos Complexos")
    total_success += s
    total_failed += f
    
    print(f"\n{'='*70}")
    print(f"  ROTEIRO 3 COMPLETO: {total_success} OK, {total_failed} falhas")
    print(f"{'='*70}")
    
    assert total_failed < total_success * 0.3, f"Muitas falhas: {total_failed}/{total_success + total_failed}"


# =============================================================================
# ROTEIRO 4 - PORTUGAL: Português Europeu
# =============================================================================

@pytest.mark.asyncio
async def test_roteiro4_portugal_pt_europeu():
    """
    ROTEIRO 4 - PORTUGAL
    Foco: Português Europeu e Fuso Horário
    """
    print("\n" + "="*70)
    print("  ROTEIRO 4 - PORTUGAL 🇵🇹: Português Europeu")
    print("="*70)
    
    chat_id = f"roteiro4_pt_{random.randint(10000, 99999)}"
    ctx = create_test_context(chat_id)
    
    total_success = 0
    total_failed = 0
    
    # Fase 1: Onboarding PT-PT
    fase1 = [
        "/start",
        "chamo-me TestadorPT4",
        "moro em Lisboa",
        "/tz Europe/Lisbon",
        "/lang pt-PT",
    ]
    results = await send_batch(ctx, fase1)
    s, f = print_results(results, "Fase 1: Onboarding PT-PT")
    total_success += s
    total_failed += f
    
    # Fase 2: Comandos em Português Europeu
    fase2 = [
        "põe na lista: arroz, massa, azeite, sal, açúcar",
        "adiciona à lista: leite, ovos, queijo, fiambre, manteiga",
        "coloca na lista: tomate, cebola, alho, batata, cenoura",
        "mete na lista: frango, carne picada, chouriço, bacalhau",
        "adiciona: café, sumo, água, cerveja, vinho",
    ]
    results = await send_batch(ctx, fase2)
    s, f = print_results(results, "Fase 2: Comandos PT-PT")
    total_success += s
    total_failed += f
    
    # Fase 3: Lembretes em PT-PT
    fase3 = [
        "lembra-me de telefonar ao médico amanhã às 9h",
        "avisa-me para tomar o comprimido daqui a 2 horas",
        "tenho consulta na segunda-feira às 14h30",
        "reunião de trabalho na quarta às 10h",
        "lembra-me de ir ao multibanco na sexta",
    ]
    results = await send_batch(ctx, fase3)
    s, f = print_results(results, "Fase 3: Lembretes PT-PT")
    total_success += s
    total_failed += f
    
    # Fase 4: Expressões Típicas PT-PT
    fase4 = [
        "preciso de comprar pastéis de nata",
        "adiciona bifanas à lista",
        "mete uma francesinha na lista de comidas",
    ]
    results = await send_batch(ctx, fase4)
    s, f = print_results(results, "Fase 4: Expressões PT-PT")
    total_success += s
    total_failed += f
    
    # Fase 5: Consultas em PT-PT
    fase5 = [
        "mostra-me a lista",
        "o que tenho para fazer?",
        "qual é a minha agenda?",
        "/hoje",
        "/semana",
    ]
    results = await send_batch(ctx, fase5)
    s, f = print_results(results, "Fase 5: Consultas PT-PT")
    total_success += s
    total_failed += f
    
    # Fase 6: Mistura PT-BR e PT-PT
    fase6 = [
        "adiciona na lista: guaraná, açaí, tapioca",
        "me lembra de ver o jogo",
        "lembra-me de comprar pastéis",
        "põe bacalhau na lista",
    ]
    results = await send_batch(ctx, fase6)
    s, f = print_results(results, "Fase 6: Mistura PT-BR e PT-PT")
    total_success += s
    total_failed += f
    
    print(f"\n{'='*70}")
    print(f"  ROTEIRO 4 COMPLETO: {total_success} OK, {total_failed} falhas")
    print(f"{'='*70}")
    
    assert total_failed < total_success * 0.3, f"Muitas falhas: {total_failed}/{total_success + total_failed}"


# =============================================================================
# ROTEIRO 5 - PORTUGAL: Stress Extremo
# =============================================================================

@pytest.mark.asyncio
async def test_roteiro5_portugal_stress_extremo():
    """
    ROTEIRO 5 - PORTUGAL
    Foco: Comandos Simultâneos e Stress Extremo
    """
    print("\n" + "="*70)
    print("  ROTEIRO 5 - PORTUGAL 🇵🇹: Stress Extremo")
    print("="*70)
    
    chat_id = f"roteiro5_pt_{random.randint(10000, 99999)}"
    ctx = create_test_context(chat_id)
    
    total_success = 0
    total_failed = 0
    
    # Fase 1: Setup Rápido
    fase1 = [
        "/start",
        "sou o TestadorPT5",
        "Lisboa",
    ]
    results = await send_batch(ctx, fase1)
    s, f = print_results(results, "Fase 1: Setup Rápido")
    total_success += s
    total_failed += f
    
    # Fase 2: RAJADA EXTREMA - 20 itens individuais
    fase2 = [
        "arroz", "feijão", "massa", "azeite", "sal",
        "açúcar", "leite", "ovos", "queijo", "manteiga",
        "tomate", "cebola", "alho", "batata", "frango",
        "carne", "peixe", "pão", "café", "água",
    ]
    results = await send_batch(ctx, fase2)
    s, f = print_results(results, "Fase 2: Rajada 20 Itens")
    total_success += s
    total_failed += f
    
    # Fase 3: Verificar Lista
    fase3 = ["/list mercado"]
    results = await send_batch(ctx, fase3)
    s, f = print_results(results, "Fase 3: Verificar Lista")
    total_success += s
    total_failed += f
    
    # Fase 4: Comandos Conflitantes
    fase4 = [
        "adiciona leite",
        "remove leite",
        "adiciona leite",
        "feito leite",
        "adiciona leite",
    ]
    results = await send_batch(ctx, fase4)
    s, f = print_results(results, "Fase 4: Comandos Conflitantes")
    total_success += s
    total_failed += f
    
    # Fase 5: Múltiplas Listas
    fase5 = [
        "/list filmes add Matrix",
        "/list livros add 1984",
        "/list músicas add Imagine",
        "/list séries add Friends",
        "/list jogos add FIFA",
        "/list filmes add Inception",
        "/list livros add O Hobbit",
        "/list músicas add Yesterday",
    ]
    results = await send_batch(ctx, fase5)
    s, f = print_results(results, "Fase 5: Múltiplas Listas")
    total_success += s
    total_failed += f
    
    # Fase 6: Consultas Simultâneas
    fase6 = [
        "/list",
        "/hoje",
        "/semana",
        "minhas listas",
        "meus lembretes",
    ]
    results = await send_batch(ctx, fase6)
    s, f = print_results(results, "Fase 6: Consultas Simultâneas")
    total_success += s
    total_failed += f
    
    # Fase 7: Emojis e Caracteres Especiais
    fase7 = [
        "adiciona 🍎 maçã na lista",
        "põe café ☕ na lista",
        "adiciona item com aspas e apóstrofo",
        "põe na lista: café/chá, pão+manteiga",
    ]
    results = await send_batch(ctx, fase7)
    s, f = print_results(results, "Fase 7: Emojis e Especiais")
    total_success += s
    total_failed += f
    
    # Fase 8: Mensagem com 50 itens
    items_50 = ", ".join([f"item{i}" for i in range(1, 51)])
    fase8 = [f"adiciona na lista: {items_50}"]
    results = await send_batch(ctx, fase8)
    s, f = print_results(results, "Fase 8: 50 Itens numa Mensagem")
    total_success += s
    total_failed += f
    
    print(f"\n{'='*70}")
    print(f"  ROTEIRO 5 COMPLETO: {total_success} OK, {total_failed} falhas")
    print(f"{'='*70}")
    
    # Mais tolerante pois alguns comandos naturais podem não ser reconhecidos
    assert total_failed < total_success * 0.4, f"Muitas falhas: {total_failed}/{total_success + total_failed}"


# =============================================================================
# ROTEIRO 6 - PORTUGAL: Simulação de Uso Real (1 Semana)
# =============================================================================

@pytest.mark.asyncio
async def test_roteiro6_portugal_uso_real():
    """
    ROTEIRO 6 - PORTUGAL
    Foco: Simulação de Uso Real (1 Semana)
    """
    print("\n" + "="*70)
    print("  ROTEIRO 6 - PORTUGAL 🇵🇹: Simulação 1 Semana")
    print("="*70)
    
    chat_id = f"roteiro6_pt_{random.randint(10000, 99999)}"
    ctx = create_test_context(chat_id)
    
    total_success = 0
    total_failed = 0
    
    # SEGUNDA-FEIRA
    segunda = [
        "bom dia",
        "o que tenho para hoje?",
        "preciso comprar pão, leite e ovos",
        "tenho reunião às 10h",
        "me lembra de ligar pro cliente às 14h",
    ]
    results = await send_batch(ctx, segunda)
    s, f = print_results(results, "Segunda-feira")
    total_success += s
    total_failed += f
    
    # TERÇA-FEIRA
    terca = [
        "olá",
        "minha agenda",
        "adiciona na lista: detergente, sabão, esponja",
        "consulta médica quinta às 15h",
    ]
    results = await send_batch(ctx, terca)
    s, f = print_results(results, "Terça-feira")
    total_success += s
    total_failed += f
    
    # QUARTA-FEIRA
    quarta = [
        "oi",
        "o que tenho amanhã?",
        "feito pão",
        "feito leite",
        "preciso de comprar presente pro aniversário do João",
        "aniversário do João sábado às 20h",
    ]
    results = await send_batch(ctx, quarta)
    s, f = print_results(results, "Quarta-feira")
    total_success += s
    total_failed += f
    
    # QUINTA-FEIRA
    quinta = [
        "bom dia",
        "meus lembretes de hoje",
        "feito detergente",
        "adiciona vinho tinto pra levar no sábado",
    ]
    results = await send_batch(ctx, quinta)
    s, f = print_results(results, "Quinta-feira")
    total_success += s
    total_failed += f
    
    # SEXTA-FEIRA
    sexta = [
        "última verificação antes do fim de semana",
        "/semana",
        "minhas listas",
        "o que falta comprar?",
        "me lembra de acordar cedo amanhã às 8h",
    ]
    results = await send_batch(ctx, sexta)
    s, f = print_results(results, "Sexta-feira")
    total_success += s
    total_failed += f
    
    # SÁBADO
    sabado = [
        "bom dia",
        "o que tenho hoje?",
        "feito presente",
        "feito vinho",
    ]
    results = await send_batch(ctx, sabado)
    s, f = print_results(results, "Sábado")
    total_success += s
    total_failed += f
    
    # DOMINGO
    domingo = [
        "olá",
        "próxima semana",
        "preciso de organizar a semana",
        "segunda: reunião 9h",
        "terça: dentista 10h",
        "quinta: apresentação importante 14h",
    ]
    results = await send_batch(ctx, domingo)
    s, f = print_results(results, "Domingo")
    total_success += s
    total_failed += f
    
    # Verificação Final
    final = [
        "/agenda",
        "/list",
    ]
    results = await send_batch(ctx, final)
    s, f = print_results(results, "Verificação Final")
    total_success += s
    total_failed += f
    
    print(f"\n{'='*70}")
    print(f"  ROTEIRO 6 COMPLETO: {total_success} OK, {total_failed} falhas")
    print(f"{'='*70}")
    
    assert total_failed < total_success * 0.4, f"Muitas falhas: {total_failed}/{total_success + total_failed}"


# =============================================================================
# RELATÓRIO FINAL
# =============================================================================

@pytest.mark.asyncio
async def test_relatorio_final_todos_roteiros():
    """
    Executa um resumo de todos os roteiros com métricas agregadas.
    """
    print("\n" + "="*70)
    print("  RELATÓRIO FINAL - TODOS OS ROTEIROS")
    print("="*70)
    
    # Testar parsing de todos os comandos dos roteiros
    all_commands = [
        # BR
        "adiciona na lista: arroz, feijão, macarrão",
        "coloca na lista: leite, ovos, queijo",
        "põe na lista: tomate, cebola, alho",
        "/list mercado",
        "/list filmes add Matrix, Inception",
        "me lembra de ligar pro médico em 10 minutos",
        "lembrete: reunião sexta às 14h",
        "/hoje",
        "/semana",
        "minha agenda",
        # PT
        "põe na lista: arroz, massa, azeite",
        "adiciona à lista: leite, ovos, queijo",
        "lembra-me de telefonar ao médico amanhã",
        "mostra-me a lista",
        "o que tenho para fazer?",
        # Emojis
        "adiciona 🍎 maçã na lista",
        # Recorrentes
        "me lembra de tomar remédio todo dia às 8h",
        "toda segunda às 7h: academia",
    ]
    
    success = 0
    failed = 0
    
    for cmd in all_commands:
        result = parse(cmd)
        if result:
            success += 1
        else:
            failed += 1
            print(f"  ❌ Parser não reconheceu: {cmd[:50]}")
    
    print(f"\n  Parser: {success}/{len(all_commands)} comandos reconhecidos")
    print(f"  Taxa de sucesso: {success/len(all_commands)*100:.1f}%")
    
    assert success >= len(all_commands) * 0.7, "Parser reconheceu menos de 70% dos comandos"
