# Plano de Implementação Sugerido

Este documento descreve as fases de implementação para melhorias de segurança, estrutura e qualidade do projeto. A validação é progressiva: cada fase pode ser concluída e testada antes da seguinte.

---

## Fase 1 — Melhorias de segurança críticas (≈ 1 semana)

**Objetivo:** Autenticação, CORS e revisão de permissões de endpoints.

### 1.1 Autenticação na API

- **Estado atual:** A API FastAPI (`backend/app.py`) não exige autenticação; endpoints como `/users`, `/users/{id}/lists`, `/users/{id}/events` e `/audit` estão abertos.
- **Ações sugeridas:**
  - Definir um esquema de autenticação (ex.: API key em header `X-API-Key`, ou JWT para frontend).
  - Proteger todos os endpoints de dados (exceto `/health`) com um dependency que valide o token.
  - Manter `/health` com o mecanismo atual (token opcional `X-Health-Token` para orquestração).
  - Documentar no `.env.example` e em `DEPLOY.md` as variáveis de auth (ex.: `API_SECRET_KEY`).

### 1.2 Correção de CORS

- **Estado atual:** `allow_origins=["*"]` em `backend/app.py` (qualquer origem pode chamar a API).
- **Ações sugeridas:**
  - Em produção, restringir `allow_origins` à lista de origens do frontend (ex.: `https://app.seudominio.com`).
  - Configurar via variável de ambiente (ex.: `CORS_ORIGINS`) com fallback para `*` em desenvolvimento.
  - Documentar em `DEPLOY.md` e em `SECURITY.md`.

### 1.3 Revisão de permissões de endpoints

- **Estado atual:** Qualquer cliente autenticado (quando existir auth) pode aceder a qualquer `user_id` em `/users/{user_id}/lists` e `/users/{user_id}/events`.
- **Ações sugeridas:**
  - Associar o token de API a um utilizador (ou a um scope “admin”) ou exigir que o `user_id` coincida com o utilizador autenticado (quando o conceito de “utilizador da API” estiver definido).
  - Endpoint `/audit`: restringir a roles administrativos ou a um token específico.
  - Documentar no README da API quais endpoints são públicos, por utilizador ou admin.

### Critérios de conclusão da Fase 1

- [x] Autenticação implementada e documentada (`backend/auth.py`, `X-API-Key`, `API_SECRET_KEY`).
- [x] CORS configurável e restrito em produção (`CORS_ORIGINS`).
- [x] Permissões por endpoint definidas e aplicadas (todos os dados exigem API key quando definida).
- [x] Testes de integração para auth (`test_fastapi_api_key_auth`).
- [x] `SECURITY.md` e `DEPLOY.md` atualizados.

---

## Fase 2 — Reorganização da estrutura de ficheiros (1–2 semanas)

**Objetivo:** Criar diretórios mais claros e mover código de forma incremental, mantendo a funcionalidade.

### 2.1 Definição da nova estrutura

- **Implementado:** Estrutura documentada em `workspace/ARCHITECTURE.md` (secção “Estrutura de ficheiros”).
  - `backend/` — `app.py` (app + health + CORS), `auth.py`, `routes.py`, parser, DB, sanitize, rate limit, scope filter.
  - `nanobot/` — agente, canais, cron, providers, bus, CLI (core do bot).
- Movimentações futuras (ex.: mais subpacotes) devem ser incrementais; ver ARCHITECTURE.

### 2.2 Movimentação incremental

- Mover um subconjunto de módulos de cada vez (ex.: primeiro só `backend.database` e `backend.models_db` para um pacote `backend.db`, se fizer sentido).
- Após cada movimentação:
  - Atualizar imports em todo o projeto.
  - Executar a suite de testes (`pytest tests/`).
  - Fazer commit com mensagem clara (ex.: “refactor: move X para Y”).
- Evitar movimentações massivas num único commit para facilitar revisão e rollback.

### 2.3 Compatibilidade

- Manter pontos de entrada atuais (ex.: `uvicorn backend.app:app`, `nanobot` CLI) funcionando.
- Se for necessário, adicionar re-exports em `__init__.py` durante a transição (ex.: `from backend.new.location import X`) e remover depois.

### Critérios de conclusão da Fase 2

- [ ] Estrutura de diretórios documentada em ARCHITECTURE.
- [ ] Código movido e imports atualizados.
- [ ] Todos os testes a passar; Docker e CLI a funcionar.
- [ ] Sem re-exports desnecessários ou caminhos obsoletos.

---

## Fase 3 — Documentação e type hints (contínuo)

**Objetivo:** Melhorar documentação e tipagem como parte do ciclo normal de desenvolvimento.

### 3.1 Expectativas de qualidade em Pull Requests

- Definir (em `CONTRIBUTING.md` ou no README):
  - Novos módulos devem ter docstrings (módulo, funções públicas, classes).
  - Novos endpoints devem ser documentados (OpenAPI já gera parte; completar com descrição e exemplos).
  - Type hints em assinaturas de funções e métodos novos; gradualmente em código existente quando se tocar nele.
- Opcional: configurar um linter/type checker (ex.: Ruff, mypy) no CI e exigir que não introduza erros em código novo.

### 3.2 Documentação gradual

- Ao alterar um ficheiro, adicionar ou atualizar docstrings e comentários onde faltem.
- Manter `workspace/ARCHITECTURE.md` atualizado quando houver decisões de desenho ou mudanças de estrutura.
- Documentar em `DEPLOY.md` e `SECURITY.md` qualquer nova variável de ambiente ou requisito de segurança.

### 3.3 Type hints

- Prioridade: funções públicas (API, tools, parsers) e tipos de dados partilhados (eventos, payloads).
- Não é obrigatório tipar todo o código de uma vez; preferir progressão incremental ao longo dos PRs.

### Critérios de conclusão da Fase 3 (contínuos)

- [x] CONTRIBUTING (ou equivalente) com expectativas de PR definidas (`CONTRIBUTING.md`).
- [x] Linter referido no CONTRIBUTING (Ruff em `pyproject.toml`).
- [ ] Documentação e type hints a serem adicionados de forma consistente em código novo e em alterações (contínuo).

---

## Resumo

| Fase | Duração      | Foco                                      |
|------|--------------|-------------------------------------------|
| 1    | ≈ 1 semana  | Autenticação, CORS, permissões de endpoints |
| 2    | 1–2 semanas | Reorganização de ficheiros com testes     |
| 3    | Contínuo    | Documentação, type hints, qualidade de PRs |

A Fase 1 é a mais crítica para segurança em produção. As Fases 2 e 3 melhoram manutenibilidade e sustentabilidade a longo prazo.
