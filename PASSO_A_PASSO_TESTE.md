# Passo a passo para testar o nanobot (até o que temos agora)

Este guia cobre: config, bridge WhatsApp, gateway, agente (lembretes, listas, eventos) e entrega de mensagens no WhatsApp.

---

## Pré-requisitos

- **Python 3.11+** (no Windows: `py -3.11` ou `py -3.14`)
- **Node.js** (para o bridge WhatsApp)
- **Chave de API** de um provedor LLM (OpenRouter, OpenAI, etc.)

---

## 1. Configuração (`config.json`)

O arquivo fica em **`%USERPROFILE%\.nanobot\config.json`** (Windows) ou **`~/.nanobot/config.json`** (Linux/Mac).

### Exemplo completo (com seu número permitido)

Para **permitir apenas** o número **+351 910 070 509**, use `allow_from` com o número **sem + e sem espaços**: `351910070509`. O canal WhatsApp envia o `sender_id` já como número (parte antes do `@` do JID).

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
      "model": "openrouter/anthropic/claude-sonnet-4",
      "max_tokens": 8192,
      "temperature": 0.7,
      "max_tool_iterations": 20
    }
  },
  "channels": {
    "whatsapp": {
      "enabled": true,
      "bridge_url": "ws://localhost:3001",
      "allow_from": ["351910070509"]
    }
  },
  "providers": {
    "openrouter": {
      "api_key": "SUA_CHAVE_OPENROUTER_AQUI",
      "api_base": null,
      "extra_headers": null
    }
  },
  "gateway": {
    "host": "0.0.0.0",
    "port": 18790
  }
}
```

### Regras do `allow_from`

- **`allow_from`: []** (lista vazia) → **qualquer número** pode usar o bot.
- **`allow_from`: ["351910070509"]** → só esse número (formato: país + número sem + nem espaços).
- Para mais números: `"allow_from": ["351910070509", "5511999999999"]`.

Substitua `SUA_CHAVE_OPENROUTER_AQUI` pela sua chave real. Não compartilhe a chave em repositórios.

---

## 2. Criar a pasta e o config

No PowerShell (Windows):

```powershell
mkdir -Force $env:USERPROFILE\.nanobot
notepad $env:USERPROFILE\.nanobot\config.json
```

Cole o JSON acima, ajuste a chave e o `allow_from` se quiser, e salve.

---

## 3. Ambiente Python (nanobot)

Na pasta do projeto (onde está `pyproject.toml`):

```powershell
cd C:\Users\rafae\nanobot
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

(Se usar outro Python, troque `py -3.11` por `py -3.14` etc.)

---

## 4. Bridge WhatsApp (Node)

Em outro terminal:

```powershell
cd C:\Users\rafae\nanobot\bridge
npm install
npm run build
npm start
```

- Deixe este terminal aberto.
- Quando aparecer o **QR code**, abra o WhatsApp no telemóvel: **Menu (⋮) → Aparelhos ligados → Ligar um aparelho** e escaneie o QR.
- Depois de ligado, deve aparecer algo como **"Connected to WhatsApp"**.

A autenticação fica guardada em `%USERPROFILE%\.nanobot\whatsapp-auth` (ou em `AUTH_DIR` se tiver definido).

---

## 5. Gateway (Python) – receber e enviar pelo WhatsApp

Em **outro** terminal (com o venv ativado):

```powershell
cd C:\Users\rafae\nanobot
.\.venv\Scripts\Activate.ps1
nanobot gateway
```

- Deve aparecer algo como: **Channels enabled: whatsapp**, **WhatsApp channel enabled**, **Connected to WhatsApp bridge**.
- Este processo é quem:
  - Recebe mensagens do bridge e manda para o agente.
  - Roda o **cron** (lembretes); por isso o lembrete só é entregue no WhatsApp se o gateway estiver a correr na hora do disparo.

---

## 6. Testar pelo WhatsApp

Com o bridge e o gateway a correr e o número no `allow_from` (ou `allow_from` vazio):

1. Envie uma mensagem para o número/contato que está ligado ao bridge (o “nanobot” no WhatsApp).
2. Exemplos:
   - **"Olá"** → resposta do agente (organizador).
   - **"Me lembre em 2 minutos de tomar o remédio"** → deve confirmar e, 2 minutos depois, enviar o lembrete no mesmo chat (se o gateway continuar ligado).
   - **"/list mercado add leite"** → cria lista “mercado” e adiciona “leite”.
   - **"/list mercado"** → mostra a lista.
   - **"/filme Dune"** → adiciona evento tipo filme.

Se tiver **allow_from** com só o teu número e enviares de outro número, o bot ignora (e no log do gateway pode aparecer “Access denied for sender ...”).

---

## 7. Testar agente pelo CLI (sem WhatsApp)

Noutro terminal (venv ativo):

```powershell
cd C:\Users\rafae\nanobot
nanobot agent -m "Que horas são?"
```

Ou modo interativo:

```powershell
nanobot agent
```

Nota: lembretes criados aqui (`nanobot agent -m "me lembre em 2 min"`) ficam com canal `cli` e **não são entregues no WhatsApp**. Para receber no telemóvel, crie o lembrete **pelo WhatsApp** (passo 6).

---

## 8. API do backend (listas/eventos/auditoria)

Opcional. Noutro terminal:

```powershell
cd C:\Users\rafae\nanobot
.\.venv\Scripts\Activate.ps1
uvicorn backend.app:app --reload --port 8000
```

- Health: **http://localhost:8000/health**
- Users: **http://localhost:8000/users**
- (Requer uso prévio pelo WhatsApp para existirem utilizadores no DB.)

---

## 9. Resumo da ordem recomendada para “testar tudo”

1. Criar **config.json** em `~/.nanobot/` com `allow_from: ["351910070509"]` (ou vazio para permitir todos).
2. **Bridge:** `cd bridge` → `npm run build` → `npm start` → escanear QR.
3. **Gateway:** `nanobot gateway` (deixar a correr).
4. Enviar mensagens e um lembrete **pelo WhatsApp** e esperar 1–2 minutos para ver a entrega.
5. (Opcional) **API:** `uvicorn backend.app:app --port 8000` e abrir `/health` e `/users`.

---

## 10. Se o lembrete não chegar no WhatsApp

Use o **DEBUG_WHATSAPP_DELIVERY.md**: checklist (lembrete criado pelo WhatsApp? gateway a correr? bridge conectada?) e significado dos logs (`Cron deliver`, `Dispatch outbound`, `WhatsApp send`, `Unknown channel: cli`).

---

## Config: só o bloco WhatsApp com o teu número

Se já tens o resto do config e só queres alterar o WhatsApp e o número permitido:

```json
"channels": {
  "whatsapp": {
    "enabled": true,
    "bridge_url": "ws://localhost:3001",
    "allow_from": ["351910070509"]
  }
}
```

- **Permitir todos:** `"allow_from": []`
- **Só o teu:** `"allow_from": ["351910070509"]`
