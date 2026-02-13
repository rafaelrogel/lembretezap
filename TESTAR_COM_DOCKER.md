# Instruções detalhadas: testar o zapista com Docker

Siga estes passos **na ordem**. Você já tem Docker instalado.

---

## Passo 1: Criar a pasta e o arquivo de configuração

O bot precisa de um `config.json` com sua chave de API (OpenRouter ou outro) e a configuração do WhatsApp.

### 1.1 Abrir PowerShell

Abra o **PowerShell** (Windows).

### 1.2 Criar a pasta `.zapista`

Execute:

```powershell
mkdir -Force $env:USERPROFILE\.zapista
```

### 1.3 Criar o arquivo `config.json`

Execute (abre o Bloco de Notas):

```powershell
notepad $env:USERPROFILE\.zapista\config.json
```

Se o Notepad perguntar “Deseja criar um novo arquivo?”, clique em **Sim**.

### 1.4 Colar este conteúdo no Notepad

Substitua **`SUA_CHAVE_OPENROUTER_AQUI`** pela sua chave real da OpenRouter (ou ajuste o provedor se usar outro).

- Para **permitir qualquer número** no WhatsApp: deixe `"allow_from": []`.
- Para **permitir só o seu número**: use `"allow_from": ["5511999999999"]` (código do país + número, sem + e sem espaços).

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.zapista/workspace",
      "model": "openrouter/anthropic/claude-sonnet-4",
      "max_tokens": 2048,
      "temperature": 0.7,
      "max_tool_iterations": 20
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

Salve o arquivo (Ctrl+S) e feche o Notepad.

---

## Passo 2: Ir para a pasta do projeto

No mesmo PowerShell:

```powershell
cd C:\Users\rafae\zapista
```

(Se o projeto estiver em outro disco ou pasta, use esse caminho.)

Confirme que existem os arquivos `docker-compose.yml` e `Dockerfile`:

```powershell
dir docker-compose.yml, Dockerfile
```

---

## Passo 3: Colocar o config no “volume” do Docker

Os containers usam um volume chamado `ZAPISTA_data` para guardar config e sessão do WhatsApp. É preciso copiar o seu `config.json` para dentro desse volume **antes** de subir os serviços.

### 3.1 Subir os containers uma vez (só para criar o volume)

```powershell
docker-compose up -d
```

Aguarde alguns segundos. Depois **pare** os containers (o volume já terá sido criado):

```powershell
docker-compose stop
```

### 3.2 Descobrir o nome exato do volume

```powershell
docker volume ls
```

Procure um volume cujo nome termina com `_ZAPISTA_data`, por exemplo: `ZAPISTA_ZAPISTA_data`.

### 3.3 Copiar o config para dentro do volume

Use o nome que você viu no passo anterior. No exemplo abaixo está `ZAPISTA_ZAPISTA_data`; **troque** se no seu `docker volume ls` aparecer outro nome.

```powershell
$vol = "ZAPISTA_ZAPISTA_data"
$cfg = "$env:USERPROFILE\.zapista\config.json"
docker run --rm -v "${vol}:/data" -v "${cfg}:/src/config.json:ro" alpine cp /src/config.json /data/config.json
```

Se der erro “volume não encontrado”, use o nome que apareceu em `docker volume ls` no lugar de `ZAPISTA_ZAPISTA_data`.

---

## Passo 4: Subir os containers de novo

```powershell
docker-compose up -d
```

Aguarde até os três serviços estarem “Up” (bridge, gateway, api). Para ver o status:

```powershell
docker-compose ps
```

Deve aparecer algo como:

- **bridge** – porta 3001  
- **gateway** – porta 18790  
- **api** – porta 8000  

---

## Passo 5: Ver o QR code do WhatsApp (primeira vez)

Na primeira execução o bridge ainda não tem sessão do WhatsApp. É preciso escanear o QR code.

### 5.1 Acompanhar os logs do bridge

```powershell
docker-compose logs -f bridge
```

Deixe esse comando rodando. No terminal vai aparecer um **QR code** em caracteres (e às vezes uma URL para abrir o QR em imagem).

### 5.2 Escanear o QR no telemóvel

1. Abra o **WhatsApp** no telemóvel.  
2. Toque em **Menu (⋮)** → **Aparelhos ligados** → **Ligar um aparelho**.  
3. Aponte a câmera para o QR code (ou use a URL, se aparecer).

Quando conectar, nos logs deve aparecer algo como **“Connected to WhatsApp”**.

### 5.3 Sair dos logs

Pressione **Ctrl+C** para parar de ver os logs. Os containers **continuam rodando**; você só deixou de acompanhar o terminal.

---

## Passo 6: Verificar se está tudo certo

### 6.1 Logs do gateway

```powershell
docker-compose logs gateway
```

Deve aparecer algo como:

- “WhatsApp channel enabled”  
- “Connected to WhatsApp bridge”  

Se não aparecer “Connected to WhatsApp bridge”, espere um pouco (o gateway tenta conectar ao bridge) e rode o comando de novo.

### 6.2 API (opcional)

No navegador ou no PowerShell:

```powershell
curl http://localhost:8000/health
```

Ou abra no navegador: **http://localhost:8000/health**  
A resposta deve indicar que a API está ok.

---

## Passo 7: Testar pelo WhatsApp

1. No telemóvel, envie uma mensagem para o **número/contato** que está ligado ao bridge (o “Zapista” no WhatsApp).  
2. Exemplos para testar:
   - **“Olá”** → o bot deve responder.
   - **“Me lembre em 2 minutos de tomar o remédio”** → ele confirma e, 2 minutos depois, envia o lembrete (se os containers continuarem ligados).
   - **“/list mercado add leite”** → cria a lista “mercado” e adiciona “leite”.
   - **“/list mercado”** → mostra a lista.

Se você configurou `allow_from` com um número específico, só esse número receberá resposta; mensagens de outros números serão ignoradas.

---

## Resumo da ordem

| # | O que fazer |
|---|------------------|
| 1 | Criar `%USERPROFILE%\.zapista\config.json` com chave de API e `allow_from` |
| 2 | `cd C:\Users\rafae\zapista` |
| 3 | `docker-compose up -d` → `docker-compose stop` (criar volume) |
| 4 | Copiar config para o volume (comando com `alpine cp`) |
| 5 | `docker-compose up -d` de novo |
| 6 | `docker-compose logs -f bridge` → escanear QR no WhatsApp → Ctrl+C |
| 7 | Verificar logs do gateway e testar mensagem no WhatsApp |

---

## Comandos úteis depois

- **Parar tudo:**  
  `docker-compose stop`

- **Subir de novo:**  
  `docker-compose up -d`

- **Ver logs do bridge:**  
  `docker-compose logs -f bridge`

- **Ver logs do gateway:**  
  `docker-compose logs -f gateway`

- **Reiniciar um serviço:**  
  `docker-compose restart gateway`  
  (ou `bridge`, ou `api`)

Se o WhatsApp der erro de sessão (por exemplo 401), pode ser preciso apagar a pasta de autenticação no volume, subir de novo e escanear o QR outra vez. Para isso e outros problemas de entrega, use o **DEBUG_WHATSAPP_DELIVERY.md**.
