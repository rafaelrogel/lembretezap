"""Métricas de uso de tokens por provedor (DeepSeek, Mimo). Para #ai admin.

Registo via record_usage() (chamado do provider após cada completion).
Agora persiste no banco de dados (tabela TokenUsage).

Preços (USD por 1M tokens):
DeepSeek: Input $0.14, Cache Hit $0.014, Output $0.28
Mimo: Input $0.10, Cache Hit $0.01, Output $0.30
"""

from datetime import date, timedelta
from typing import Any
from sqlalchemy import func
from backend.database import SessionLocal
from backend.models_db import TokenUsage

# Preços por 1M tokens (USD)
PRICE_PER_1M = {
    "xiaomi": {
        "input": 0.10,
        "cache_hit": 0.01,
        "output": 0.30,
    },
    "deepseek": {
        "input": 0.14,
        "cache_hit": 0.014,
        "output": 0.28,
    },
    # Fallback default
    "default": {
        "input": 0.10,
        "cache_hit": 0.01,
        "output": 0.30,
    }
}

def _derive_provider(model: str) -> str:
    """De model string devolve 'deepseek', 'mimo' ou 'other'."""
    if not model:
        return "other"
    m = model.lower()
    if "deepseek" in m:
        return "deepseek"
    if "xiaomi" in m or "mimo" in m:
        return "mimo"
    return "other"

def calculate_cost(provider: str, input_tokens: int, output_tokens: int, cached_tokens: int) -> float:
    # Normalize provider key
    p_key = "default"
    if "deepseek" in provider.lower(): p_key = "deepseek"
    elif "xiaomi" in provider.lower() or "mimo" in provider.lower(): p_key = "xiaomi"
    
    prices = PRICE_PER_1M.get(p_key, PRICE_PER_1M["default"])
    
    cost_input = (input_tokens / 1_000_000) * prices["input"]
    cost_cache = (cached_tokens / 1_000_000) * prices["cache_hit"]
    cost_output = (output_tokens / 1_000_000) * prices["output"]
    
    return cost_input + cost_cache + cost_output

def record_usage(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    **kwargs: Any,
) -> None:
    """Registar uso de tokens (chamar a partir do provider/litellm)."""
    if (input_tokens or 0) <= 0 and (output_tokens or 0) <= 0:
        return

    # Normalizar provider
    provider = (provider or _derive_provider(model)).lower()
    if provider == "other":
        # Tenta derivar novamente pelo model se provider veio vazio/"other"
        provider = _derive_provider(model)
    
    # Se ainda for other, podemos registrar ou ignorar. 
    # O user pediu #ai para DeepSeek e Mimo. Vamos registrar tudo para ter histórico.

    today_str = date.today().isoformat()
    
    # Tentativa de extrair cache hit dos kwargs (se o provider passar details)
    # Atualmente litellm_provider passa input_tokens = prompt_tokens.
    # Se tivermos acesso a prompt_tokens_details, precisaríamos alterar litellm_provider.
    # Por agora, assumimos cache_hit=0 a menos que venha num kwarg específico.
    cached_tokens = kwargs.get("cached_tokens", 0)
    
    # Input cobrado (miss) = input_tokens - cached_tokens
    # (Assumindo que input_tokens é o total bruto)
    input_miss = max(0, input_tokens - cached_tokens)
    
    cost = calculate_cost(provider, input_miss, output_tokens, cached_tokens)
    
    db = SessionLocal()
    try:
        # Busca registro existente para hoje
        row = db.query(TokenUsage).filter(
            TokenUsage.provider == provider,
            TokenUsage.model == model,
            TokenUsage.date == today_str
        ).first()
        
        if not row:
            row = TokenUsage(
                provider=provider,
                model=model,
                date=today_str,
                input_tokens=0,
                output_tokens=0,
                cached_tokens=0,
                cost_usd=0.0
            )
            db.add(row)
        
        # Atualiza contadores
        row.input_tokens += input_miss
        row.output_tokens += output_tokens
        row.cached_tokens += cached_tokens
        row.cost_usd += cost
        
        db.commit()
    except Exception as e:
        # Silencioso para não quebrar fluxo principal
        pass
    finally:
        db.close()


def get_usage_summary() -> str | None:
    """Resumo para #ai: uso por provedor, por dia e últimos 7 dias; custo estimado. Sem secrets."""
    db = SessionLocal()
    try:
        # Últimos 7 dias
        start_date = (date.today() - timedelta(days=7)).isoformat()
        
        rows = db.query(TokenUsage).filter(TokenUsage.date >= start_date).all()
        
        if not rows:
            return None

        # Agregação
        today_str = date.today().isoformat()
        
        today_stats = {"cost": 0.0, "input": 0, "output": 0, "cached": 0}
        week_stats = {"cost": 0.0, "input": 0, "output": 0, "cached": 0}
        
        by_provider_week = {} # provider -> {input, output, cached, cost}

        for r in rows:
            # Week totals
            week_stats["cost"] += r.cost_usd
            week_stats["input"] += r.input_tokens
            week_stats["output"] += r.output_tokens
            week_stats["cached"] += r.cached_tokens
            
            # Today totals
            if r.date == today_str:
                today_stats["cost"] += r.cost_usd
                today_stats["input"] += r.input_tokens
                today_stats["output"] += r.output_tokens
                today_stats["cached"] += r.cached_tokens
            
            # Per provider (week)
            p_key = r.provider
            if p_key not in by_provider_week:
                by_provider_week[p_key] = {"input": 0, "output": 0, "cached": 0, "cost": 0.0}
            
            by_provider_week[p_key]["input"] += r.input_tokens
            by_provider_week[p_key]["output"] += r.output_tokens
            by_provider_week[p_key]["cached"] += r.cached_tokens
            by_provider_week[p_key]["cost"] += r.cost_usd

        lines = []
        
        # Hoje
        lines.append(f"Hoje: ${today_stats['cost']:.4f}")
        lines.append(f"  In: {today_stats['input']:,} | Out: {today_stats['output']:,} | Cache: {today_stats['cached']:,}")
        
        # 7 Dias
        lines.append("")
        lines.append(f"Últimos 7 dias: ${week_stats['cost']:.4f}")
        lines.append(f"  In: {week_stats['input']:,} | Out: {week_stats['output']:,} | Cache: {week_stats['cached']:,}")
        
        # Por provedor
        lines.append("")
        lines.append("Por provedor (7 dias):")
        for p, stats in by_provider_week.items():
            lines.append(f"  {p}: ${stats['cost']:.4f}")
            lines.append(f"    In {stats['input']:,} | Out {stats['output']:,} | Cache {stats['cached']:,}")

        return "\n".join(lines)
    finally:
        db.close()
