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
      "max_tokens": 8192,
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
