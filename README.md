# ZapAssist

**Assistente de organização por WhatsApp** — lembretes, listas e eventos.

- 📱 Um número WhatsApp (bridge Baileys)
- ⏰ Lembretes por mensagem natural ou `/lembrete`
- 📋 Listas com `/list nome add item`, `/list nome`, `/feito nome id`
- 🎬 Eventos (ex.: filmes) com `/filme Nome`
- 🤖 Agente LLM restrito ao escopo (organizador)
- 🐳 Docker: bridge + gateway + API

## Requisitos

- Python 3.11+
- Node.js (para o bridge WhatsApp)
- Chaves de API: **DeepSeek** (agente) e **Xiaomi MiMo** (scope/heartbeat), APIs diretas — ou outro provedor

## Instalação

```bash
git clone https://github.com/rafae/zapassist.git
cd zapassist
pip install -e .
```

## Configuração

Crie `~/.nanobot/config.json` (ou `%USERPROFILE%\.nanobot\config.json` no Windows). Exemplo:

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
      "model": "deepseek/deepseek-chat",
      "scopeModel": "xiaomi_mimo/mimo-v2-flash",
      "max_tokens": 2048,
      "temperature": 0.7
    }
  },
  "channels": {
    "whatsapp": {
      "enabled": true,
      "bridge_url": "ws://localhost:3001",
      "allow_from": []
    }
  },
  "providers": {
    "deepseek": { "api_key": "" },
    "xiaomi": { "api_key": "" }
  }
}
```

- `allow_from`: lista vazia = qualquer número; ou `["5511999999999"]` (país + número, sem + nem espaços).
- As chaves **DeepSeek** e **Xiaomi** põem-se no `.env` (`NANOBOT_PROVIDERS__DEEPSEEK__API_KEY`, `NANOBOT_PROVIDERS__XIAOMI__API_KEY`). Ver [DEPLOY.md](DEPLOY.md) § 1.1.

### God Mode (comandos admin)

O bot está **disponível para qualquer pessoa** no WhatsApp. Os comandos admin (`#status`, `#users`, etc.) são protegidos por **senha**:

1. Na instalação no VPS, defines uma **senha de god-mode** (guardada no `.env` como `GOD_MODE_PASSWORD`).
2. No chat, quem quiser rodar comandos admin envia **`#<senha>`** (ex.: `#minhasenha123`) — o bot responde «God-mode ativo» e a partir daí pode usar os comandos.
3. A ativação dura **24 horas** por chat; depois é preciso enviar `#<senha>` de novo.
4. Se alguém enviar **`#` com senha errada** ou **`#comando` sem ter ativado**, o bot **não responde** (silêncio total).

**Comandos (após ativar com #senha):**

| Comando   | Conteúdo |
|-----------|----------|
| `#status` | Resumo e lista de comandos |
| `#users`  | Total de utilizadores registados (DB) |
| `#paid`   | Total pagantes (critério a definir) |
| `#cron`   | N.º de jobs agendados, último/next run |
| `#server` | RAM, CPU (load), disco (psutil) |
| `#system` | Erros 60 min, latência (estrutura para métricas) |
| `#ai`     | Uso de tokens por provedor (dia/7d; a implementar) |
| `#painpoints` | Jobs atrasados, endpoints lentos (heurísticas) |

**Exemplo de output (admin envia `#users`):**
```
#users
Total: 12 utilizadores registados.
```

**Exemplo de output (`#server`):**
```
#server
RAM: 45% usado | livre: 2.1G
Load (1m): N/A (Windows)
Disco: 62% usado | livre: 120.5G
```

Segurança: as respostas **nunca** incluem secrets (tokens, API keys, connection strings).

### O bot não responde a ninguém / ao cliente

1. **Por defeito qualquer pessoa pode falar com o bot** (instalação VPS usa `allow_from: []`). Se não há resposta, vê os logs do gateway: `docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f gateway`. Confirma que aparecem linhas como "WhatsApp from sender ..." e que o bridge está ligado (`docker compose logs bridge`, QR escaneado).
2. **God Mode:** Envia `#<tua_senha>` para ativar; depois podes usar `#status`, `#users`, etc. Senha errada = o bot não responde (silêncio).

## Uso

1. **Inicializar:** `zapassist onboard`
2. **Bridge WhatsApp:** na pasta `bridge/`: `npm install && npm run build && npm start` → escanear QR no telemóvel
3. **Gateway:** `zapassist gateway` (recebe/envia WhatsApp, roda cron e agente)
4. **CLI (sem WhatsApp):** `zapassist agent -m "Olá"` ou `zapassist agent` (interativo)

## Docker

Ver [TESTAR_COM_DOCKER.md](TESTAR_COM_DOCKER.md) ou [DEPLOY.md](DEPLOY.md) para build e subida com `docker-compose` (bridge + gateway + API).

## Documentação

- [PASSO_A_PASSO_TESTE.md](PASSO_A_PASSO_TESTE.md) — teste completo (config, bridge, gateway, WhatsApp)
- [DEBUG_WHATSAPP_DELIVERY.md](DEBUG_WHATSAPP_DELIVERY.md) — quando o lembrete não chega no WhatsApp
- [DEPLOY.md](DEPLOY.md) — deploy com Docker

## Licença

MIT.
