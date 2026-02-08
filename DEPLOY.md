# Deploy do nanobot (Docker)

Guia para subir o organizador WhatsApp em servidor com Docker: **bridge** (WhatsApp), **gateway** (agente + cron) e **API** (opcional).

---

## Pré-requisitos

- Docker e Docker Compose instalados
- Config `config.json` com chave de API e, se quiser, `allow_from` (números/grupos permitidos)

---

## 1. Config antes do primeiro deploy

O gateway e a API usam o diretório de dados montado em `/root/.nanobot` no container. Aí devem estar:

- **config.json** — obrigatório para o gateway (LLM, WhatsApp habilitado, etc.)
- **whatsapp-auth/** — criado pelo bridge ao escanear o QR (persistido no volume)

**Opção A – Usar o teu config local no volume**

Antes de subir, copia o config para o volume (substitui `nanobot_nanobot_data` pelo nome do teu volume se for diferente):

```powershell
# Windows (PowerShell)
docker volume create nanobot_nanobot_data
$cfg = "$env:USERPROFILE\.nanobot\config.json"
if (Test-Path $cfg) {
  docker run --rm -v nanobot_nanobot_data:/data -v "${cfg}:/src/config.json:ro" alpine cp /src/config.json /data/config.json
}
```

```bash
# Linux / Mac
docker volume create nanobot_nanobot_data
[ -f ~/.nanobot/config.json ] && docker run --rm -v nanobot_nanobot_data:/data -v ~/.nanobot/config.json:/src/config.json:ro alpine cp /src/config.json /data/config.json
```

**Opção B – Montar o teu diretório .nanobot (desenvolvimento)**

No `docker-compose.yml`, no serviço **gateway** e **api**, podes usar bind mount (ajusta o caminho):

```yaml
volumes:
  - /caminho/para/tua/pasta/.nanobot:/root/.nanobot
```

Assim o `config.json` e o resto dos dados ficam no teu disco.

**Opção C – API key via .env (opcional)**

Para não deixar a chave só no config do volume, podes usar ficheiro `.env`: copia `.env.example` para `.env`, define `NANOBOT_PROVIDERS__OPENROUTER__API_KEY=...` (ou outro provider), e no `docker-compose.yml` descomenta `env_file: .env` nos serviços **gateway** e **api**. O `.env` não deve ser commitado (já está no `.gitignore`).

---

## 2. Build e subir

Na pasta do projeto:

```bash
cd ..
docker-compose up -d
```

Serviços:

| Serviço   | Porta | Função                          |
|-----------|--------|----------------------------------|
| **bridge**  | 3001  | WhatsApp (Baileys), gera QR      |
| **gateway** | 18790 | Agente, cron, envia/recebe mensagens |
| **api**     | 8000  | FastAPI (listas, eventos, health) |

---

## 3. Ligar o WhatsApp (QR code)

Na primeira execução o bridge não tem sessão; é preciso escanear o QR:

```bash
docker-compose logs -f bridge
```

Quando aparecer o **QR code** no log:

1. Abre o WhatsApp no telemóvel
2. Menu (⋮) → **Aparelhos ligados** → **Ligar um aparelho**
3. Escaneia o QR

Ao conectar, deve aparecer algo como “Connected to WhatsApp”. Podes sair dos logs com **Ctrl+C**; os containers continuam a correr.

O estado da sessão fica em `whatsapp-auth/` dentro do volume, por isso não precisas de escanear de novo ao reiniciar (a menos que saias da sessão no telemóvel ou dê 401).

---

## 4. Verificar

- **Gateway:**  
  `docker-compose logs gateway`  
  Deve mostrar “WhatsApp channel enabled” e “Connected to WhatsApp bridge” (após o QR).

- **API:**  
  `curl http://localhost:8000/health`  
  (Se usares `HEALTH_CHECK_TOKEN`, passa o header: `curl -H "X-Health-Token: teu-token" http://localhost:8000/health`.)

- **Enviar uma mensagem** para o número/grupo ligado ao bridge; o bot deve responder (se o número/grupo estiver em `allow_from` ou se `allow_from` estiver vazio).

---

## 5. Config no Docker (bridge_url)

O gateway usa por defeito `ws://localhost:3001`. Em Docker, o bridge está noutro container, por isso o compose define:

```yaml
environment:
  - NANOBOT_CHANNELS__WHATSAPP__BRIDGE_URL=ws://bridge:3001
```

Não precisas de alterar o `config.json` para a URL do bridge em deploy com este compose.

---

## 6. Reiniciar / parar

```bash
docker-compose restart    # reiniciar todos
docker-compose stop       # parar
docker-compose up -d      # voltar a subir
```

Se o WhatsApp der **401** (sessão inválida), apaga a pasta de auth no volume, sobe de novo e escaneia o QR outra vez (ver DEBUG_WHATSAPP_DELIVERY.md).

---

## 7. Health check (segurança)

Por boa prática, os endpoints `/health` (bridge na porta 3001 e API na 8000) não devem ser expostos publicamente sem proteção. Duas opções:

1. **Token (recomendado)**  
   Define no `.env`: `HEALTH_CHECK_TOKEN=um-token-secreto`. O compose já passa este valor aos containers; o healthcheck do Docker usa-o automaticamente. Chamadas externas a `/health` sem o header `X-Health-Token` com o mesmo valor recebem **401**. Assim só orquestração (Docker, load balancer na rede interna) com o token consegue validar saúde.

2. **Rede isolada**  
   Em produção, não expor as portas 3001/8000 à internet; manter apenas na rede interna e deixar o healthcheck acessar por `localhost` dentro do container (como já acontece).

---

## 8. Resumo rápido

1. Ter **config.json** no volume (ou montar `~/.nanobot`).
2. `docker-compose up -d`
3. `docker-compose logs -f bridge` → escanear QR
4. Testar mensagem no WhatsApp
