# Proposta: Listas com memória e aprendizagem (Mimo)

## Objetivo

O sistema lembrar-se da lista da semana passada e aprender com padrões, usando o Mimo para histórico e classificação.

## Estado atual

- **Smart reminder** já envia a Mimo: listas atuais, itens pendentes, lembretes, eventos
- **AuditLog** já guarda `list_add`, `list_feito`, `list_remove` com `payload_json` (list_name, item_text, item_id)
- **Listas** são persistidas em SQLite; itens feitos ficam com `done=True` (soft-delete) para auditoria

## O que falta implementar

### 1. Histórico de listas por semana

- Consultar `ListItem` e `AuditLog` para extrair:
  - Itens adicionados na semana N (por lista)
  - Itens marcados como feitos na semana N
- Guardar snapshots semanais opcionais (tabela `list_snapshot` ou similar) com:
  - `user_id`, `list_name`, `week_start`, `items_json` (lista de itens no início da semana)
  - Ou inferir a partir de `ListItem.created_at` + `AuditLog`

### 2. Contexto enriquecido para o Mimo

- Em `smart_reminder` e noutros fluxos, incluir no contexto:
  - **Lista da semana passada**: itens que estavam em cada lista há 7 dias
  - **Padrões**: "na lista mercado, costumas adicionar X, Y, Z" (frequência)
  - **Sugestões**: "Na última semana tinhas leite e pão na lista mercado; queres que eu sugira?"

### 3. Classificação e sugestões

- **Mimo** analisa:
  - Histórico de itens por lista
  - Estação, dia da semana, contexto (ex.: "depois do filme" → lista filmes)
  - Sugere itens com base em padrões: "Costumas comprar leite às segundas"
- **Integração** com o fluxo de `/list mercado add`:
  - Se o utilizador disser "adiciona o habitual" ou "lista de compras da semana", o Mimo sugere com base no histórico

### 4. Estrutura de dados proposta

```python
# Opção A: Snapshots semanais (mais simples)
class ListSnapshot(Base):
    user_id, list_name, week_start (YYYY-MM-DD), items_json, created_at

# Opção B: Usar AuditLog + ListItem (já existentes)
# Query: ListItem onde created_at na semana X, ou AuditLog list_add com payload_json
```

## Próximos passos

1. Adicionar consulta "itens da semana passada" em `backend/` (novo módulo ou em `views/`)
2. Integrar no `_format_context_for_mimo` do `smart_reminder.py`
3. Novo handler ou extensão do list_tool: quando o utilizador pede "lista habitual" ou "o que costumo comprar", chamar Mimo com histórico e devolver sugestões
4. Avaliar tabela `ListSnapshot` se as queries ao histórico forem lentas
