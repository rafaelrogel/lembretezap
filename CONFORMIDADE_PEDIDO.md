# Conformidade com o pedido: Backend WhatsApp AI Organizer

Checklist do que foi pedido vs estado atual do código.

---

## ✅ Conforme

| Pedido | Estado no código |
|--------|-------------------|
| **Fork HKUDS/zapista** (leve, WhatsApp/Baileys, cron, canais) | Base zapista com canal WhatsApp (Baileys), cron nativo, agent loop. |
| **Bot "secretária organizada" para 100 users** | Escopo organizador; rate-limit por user; 1 número WhatsApp. |
| **Escopo estrito: lembretes, listas, compras, eventos, filmes** | Scope filter (LLM SIM/NÃO + regex) + parser de comandos. |
| **Filtro LLM "Analise se input é agenda/lembrete/lista; ignore resto"** | `backend/scope_filter.py`: `is_in_scope_llm()` + `prompts/scope_filter.txt`. |
| **Comandos /lembrete "X em 2min"** | `command_parser.py`: /lembrete com daqui a N min/hora/dia, cron. |
| **/list mercado add leite, /list pendentes** | Parser: list_add, list_show; ListTool: add, list. |
| **/feito (delete)** | Parser: /feito lista id; ListTool: feito = marca e **apaga** item (sem histórico). |
| **/filme nome** | Parser + EventTool tipo=filme. |
| **Memória per-user** | SQLite: User(phone_hash, phone_truncated), List(user_id), Event(user_id). |
| **PII truncada** | `_truncate_phone()` → 55119***9999; só hash + truncado guardados. |
| **Delete auto pós-confirma; não no histórico** | ListTool._feito: `db.delete(item)` + AuditLog; item removido. |
| **Segurança: min data, logs audit** | AuditLog (user_id, action, resource); API `/audit`. |
| **Rate-limit anomalia** | `backend/rate_limit.py`: por channel:chat_id, N msg/min. |
| **Backend FastAPI para frontend irmão** | `backend/app.py`: /health, /users, /users/{id}/lists, /users/{id}/events, /audit. |
| **Cron nativo zapista** | CronService no gateway; CronTool no agente; entrega no WhatsApp. |
| **Estrutura: customize whatsapp + agent loop (scope filter)** | channels/whatsapp.py; agent/loop.py com scope filter antes do LLM. |
| **DB: User(id,phone), List(user_id,nome,itens[]), Event(user_id,tipo,data,recorrente)** | models_db.py: User, List, ListItem, Event (payload JSON; data_at; recorrente). |
| **Tools: add/remove/list/delete/notify** | list: add/list/remove/feito; event: add/list; cron (notify/lembrete). |
| **Dockerfile, docker-compose.yml** | Dockerfile (Python+Node, bridge+gateway); docker-compose (bridge, gateway, api). |
| **app.py, models** | backend/app.py; backend/models_db.py. |
| **prompts/** | prompts/scope_filter.txt. |
| **Tests** | tests/test_agent_organizer.py, test_backend.py, etc. |
| **MVP rodando local** | PASSO_A_PASSO_TESTE.md, TESTAR_COM_DOCKER.md. |

---

## ⚠️ Parcial ou diferente

| Pedido | Estado | Nota |
|--------|--------|------|
| **SQLite cripto** | SQLite **sem** criptografia em repouso | FEASIBILITY: MVP sem cripto; prod pode usar SQLCipher ou volume cripto. |
| **NER LLM: detect nomes/produtos/datas** | Não implementado como passo separado | Parser usa regex para tempos (/lembrete). NER explícito (nomes/produtos/datas) não está no fluxo. |
| **Groq Llama3.1 para chat/NER** | Provedor configurável (OpenRouter, etc.) | Qualquer provider LiteLLM; pode configurar Groq no config. Não forçado a Groq. |
| **Filtro LLM local Ollama/Llama3.2** | Scope filter usa o **mesmo** provider/model do agente | Pedido era “LLM local Ollama/Llama3.2”; hoje usa o provider configurado (pode ser Ollama no config). |
| **/feito 1 (delete)** sem nome da lista | Hoje exige `/feito nome_da_lista id` | Parser: /feito 1 → list_name=None → resposta “Use: /feito nome_da_lista id”. Não há “/feito 1” sozinho. |
| **/list remove, delete** | Remove por list_name + item_id | “remove” existe na tool; comando explícito /list X delete/remove não está no parser (só /feito). |
| **Livros/músicas** como comandos | Só `/filme nome` no parser | EventTool tem tipo livros/músicas; não há /livro ou /musica no command_parser. |
| **Docker Compose (Redis queue)** | Sem Redis no compose | docker-compose só bridge + gateway + api; sem Redis. |

---

## ❌ Em falta

| Pedido | Ação sugerida |
|--------|----------------|
| **Redis queue** no deploy | Adicionar serviço `redis` no docker-compose e (se quiser) fila para tarefas assíncronas. |
| **NER LLM** (nomes, produtos, datas) | Opcional: passo no agent (ou tool) que chama LLM para extrair entidades e preencher listas/eventos. |
| **SQLite cripto** (prod) | Para produção: SQLCipher ou volume criptografado; fora do MVP. |

---

## Resumo

- **Conforme:** Base zapista + WhatsApp, escopo organizador, filtro de scope (LLM + regex), comandos /lembrete, /list, /feito, /filme, memória per-user, PII truncada, delete pós-confirma sem histórico, audit log, rate-limit, FastAPI, Docker, cron nativo, estrutura DB e tools, prompts, testes, MVP local.
- **Parcial:** SQLite sem cripto (MVP), NER não implementado, Groq/Ollama não obrigatórios, /feito exige nome da lista, Redis não está no compose.
- **Em falta:** Redis no compose; NER opcional; cripto em repouso para prod.

O código está **em grande medida conforme** ao pedido; as principais lacunas são Redis no deploy, NER explícito e cripto do DB (previsto para além do MVP).
