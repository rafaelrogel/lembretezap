# Instalação do ZapAssist num VPS Linux (passo a passo)

Guia para instalar o **ZapAssist** (organizador por WhatsApp) num VPS com **Linux**, por exemplo **4 GB RAM** e **40 GB disco**, para testes reais com **4 a 5 pessoas**.

---

## Aviso sobre a chave da API

- **Nunca partilhes a tua chave OpenRouter** em sítios públicos (chat, email, repositório).
- Se já a colaste em algum sítio visível, **gera uma nova** em [OpenRouter](https://openrouter.ai/keys) e usa a nova no servidor.
- O script e este guia **não incluem** a tua chave; vais introduzi-la só no servidor quando o script pedir (ou por variável de ambiente).

---

## O que vais precisar

1. **VPS** com Linux (Ubuntu 22.04 ou 24.04, ou Debian 11/12).
2. **Acesso SSH** ao VPS (utilizador com permissão para usar `sudo`).
3. **Chave OpenRouter** (formato `sk-or-v1-...`).
4. **Telemóvel** com WhatsApp para escanear o QR na primeira vez.

---

## Opção A: Instalação automática (recomendada)

Um único script faz a instalação: Docker, código, configuração e arranque dos contentores.

### Passo 1 — Ligar ao VPS por SSH

No teu computador, abre um terminal e liga ao VPS (substitui `utilizador` e `IP_DO_TEU_VPS`):

```bash
ssh utilizador@IP_DO_TEU_VPS
```

Exemplo: `ssh root@192.168.1.100` ou `ssh ubuntu@meuservidor.pt`

### Passo 2 — Descarregar o script de instalação

Ainda no SSH do VPS, corre:

```bash
sudo apt-get update
sudo apt-get install -y curl
curl -sSL -o /tmp/install_vps.sh https://raw.githubusercontent.com/rafaelrogel/lembretezap/main/scripts/install_vps.sh
```

Se o repositório for outro, substitui o URL pelo teu (e garante que o ficheiro `scripts/install_vps.sh` existe nesse repositório).

### Passo 3 — Executar o script

```bash
sudo bash /tmp/install_vps.sh
```

Quando o script pedir **"Chave OpenRouter"**, cola a tua chave (ex.: `sk-or-v1-...`) e carrega em Enter. A chave não aparece enquanto escreves (por segurança).

**Alternativa:** passar a chave por variável de ambiente (evita colar no terminal):

```bash
sudo OPENROUTER_API_KEY="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" bash /tmp/install_vps.sh
```

(Substitui pelo teu valor real; em produção prefere pedir a chave no script e não deixá-la na linha de comandos.)

### Passo 4 — Esperar o fim da instalação

O script vai:

- Atualizar o sistema e instalar dependências
- Instalar Docker e Docker Compose (se não existirem)
- Clonar o repositório do ZapAssist para `/opt/zapassist`
- Criar a configuração com a tua chave OpenRouter
- Construir as imagens Docker e arrancar os serviços

No final aparece uma mensagem a dizer que a instalação terminou.

### Passo 5 — Ligar o WhatsApp (QR code)

É **obrigatório** fazer isto na primeira vez:

```bash
cd /opt/zapassist
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f bridge
```

Quando aparecer o **QR code** no terminal:

1. Abre o **WhatsApp** no telemóvel.
2. Menu (⋮) → **Aparelhos ligados** → **Ligar um aparelho**.
3. Escaneia o QR que está no ecrã do VPS.

Quando aparecer algo como **"Connected to WhatsApp"**, podes sair dos logs com **Ctrl+C**. Os contentores continuam a correr.

### Passo 6 — Testar

Envia uma mensagem para o número de WhatsApp que está ligado ao bridge (o mesmo que escaneou o QR). Por exemplo:

- *"Lembra-me de beber água daqui a 2 minutos"*
- *"/list mercado add leite"*

O bot deve responder. Se não responder, vê a secção **Problemas comuns** mais abaixo.

---

## Opção B: Instalação manual (passo a passo)

Se preferires fazer tudo à mão, sem usar o script:

### Etapa 1 — Atualizar o sistema

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### Etapa 2 — Instalar Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable docker
sudo systemctl start docker
```

Verificar: `sudo docker run hello-world` (deve mostrar uma mensagem e sair).

### Etapa 3 — Instalar Docker Compose

```bash
sudo apt-get install -y docker-compose-plugin
```

Verificar: `sudo docker compose version`.

### Etapa 4 — Clonar o repositório

```bash
sudo mkdir -p /opt
sudo git clone https://github.com/rafaelrogel/lembretezap.git /opt/zapassist
cd /opt/zapassist
```

(Substitui o URL pelo teu repositório se for diferente.)

### Etapa 5 — Criar a pasta de dados e o config.json

```bash
sudo mkdir -p /opt/zapassist/data/whatsapp-auth
sudo nano /opt/zapassist/data/config.json
```

Cola o seguinte (e **substitui** `SUA_CHAVE_OPENROUTER` pela tua chave real):

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
      "model": "openrouter/anthropic/claude-sonnet-4",
      "max_tokens": 8192,
      "temperature": 0.7
    }
  },
  "channels": {
    "whatsapp": {
      "enabled": true,
      "bridge_url": "ws://bridge:3001",
      "allow_from": []
    }
  },
  "providers": {
    "openrouter": {
      "api_key": "SUA_CHAVE_OPENROUTER"
    }
  }
}
```

Guarda com **Ctrl+O**, Enter, e sai com **Ctrl+X**.

```bash
sudo chmod 600 /opt/zapassist/data/config.json
```

### Etapa 6 — Ficheiro override para o VPS (dados em pasta local)

```bash
sudo nano /opt/zapassist/docker-compose.vps.yml
```

Conteúdo (o caminho deve ser exatamente `/opt/zapassist/data`):

```yaml
volumes:
  nanobot_data:
    driver: local
    driver_opts:
      type: none
      device: /opt/zapassist/data
      o: bind
```

Guarda e sai.

### Etapa 7 — Arrancar os serviços

```bash
cd /opt/zapassist
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml build
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d
```

### Etapa 8 — Ver o QR do WhatsApp

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f bridge
```

Escaneia o QR no telemóvel como na Opção A, passo 5. Sair com **Ctrl+C** quando estiver ligado.

---

## Comandos úteis depois de instalar

| O que queres fazer | Comando |
|--------------------|--------|
| Ver logs do bridge (QR / erros) | `cd /opt/zapassist && sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f bridge` |
| Ver logs do gateway | `sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f gateway` |
| Parar tudo | `sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml stop` |
| Arrancar de novo | `sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d` |
| Reiniciar um serviço | `sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml restart bridge` |

---

## Portas e segurança

- **3001** — Bridge (WhatsApp). Evita abrir à internet; usa só na rede interna ou com firewall.
- **8000** — API (listas, eventos). Se abrires ao exterior, usa firewall e, em produção, `API_SECRET_KEY` e `CORS_ORIGINS` no `.env`.
- **18790** — Gateway (agente). Normalmente só localhost/rede interna.

Para **4–5 pessoas em testes**, podes deixar o firewall a bloquear tudo e aceder só por SSH; ou abrir só a porta que precisares (por exemplo 8000) com restrições de IP.

---

## Problemas comuns

**O QR não aparece**  
- Espera 30–60 segundos após `docker compose up -d`.  
- Confirma que o serviço está a correr: `sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml ps`  
- Volta a ver os logs: `logs -f bridge`.

**"Connected" mas o bot não responde**  
- Confirma que estás a enviar do **mesmo número** que escaneou o QR (chats privados; grupos são ignorados).  
- Vê os logs do gateway: `sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f gateway` e verifica erros de API/chave.

**Sessão WhatsApp desligada (401)**  
- No VPS: `sudo rm -rf /opt/zapassist/data/whatsapp-auth/*`  
- Reinicia o bridge: `sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml restart bridge`  
- Volta a correr `logs -f bridge` e escaneia um novo QR.

**Limitar a números específicos**  
- Edita `/opt/zapassist/data/config.json` e em `channels.whatsapp` define por exemplo:  
  `"allow_from": ["351912345678", "351987654321"]`  
  (número com código do país, sem + nem espaços).  
- Reinicia o gateway: `sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml restart gateway`

---

## Resumo rápido (com script)

1. SSH ao VPS: `ssh utilizador@IP`
2. Descarregar script: `curl -sSL -o /tmp/install_vps.sh https://raw.githubusercontent.com/rafaelrogel/lembretezap/main/scripts/install_vps.sh`
3. Executar: `sudo bash /tmp/install_vps.sh` e colar a chave OpenRouter quando pedido
4. Ver QR: `cd /opt/zapassist && sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f bridge`
5. Escanear QR no WhatsApp (Aparelhos ligados → Ligar um aparelho)
6. Testar a enviar uma mensagem ao bot

Se seguires estes passos, tens o ZapAssist a correr no VPS para testes com 4–5 pessoas.
