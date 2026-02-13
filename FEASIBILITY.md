# Exequibilidade — Backend WhatsApp AI Organizer (100 users)

## Resumo

| Item | Exequibilidade | Notas |
|------|----------------|-------|
| Base zapista fork (WhatsApp, cron, organizer) | ✅ Feito | Já temos |
| Comandos /lembrete, /list, /feito, /filme | ✅ Alta | Parsing + tools + DB |
| Memória per-user (SQLite) | ✅ Alta | User, List, Event; PII truncada |
| Cripto SQLite / at-rest | ⚠️ Média | MVP: sem cripto; prod: SQLCipher ou volume cripto |
| Filtro scope (LLM: agenda/lista/lembrete) | ✅ Alta | 1 chamada Groq/Ollama antes do loop |
| NER (nomes, produtos, datas) | ✅ Alta | Groq/Llama no prompt ou tool |
| FastAPI para frontend irmão | ✅ Alta | API REST sobre mesmo SQLite |
| Docker + Linux VPS | ✅ Alta | Dockerfile + compose |
| Redis queue | ✅ Alta | Opcional MVP; compose já inclui |
| GDPR/LGPD (min data, audit logs) | ⚠️ Média | Schema + audit_log; delete on request |
| Rate-limit anomalia | ✅ Alta | Middleware por user_id |
| 100 users, 1 número WhatsApp | ✅ OK | Bridge 1 sessão; allowFrom por número |

## Decisões MVP

- **Filtro scope:** 1 chamada barata (Groq Llama) "input é agenda/lembrete/lista/comando? sim/não" → se não, resposta fixa.
- **Cripto:** MVP sem cripto em repouso; phone armazenado truncado (ex.: 55119***9999).
- **Listas:** Tabela List + ListItem; comandos /list nome add X, /list nome, /feito id.
- **Eventos/filmes:** Tabela Event (user_id, tipo, payload, data, recorrente); /filme nome → Event(tipo=filme).
- **Cron:** Mantém cron nativo do zapista para lembretes.
- **API:** FastAPI com CRUD listas/eventos/usuários (leitura mínima) para frontend.

## Riscos

- Bridge WhatsApp (Baileys): 1 número para 100 users; limite de uso da API/WhatsApp.
- Ollama local para filtro: exige VM com GPU/CPU boa; MVP pode usar só Groq.
