# Guia para contribuir

Obrigado por contribuir. Estes pontos ajudam a manter qualidade e consistência.

## Pull requests

- **Testes:** Novas funcionalidades devem incluir testes (ex.: `tests/`). Execute `uv run pytest tests/` antes de abrir o PR.
- **Documentação:** Novos módulos ou endpoints devem ter docstrings (módulo, funções e classes públicas). Endpoints da API são documentados via OpenAPI (FastAPI); complete a descrição e exemplos quando fizer sentido.
- **Type hints:** Preferir type hints em assinaturas de funções e métodos em código novo. Em alterações a código existente, adicione tipos quando tocar nas assinaturas.
- **Segurança:** Não commitar chaves, tokens ou dados sensíveis. Use variáveis de ambiente e documente-as em `.env.example` e em `DEPLOY.md` ou `SECURITY.md` quando relevante.
- **Linter:** O projeto usa Ruff (ver `pyproject.toml`). Execute `uv run ruff check .` e corrija avisos em código novo.

## Estrutura do projeto

- **backend/** — API FastAPI (app, auth, routes), parser, DB, sanitização, rate limit.
- **nanobot/** — Core do bot: agente, canais, cron, providers, CLI.
- **bridge/** — Servidor Node/TypeScript para WhatsApp (Baileys).
- **tests/** — Testes com pytest; `conftest.py` adiciona a raiz ao path.
- **workspace/** — Documentação de arquitetura e planos (`ARCHITECTURE.md`, `PLANO_IMPLEMENTACAO.md`).

## Reportar problemas de segurança

Não abra issues públicas para vulnerabilidades. Consulte a secção “Reporting a Vulnerability” em [SECURITY.md](SECURITY.md).
