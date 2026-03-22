"""Análise contextual com Mimo (LLM barato) para identificar intenções baseadas no histórico.
Útil para títulos de livros, itens de mercado ou tarefas que não seguem um padrão rígido.
"""

import json
from typing import Any, Dict, List, Optional
from backend.logger import get_logger
logger = get_logger(__name__)

_CONTEXT_REASONER_PROMPT = """Analise o histórico da conversa e a mensagem atual do utilizador.
O utilizador pode estar a falar sobre uma lista específica (livros, compras, mercado, tarefas, filmes, etc.).

Contexto extra:
- Última lista ativa: {last_list}

Histórico recente:
{history}

Mensagem atual: "{current}"

Determine se a mensagem atual é um pedido para ADICIONAR algo a uma lista.
REGRAS IMPORTANTES:
1. Se a mensagem diz apenas "adicione [item]", use a "Última lista ativa" se esta fizer sentido.
2. Ignore palavras de preenchimento/conectores como "aí", "ai", "ali", "aqui" (Portuguese fillers) - NUNCA as use como nome de lista.
3. Se a mensagem for "Adicione aí X", o item é "X" e o nome da lista deve ser inferido do histórico ou da "Última lista ativa".
4. Normalize os nomes das listas para o plural (ex: filme -> filmes, livro -> livros).
5. O sistema suporta 4 línguas (Português PT e BR, Inglês e Espanhol). Mapeie termos equivalentes para os nomes de lista em Português plural (filmes, livros, músicas, séries, jogos, receitas, notas, mercado).

Responda APENAS com um objeto JSON válido (sem markdown), com este formato:
{{
  "is_list_item": true/false,
  "list_name": "nome_da_lista_em_plural" (ex: filmes, mercado, livros, tarefas, notas),
  "item": "o item limpo"
}}

Se não for um pedido de adição à lista, "is_list_item" deve ser false.
Se for uma lista de "afazeres" ou "pendentes", normalize para "tarefas".
"""

async def classify_intent_with_full_context(
    history: List[Dict[str, str]],
    current_content: str,
    provider: Any,
    model: str,
    last_list: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Usa o Mimo para classificar a intenção com base no histórico e última lista ativa.
    Retorna um dicionário com 'type': 'list_add' e os detalhes, ou None.
    """
    if not current_content or not provider:
        return None

    try:
        # Formatar histórico para o prompt (máx 10 mensagens)
        history_text = ""
        for m in history[-10:]:
            role = "Utilizador" if m.get("role") == "user" else "Assistente"
            content = (m.get("content") or "")[:200]
            history_text += f"{role}: {content}\n"

        prompt = _CONTEXT_REASONER_PROMPT.format(
            history=history_text,
            current=current_content,
            last_list=last_list or "(nenhuma)"
        )

        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            temperature=0,
            max_tokens=200
        )

        if not response or not response.content:
            return None

        # Limpar resposta (remover blocos de código se houver)
        raw = response.content.strip()
        if raw.startswith("```json"):
            raw = raw[7:-3].strip()
        elif raw.startswith("```"):
            raw = raw[3:-3].strip()

        data = json.loads(raw)
        if data.get("is_list_item") is True and data.get("list_name") and data.get("item"):
            return {
                "type": "list_add",
                "list_name": data["list_name"],
                "item": data["item"]
            }

    except Exception as e:
        logger.debug("context_reasoner_failed", extra={"extra": {"error": str(e)}})
    
    return None
