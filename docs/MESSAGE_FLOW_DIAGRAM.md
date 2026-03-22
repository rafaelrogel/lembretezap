# Zapista - Fluxo de Mensagem do Usuario

## Diagrama Visual: WhatsApp → list_tool.py

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              ENTRADA (WhatsApp)                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  app.py                                                                             │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  Entrypoint: uvicorn.run("backend.app:app", port=8000)                              │
│  → Apenas inicia o servidor FastAPI                                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  backend/app.py (FastAPI)                                                           │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  • init_db() no lifespan                                                            │
│  • CORS middleware                                                                  │
│  • /health endpoint                                                                 │
│  • include_router(routes.router) → REST API admin (NÃO é o fluxo WhatsApp)          │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                          ┌─────────────┴─────────────┐
                          │                           │
                          ▼                           ▼
              ┌───────────────────┐       ┌───────────────────────────────┐
              │ REST API (admin)  │       │ WhatsApp Channel (principal)  │
              │ backend/routes.py │       │ zapista/channels/whatsapp.py  │
              │ /users, /lists... │       │ WebSocket → Node.js Bridge    │
              └───────────────────┘       └───────────────────────────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  zapista/channels/whatsapp.py                                                       │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  WhatsAppChannel._handle_bridge_message(raw: str)                                   │
│  ├── Filtra grupos (só responde em chats privados)                                  │
│  ├── Deduplicação por message_id                                                    │
│  ├── Transcrição de áudio (STT) se [Voice Message]                                  │
│  ├── Parse de .ics (calendário) → ics_handler                                       │
│  ├── God Mode (#senha) → admin_commands                                             │
│  ├── /restart flow                                                                  │
│  ├── Horário silencioso check                                                       │
│  └── await self._handle_message(...) → MessageBus                                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  zapista/bus/queue.py (MessageBus)                                                  │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  • publish_inbound(InboundMessage) → fila de entrada                                │
│  • consume_inbound() → AgentLoop consome                                            │
│  • publish_outbound(OutboundMessage) → resposta ao canal                            │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  zapista/agent/loop.py (AgentLoop)                                                  │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  _process_message_impl(msg: InboundMessage)                                         │
│  ├── sanitize_string (segurança)                                                    │
│  ├── should_skip_reply (trivial: ok, tá, emoji)                                     │
│  ├── is_rate_limited (proteção spam)                                                │
│  ├── _set_tool_context(channel, chat_id)  ←── Define contexto nas tools             │
│  ├── Onboarding flow (novo utilizador)                                              │
│  ├── Language switch detection                                                      │
│  ├── Calling message ("Tá aí?")                                                     │
│  └── await self._route_and_respond(msg) ─────────────────────────────────────┐      │
└──────────────────────────────────────────────────────────────────────────────│──────┘
                                                                               │
                                                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  backend/router.py                                                                  │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  route(ctx: HandlerContext, content: str) → str | None                              │
│  ├── normalize_nl_to_command(content)  → "/lembrete X" se padrão NL                 │
│  ├── normalize_command(content)        → i18n: /recordatorio → /lembrete            │
│  ├── resolve_confirm(ctx, text)        → confirmação pendente (1=sim, 2=não)        │
│  └── for h in HANDLERS: out = await h(ctx, content)                                 │
│      │                                                                              │
│      │  HANDLERS (ordem de prioridade):                                             │
│      │  ────────────────────────────────                                            │
│      ├── handle_atendimento_request                                                 │
│      ├── handle_pending_confirmation                                                │
│      ├── handle_curated_search     ← filmes/livros/música (Perplexity)              │
│      ├── handle_list               ← LISTAS (chama list_tool) ◄───────────────────┐ │
│      ├── handle_list_or_events_ambiguous                                          │ │
│      ├── handle_vague_time_reminder                                               │ │
│      ├── handle_recurring_event                                                   │ │
│      ├── handle_eventos_unificado                                                 │ │
│      ├── handle_sacred_text                                                       │ │
│      ├── handle_limpeza                                                           │ │
│      ├── handle_pomodoro                                                          │ │
│      ├── handle_quiet                                                             │ │
│      ├── handle_recipe                                                            │ │
│      ├── handle_recurring_prompt                                                  │ │
│      ├── handle_lembrete          ← LEMBRETES (chama cron_tool)                   │ │
│      ├── handle_add                                                               │ │
│      ├── handle_start / handle_help                                               │ │
│      ├── handle_recorrente / handle_pendente                                      │ │
│      ├── handle_feito             ← MARCAR FEITO (chama list_tool)                │ │
│      ├── handle_remove            ← REMOVER (chama list_tool)                     │ │
│      ├── handle_hora_data                                                         │ │
│      ├── handle_hoje / handle_semana / handle_agenda...                           │ │
│      ├── handle_metas / handle_projetos / handle_templates                        │ │
│      ├── handle_crypto / handle_tz / handle_lang                                  │ │
│      ├── handle_resumo / handle_analytics / handle_rever                          │ │
│      ├── handle_stop / handle_reset / handle_nuke                                 │ │
│      └── return None → fallback para LLM (DeepSeek)                               │ │
└───────────────────────────────────────────────────────────────────────────────│────┘
                                                                                │
                     ┌──────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  backend/handlers.py                                                                │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  handle_list(ctx, content) / handle_add(ctx, content)                               │
│  ├── backend/command_parser/  → intent dict                                        │
│  │   Ex: {"type": "list_add", "list_name": "mercado", "item": "ovos"}               │
│  │                                                                                  │
│  ├── Se intent["type"] == "list_add":                                               │
│  │   └── ctx.list_tool.execute(action="add", list_name=..., item_text=...)          │
│  │                                                                                  │
│  ├── Se intent["type"] == "list_show":                                              │
│  │   └── ctx.list_tool.execute(action="list", list_name=...)                        │
│  │                                                                                  │
│  └── Se intent["type"] == "feito":                                                  │
│      └── ctx.list_tool.execute(action="feito", list_name=..., item_id=...)          │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  backend/command_parser/                                                            │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  parse(raw: str, tz_iana: str) → dict | None                                        │
│                                                                                     │
│  Regex patterns (PT/ES/EN):                                                         │
│  ├── RE_LEMBRETE        /lembrete X, /reminder X, /recordatorio X                   │
│  ├── RE_LIST_ADD        /list mercado add ovos                                      │
│  ├── RE_LIST_SHOW       /list mercado                                               │
│  ├── RE_FILME           /filme Eraserhead                                           │
│  ├── RE_LIVRO           /livro O Alquimista                                         │
│  ├── RE_FEITO           /feito mercado 3                                            │
│  ├── RE_REMOVE          /remove mercado 3                                           │
│  ├── RE_NL_ADICIONE     "adicione ovos e bacon à lista"                             │
│  └── ...                                                                            │
│                                                                                     │
│  Normalização de categorias:                                                        │
│  ├── filme, filmes, movie, movies, película → "filme"                               │
│  ├── livro, livros, book, books, libro → "livro"                                    │
│  ├── compras, mercado, shopping, grocery → "mercado"                                │
│  └── ...                                                                            │
│                                                                                     │
│  Retorna: {"type": "list_add", "list_name": "filme", "item": "Eraserhead"}          │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  zapista/agent/tools/list_tool.py (ListTool)                                        │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  execute(action, list_name, item_text, item_id, no_split)                           │
│  ├── set_context(channel, chat_id) ← já chamado pelo AgentLoop                      │
│  ├── get_or_create_user(db, chat_id) → User                                         │
│  │                                                                                  │
│  ├── action == "add":                                                               │
│  │   ├── sanitize_string(list_name, item_text)                                      │
│  │   ├── suggest_correction (Mimo) → corrige erros de digitação                     │
│  │   ├── _split_items("ovos, bacon e queijo") → ["ovos", "bacon", "queijo"]         │
│  │   ├── _add_single(db, user_id, list_name, item) POR CADA item                    │
│  │   │   ├── Criar List se não existe                                              │
│  │   │   ├── Deduplicação: _normalize_for_dedup (ovos == ovo)                       │
│  │   │   ├── ListItem(list_id=..., text=..., position=...)                          │
│  │   │   └── AuditLog(action="list_add")                                            │
│  │   └── CONFIRM_ITEMS_ADDED_TO_LIST (locale)                                       │
│  │                                                                                  │
│  ├── action == "list":                                                              │
│  │   └── db.query(ListItem).filter(...).order_by(position)                          │
│  │                                                                                  │
│  ├── action == "feito":                                                             │
│  │   ├── item.done = True (soft delete)                                             │
│  │   └── AuditLog(action="list_feito")                                              │
│  │                                                                                  │
│  ├── action == "remove":                                                            │
│  │   └── Similar a feito                                                            │
│  │                                                                                  │
│  ├── action == "habitual":                                                          │
│  │   └── _ask_mimo_suggestion → itens frequentes do histórico                       │
│  │                                                                                  │
│  └── action == "shuffle":                                                           │
│      └── Embaralha ordem dos itens                                                  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  backend/models_db.py (SQLAlchemy)                                                  │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  User(id, phone_truncated, tz_iana, lang, preferred_name, ...)                      │
│  List(id, user_id, name, project_id)                                                │
│  ListItem(id, list_id, text, done, position)                                        │
│  AuditLog(id, user_id, action, resource, payload_json, created_at)                  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  SQLite Database (backend/database.py)                                              │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  SessionLocal() → sessão SQLAlchemy                                                 │
│  init_db() → cria tabelas se não existem                                            │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              RESPOSTA (WhatsApp)                                    │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  OutboundMessage → MessageBus.publish_outbound → WhatsAppChannel.send               │
│  → WebSocket → Node.js Bridge → WhatsApp                                            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Resumo do Fluxo (Exemplo: "adiciona ovos à lista")

| # | Componente | Ação |
|---|------------|------|
| 1 | **WhatsApp** | Utilizador envia "adiciona ovos à lista" |
| 2 | **Node.js Bridge** | WebSocket → `whatsapp.py._handle_bridge_message()` |
| 3 | **WhatsAppChannel** | Filtra grupos, deduplica, publica `InboundMessage` no `MessageBus` |
| 4 | **AgentLoop** | Consome da fila, sanitiza, verifica rate limit |
| 5 | **AgentLoop** | `_set_tool_context()` → configura `ListTool` com `chat_id` |
| 6 | **router.py** | `normalize_nl_to_command()` → não transforma (já é NL) |
| 7 | **router.py** | Itera `HANDLERS`, `handle_list()` reconhece o padrão |
| 8 | **backend/command_parser/** | `RE_NL_ADICIONE_LISTA` captura → `{"type": "list_add", "list_name": "mercado", "item": "ovos"}` |
| 9 | **handlers.py** | `ctx.list_tool.execute(action="add", list_name="mercado", item_text="ovos")` |
| 10 | **ListTool** | `sanitize_string()`, `_add_single()`, `AuditLog`, `db.commit()` |
| 11 | **ListTool** | Retorna `"Adicionado(s) à lista mercado (1 item)."` |
| 12 | **router.py** | Retorna string para `AgentLoop` |
| 13 | **AgentLoop** | Publica `OutboundMessage` no `MessageBus` |
| 14 | **WhatsAppChannel** | `send()` → WebSocket → Node.js Bridge → WhatsApp |

---

## Componentes-Chave

### Camada de Entrada
- `app.py` / `backend/app.py` → FastAPI (REST admin + health)
- `zapista/channels/whatsapp.py` → Canal WhatsApp via WebSocket

### Camada de Processamento
- `zapista/bus/queue.py` → MessageBus (fila in-memory ou Redis)
- `zapista/agent/loop.py` → AgentLoop (orquestrador principal)
- `backend/router.py` → Dispatcher de handlers
- `backend/command_parser/` → Parser regex para comandos estruturados

### Camada de Ferramentas
- `zapista/agent/tools/list_tool.py` → Gestão de listas
- `zapista/agent/tools/cron.py` → Lembretes/cron jobs
- `zapista/agent/tools/event_tool.py` → Eventos de agenda

### Camada de Persistência
- `backend/models_db.py` → Modelos SQLAlchemy
- `backend/database.py` → Conexão SQLite
- `zapista/cron/service.py` → Armazenamento de jobs (JSON)

### Camada de Internacionalização
- `backend/locale.py` → Todas as strings localizadas (PT-BR, PT-PT, ES, EN)
- `backend/command_i18n.py` → Normalização de comandos por idioma
