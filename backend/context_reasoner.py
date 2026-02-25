"""Análise contextual com Mimo (LLM barato) para identificar intenções baseadas no histórico.
Útil para títulos de livros, itens de mercado ou tarefas que não seguem um padrão rígido.
"""

import json
from typing import Any, Dict, List, Optional
from loguru import logger

_CONTEXT_REASONER_PROMPT = """Analise o histórico da conversa e a mensagem atual do utilizador.
O utilizador pode estar a falar sobre uma lista específica (livros, compras, mercado, tarefas, filmes, etc.).

Histórico recente:
{history}

Mensagem atual: "{current}"

Determine se a mensagem atual é um item para ser adicionado a uma dessas listas.
Considere o contexto: se as mensagens anteriores eram sobre livros, é provável que a mensagem atual seja um título de livro.

Responda APENAS com um objeto JSON válido (sem markdown), com este formato:
{{
  "is_list_item": true/false,
  "list_name": "nome_da_lista_em_singular" (ex: livro, mercado, filme, tarefa),
  "item": "o item limpo"
}}

Se não for um item de lista, "is_list_item" deve ser false.
Se for uma lista de "compras", normalize para "mercado".
Se for uma lista de "afazeres" ou "pendentes", normalize para "tarefa".
"""

async def classify_intent_with_full_context(
    history: List[Dict[str, str]],
    current_content: str,
    provider: Any,
    model: str
) -> Optional[Dict[str, Any]]:
    """
    Usa o Mimo para classificar a intenção com base no histórico.
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
            current=current_content
        )

        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            temperature=0,
            max_tokens=150
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
        logger.debug(f"Context reasoner failed: {e}")
    
    return None
