# Backend WhatsApp AI Organizer — MVP

Base: Zapista (só WhatsApp, cron, organizador). Este backend adiciona listas, eventos, filtro de escopo e API FastAPI.

## Estrutura

- **backend/** — DB (SQLite), models (User, List, Event, AuditLog), scope filter, FastAPI
- **prompts/** — scope_filter.txt (para LLM opcional)
- **zapista/agent/tools/list_tool.py** — list add/list/remove/feito
- **zapista/agent/tools/event_tool.py** — event add/list (filme, livro, musica)
- **app.py** — sobe a API (uvicorn)

## Comandos texto (WhatsApp)

Comandos são **parseados primeiro** e executados direto (sem chamada ao LLM):

- **`/lembrete texto daqui a 2 min`** ou **`/lembrete texto em 5 minutos`** → cron (in_seconds); "todo dia" → cron 9h. Se o tempo não for reconhecido, cai no LLM.
- **`/list mercado add leite`** → list add
- **`/list pendentes`** → lista itens da lista "pendentes"
- **`/list`** → lista os nomes das listas
- **`/feito mercado 1`** → marca e remove item 1 da lista mercado. **`/feito 1`** → pede "Use: /feito nome_da_lista id"
- **`/filme Nome do Filme`** → event add tipo=filme

Parser em **backend/command_parser.py**; execução em **AgentLoop._execute_parsed_intent**.

## Rodar MVP local

1. **API (porta 8000)**  
   Na raiz do projeto:
   ```bash
   py -3.14 -m uvicorn backend.app:app --reload --port 8000
   ```
   Ou: `python app.py`

2. **Gateway (WhatsApp + agente)**  
   Em outro terminal:
   ```bash
   py -3.14 -m zapista gateway
   ```
   Configure `~/.zapista/config.json` (openrouter apiKey, channels.whatsapp.enabled + allowFrom).

3. **Testes**
   ```bash
   py -3.14 -m pytest tests/test_backend.py tests/test_agent_organizer.py -v
   ```

## Docker

```bash
docker-compose up -d
# API: http://localhost:8000
# Gateway: porta 18790 (bridge WhatsApp)
```

Volume `ZAPISTA_data` persiste config e DB em `~/.zapista` (ou equivalente no container).

## API (frontend irmão)

- `GET /health` — ok
- `GET /users` — lista usuários (phone_truncated)
- `GET /users/{user_id}/lists` — listas do usuário
- `GET /users/{user_id}/events?tipo=filme` — eventos
- `GET /audit` — log de ações (audit)

## Segurança MVP

- PII: phone armazenado truncado (55119***9999); lookup por hash(phone).
- Audit: tabela audit_log (user_id, action, resource).
- Sem cripto em repouso no MVP; prod: SQLCipher ou volume cripto.
- **Rate-limit**: 15 mensagens por minuto por usuário (channel:chat_id). Ao ultrapassar, resposta fixa: "Muitas mensagens. Aguarde um minuto." Configurável em `backend/rate_limit.py` (DEFAULT_MAX_PER_MINUTE, DEFAULT_WINDOW_SECONDS).
