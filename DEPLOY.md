# Deploy do zapista (Docker)

Guia para subir o organizador WhatsApp em servidor com Docker: **bridge** (WhatsApp), **gateway** (agente + cron) e **API** (opcional).

---

## Pré-requisitos

- Docker e Docker Compose instalados
- Config `config.json` com chave de API e, se quiser, `allow_from` (números/grupos permitidos)

---

## 1. Config antes do primeiro deploy

O gateway e a API usam o diretório de dados montado em `/root/.zapista` no container. Aí devem estar:

- **config.json** — obrigatório para o gateway (LLM, WhatsApp habilitado, etc.)
- **whatsapp-auth/** — criado pelo bridge ao escanear o QR (persistido no volume)

**Opção A – Usar o teu config local no volume**

Antes de subir, copia o config para o volume (substitui `ZAPISTA_ZAPISTA_data` pelo nome do teu volume se for diferente):

```powershell
# Windows (PowerShell)
docker volume create ZAPISTA_ZAPISTA_data
$cfg = "$env:USERPROFILE\.zapista\config.json"
if (Test-Path $cfg) {
  docker run --rm -v ZAPISTA_ZAPISTA_data:/data -v "${cfg}:/src/config.json:ro" alpine cp /src/config.json /data/config.json
}
```

```bash
# Linux / Mac
docker volume create ZAPISTA_ZAPISTA_data
[ -f ~/.zapista/config.json ] && docker run --rm -v ZAPISTA_ZAPISTA_data:/data -v ~/.zapista/config.json:/src/config.json:ro alpine cp /src/config.json /data/config.json
```

**Opção B – Montar o teu diretório .zapista (desenvolvimento)**

No `docker-compose.yml`, no serviço **gateway** e **api**, podes usar bind mount (ajusta o caminho):

```yaml
volumes:
  - /caminho/para/tua/pasta/.zapista:/root/.zapista
```

Assim o `config.json` e o resto dos dados ficam no teu disco.

**Opção C – API key via .env (opcional)**

Por defeito usamos **APIs diretas** (DeepSeek + Xiaomi MiMo), não OpenRouter. As chaves ficam no `.env`: copia `.env.example` para `.env`, define `ZAPISTA_PROVIDERS__DEEPSEEK__API_KEY` e `ZAPISTA_PROVIDERS__XIAOMI__API_KEY`. No VPS o script de instalação gera o `.env`; com docker-compose local, descomenta `env_file: .env` nos serviços **gateway** e **api**. O `.env` não deve ser commitado (já está no `.gitignore`).

---

### 1.1 Modelo e custos (DeepSeek + Xiaomi MiMo)

**Não precisas do Claude Sonnet.** Para os créditos durarem muito mais, usa **DeepSeek (agente)** e **Xiaomi MiMo-V2-Flash (scope + heartbeat)** com API direta de cada um.

**Exemplo: agente = DeepSeek, scope e heartbeat = Xiaomi**

No `config.json`:

```json
"agents": {
  "defaults": {
    "model": "deepseek/deepseek-chat",
    "scopeModel": "xiaomi_mimo/mimo-v2-flash"
  }
},
"providers": {
  "deepseek": { "api_key": "sua-chave-deepseek" },
  "xiaomi": { "api_key": "sua-chave-xiaomi-mimo" }
}
```

- **Agente (lembretes, listas, ferramentas):** usa `model` e a chave em `providers.deepseek.apiKey` (API direta DeepSeek).
- **Scope filter (SIM/NAO) e heartbeat:** usam `scopeModel` e a chave em `providers.xiaomi.apiKey` (API direta Xiaomi MiMo; o LiteLLM usa o prefixo `xiaomi_mimo/`).
- **Opção B (recomendada):** Colocar as chaves **só no `.env`** (nunca no repo). O loader aplica os overrides:
  - `ZAPISTA_PROVIDERS__DEEPSEEK__API_KEY=sk-...`
  - `ZAPISTA_PROVIDERS__XIAOMI__API_KEY=sk-...`
  No `config.json` podes deixar `providers.deepseek.api_key` e `providers.xiaomi.api_key` vazios (ou omitir); o `.env` prevalece.

Se omitires `scopeModel`, o scope e o heartbeat usam o mesmo `model` (e o mesmo provider) que o agente.

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
  Para endpoints de dados (`/users`, `/audit`, etc.): se definires `API_SECRET_KEY`, envia `X-API-Key: teu-api-key` em cada pedido.

- **Enviar uma mensagem** para o número/grupo ligado ao bridge; o bot deve responder (se o número/grupo estiver em `allow_from` ou se `allow_from` estiver vazio).

---

## 5. Config no Docker (bridge_url)

O gateway usa por defeito `ws://localhost:3001`. Em Docker, o bridge está noutro container, por isso o compose define:

```yaml
environment:
  - ZAPISTA_CHANNELS__WHATSAPP__BRIDGE_URL=ws://bridge:3001
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

## 7. Rotação de logs

O `docker-compose.yml` tem rotação de logs para todos os serviços:
- **max-size: 10m** — cada ficheiro de log até 10 MB
- **max-file: 3** — até 3 ficheiros por container (≈30 MB por serviço)

Os logs ficam em `/var/lib/docker/containers/`. Para logs em ficheiro dentro do volume (persistidos e rotacionados pelo Loguru), define no `.env`:

```
ZAPISTA_LOG_FILE=/root/.zapista/logs/app.log
```

O Loguru rota automaticamente (10 MB, 7 dias, compressão gzip).

---

## 8. Health check (segurança)

Por boa prática, os endpoints `/health` (bridge na porta 3001 e API na 8000) não devem ser expostos publicamente sem proteção. Duas opções:

1. **Token (recomendado)**  
   Define no `.env`: `HEALTH_CHECK_TOKEN=um-token-secreto`. O compose já passa este valor aos containers; o healthcheck do Docker usa-o automaticamente. Chamadas externas a `/health` sem o header `X-Health-Token` com o mesmo valor recebem **401**. Assim só orquestração (Docker, load balancer na rede interna) com o token consegue validar saúde.

2. **Rede isolada**  
   Em produção, não expor as portas 3001/8000 à internet; manter apenas na rede interna e deixar o healthcheck acessar por `localhost` dentro do container (como já acontece).

---

## 9. API: autenticação e CORS

- **API_SECRET_KEY:** Se definido no `.env` (ou nas variáveis do serviço **api**), todos os endpoints exceto `/health` exigem o header `X-API-Key` com o mesmo valor. Sem este header (ou com valor errado), a API responde 401/403. Em desenvolvimento podes deixar vazio para aceder sem autenticação.
- **CORS_ORIGINS:** Lista de origens permitidas para CORS, separadas por vírgula (ex.: `https://app.seudominio.com`). Valor por defeito `*` (todas). Em produção deve ser restrito ao domínio do teu frontend.

---

## 10. Backup automático (cron diário)

O script `scripts/backup_zapista.sh` faz backup de memória, sessões, BD e cron jobs.

**Executar manualmente:**
```bash
sudo bash scripts/backup_zapista.sh
```

**Agendar backup diário às 3h** (Linux):
```bash
# Copiar para /etc/cron.d/
sudo cp scripts/cron.zapista-backup /etc/cron.d/zapista-backup
sudo chmod 644 /etc/cron.d/zapista-backup
```

Variáveis (opcional, em `/etc/default/zapista-backup` ou no crontab):
- `ZAPISTA_INSTALL_DIR=/opt/zapista` — pasta do projeto
- `ZAPISTA_BACKUP_DIR=/backups/zapista` — pasta dos backups
- `RETENTION_DAYS=7` — dias a manter (default: 7)

---

## 11. Checklist de produção

Antes de expor ao público ou em VPS em produção, confirma:

| Item | Ação |
|------|------|
| **Redis 6379** | Não expor na internet. O `install_vps.sh` e `docker-compose.prod.yml` já desativam o mapeamento de portas. Para deploy manual: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` |
| **CORS_ORIGINS** | Em produção, definir domínios específicos no `.env`, ex.: `CORS_ORIGINS=https://app.seudominio.com`. `*` só para desenvolvimento. |
| **allow_from** | `[]` = qualquer número. Em produção para uso restrito, definir lista em `config.json`: `"allow_from": ["351912345678", "5511999999999"]` (país + número, sem + nem espaços). |
| **API_SECRET_KEY** | Sempre definir em produção. O `install_vps.sh` gera um por defeito. |
| **HEALTH_CHECK_TOKEN** | Recomendado para evitar expor `/health` sem proteção. |
| **Containers root** | Os serviços correm como root no container. Para hardening futuro, considerar migrar para USER não-root (exige alterar path de dados). |

---

## 12. Resumo rápido

1. Ter **config.json** no volume (ou montar `~/.zapista`).
2. `docker-compose up -d` (ou com `-f docker-compose.prod.yml` em produção).
3. `docker-compose logs -f bridge` → escanear QR
4. **Produção:** Definir `API_SECRET_KEY`, `CORS_ORIGINS`, `allow_from` e usar `docker-compose.prod.yml` para Redis.
5. (Opcional) Configurar backup: `sudo bash scripts/backup_zapista.sh` ou cron.
6. Testar mensagem no WhatsApp
