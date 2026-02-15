# Atualizar o VPS Zapista (sem reinstalar)

Guia **passo a passo** para atualizar o código no VPS a partir do repositório GitHub, **mantendo todos os dados e histórico** (base de dados, sessões WhatsApp, lembretes, logs da aplicação, config e .env).

Repositório: https://github.com/rafaelrogel/lembretezap

---

## ⚠️ Segurança — token GitHub

**Se partilhaste um Personal Access Token (PAT) do GitHub em algum sítio:**

1. **Revoga-o já** em: GitHub → Settings → Developer settings → Personal access tokens → revoga o token exposto.
2. Cria um **novo** token só com o scope necessário (ex.: `repo` se o repositório for privado).
3. **Nunca** coloques o token em scripts commitados nem em mensagens. Usa variável de ambiente ou Git credential helper no servidor.

Para o repositório **público** (lembretezap), o `update_vps.sh` **não precisa de token**: o clone já existente faz `git fetch`/`git pull` sem autenticação. Só precisas de token se o repositório for **privado** ou se o servidor tiver restrições de rede que exijam autenticação.

---

## O que fica preservado na atualização

O script `update_vps.sh` **só atualiza código** (git) e **reconstrói e reinicia os contentores**. Não apaga nem altera:

| O que | Onde no VPS | Preservado? |
|-------|------------------|-------------|
| Base de dados (utilizadores, listas, eventos, lembretes) | `INSTALL_DIR/data/organizer.db` | ✅ Sim |
| Sessão WhatsApp (QR já escaneado) | `INSTALL_DIR/data/whatsapp-auth/` | ✅ Sim |
| Sessões do agente (memória de conversas) | `INSTALL_DIR/data/sessions/` | ✅ Sim |
| Memória do agente (workspace) | `INSTALL_DIR/data/workspace/` | ✅ Sim |
| Jobs de cron (lembretes agendados) | `INSTALL_DIR/data/cron/` | ✅ Sim |
| Configuração (canal, modelos, etc.) | `INSTALL_DIR/data/config.json` | ✅ Sim |
| Chaves API e senha god-mode | `INSTALL_DIR/.env` | ✅ Sim |
| Logs da aplicação (Loguru) | `INSTALL_DIR/data/logs/` (se `ZAPISTA_LOG_FILE` estiver definido no .env) | ✅ Sim |
| Piper TTS (vozes e binário) | `INSTALL_DIR/data/bin/`, `INSTALL_DIR/data/models/piper/` | ✅ Sim |

Os **logs do Docker** (saída de `docker compose logs`) são por contentor. Após o update, os contentores são novos, por isso os “logs antigos” deixam de aparecer no `docker compose logs`. Se quiseres guardar um cópia dos logs antes do update, usa o passo opcional de backup de logs abaixo.

---

## Pré-requisitos

- Acesso SSH ao teu VPS (utilizador com sudo).
- Pasta de instalação já existente (ex.: `/opt/zapista` ou a que usaste no `install_vps.sh`).
- Código na pasta ter sido clonado do GitHub (ter `.git`).

---

## Passo 1 — Ligar ao VPS por SSH

No teu computador (PowerShell, CMD ou terminal):

```bash
ssh utilizador@IP_DO_TEU_VPS
```

Substitui `utilizador` (ex.: `root` ou `ubuntu`) e `IP_DO_TEU_VPS` pelo teu utilizador e IP/hostname.

Se usas chave SSH:

```bash
ssh -i C:\caminho\para\chiave_privada utilizador@IP_DO_TEU_VPS
```

---

## Passo 2 — Confirmar a pasta de instalação

A atualização usa a mesma pasta onde o Zapista foi instalado (normalmente `/opt/zapista`). O script deteta-a sozinho; podes confirmar:

```bash
# Ver se existe e tem o ficheiro típico do VPS
ls -la /opt/zapista/docker-compose.vps.yml
ls -la /opt/zapista/.git
```

Se instalaste noutro sítio (ex.: `/root/zapista`), anota o caminho. Vais usá-lo no Passo 5 com `ZAPISTA_INSTALL_DIR`.

---

## Passo 3 (opcional) — Backup antes de atualizar

Recomendado na primeira vez que fazes update, para teres segurança extra.

### 3.1 Backup dos dados (organizer.db, sessões, etc.)

Na pasta do projeto existe o script de backup:

```bash
sudo ZAPISTA_INSTALL_DIR=/opt/zapista bash /opt/zapista/scripts/backup_zapista.sh
```

(Se a instalação for noutra pasta, troca `/opt/zapista` pelo teu caminho.)

Os backups ficam em `/backups/zapista/` (ficheiros `zapista-YYYYMMDD-HHMM.tar.gz`).

### 3.2 (Opcional) Guardar uma cópia dos logs do Docker

Se quiseres conservar os logs da versão antiga antes de reiniciar os contentores:

```bash
cd /opt/zapista
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml logs --no-color > /root/zapista-logs-antes-update-$(date +%Y%m%d-%H%M).txt
```

O ficheiro fica em `/root/`. Podes mudar o caminho se quiseres.

---

## Passo 4 — Garantir que o Git está a apontar ao GitHub

O script de update usa `origin` e o branch `main`. Confirma:

```bash
cd /opt/zapista
git remote -v
```

Deves ver algo como:

```
origin  https://github.com/rafaelrogel/lembretezap.git (fetch)
origin  https://github.com/rafaelrogel/lembretezap.git (push)
```

Se o repositório for **público**, não precisas de configurar token. Se for **privado** e der erro de autenticação no Passo 6, usa o Passo 4.1.

### 4.1 (Só se o repositório for privado) — Configurar acesso Git com token

**Não coloques o token em ficheiros commitados.** Usa um dos métodos abaixo.

**Opção A — URL com token (só para este remote, em memória):**

```bash
cd /opt/zapista
# Substitui TEU_TOKEN pelo teu PAT (com permissão repo)
git remote set-url origin https://TEU_TOKEN@github.com/rafaelrogel/lembretezap.git
```

Depois do update, se quiseres remover o token da URL (recomendado):

```bash
git remote set-url origin https://github.com/rafaelrogel/lembretezap.git
```

**Opção B — Credential helper (guardado no servidor):**

```bash
git config --global credential.helper store
git fetch origin
# Quando pedir, utilizador: o teu username GitHub; password: o teu PAT
```

---

## Passo 5 — Executar o script de atualização

Sempre com a pasta correta. Se instalaste em `/opt/zapista`:

```bash
sudo bash /opt/zapista/scripts/update_vps.sh
```

Se instalaste noutra pasta (ex.: `/root/zapista`):

```bash
sudo ZAPISTA_INSTALL_DIR=/root/zapista bash /root/zapista/scripts/update_vps.sh
```

O script vai:

1. **[1/3]** Entrar na pasta, fazer `git fetch origin`, `git reset --hard origin/main` e `git pull --ff-only origin main` — código atualizado ao último commit do GitHub.
2. **[2/3]** `docker compose build --no-cache` e `docker compose up -d` — imagens reconstruídas e serviços a correr.
3. **[3/3]** Mensagem de conclusão.

Se aparecer algum erro, o script para. Anota a mensagem e verifica (por exemplo: rede, falha no build Docker, falta de espaço em disco).

---

## Passo 6 — Verificar após o update

### 6.1 Serviços a correr

```bash
cd /opt/zapista
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml ps
```

Todos os serviços (redis, bridge, api, stt, gateway) devem estar `Up`.

### 6.2 Logs em tempo real (bridge = WhatsApp)

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f bridge
```

Deves ver que o bridge está ligado. Sai com `Ctrl+C`.

### 6.3 Gateway (agente e cron)

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f gateway
```

Confirma que não há erros de arranque. Sai com `Ctrl+C`.

### 6.4 Testar no WhatsApp

Envia uma mensagem ao número ligado ao Zapista. O bot deve responder; os dados antigos (listas, lembretes) continuam disponíveis.

---

## Resumo rápido (comando único, após SSH)

Se a instalação está em `/opt/zapista` e não precisas de backup nem de token:

```bash
sudo bash /opt/zapista/scripts/update_vps.sh
```

---

## Problemas comuns

### "Erro: pasta de instalação não encontrada"

- O script procura em `/opt`, `/root`, `/home` por `docker-compose.vps.yml` ou pela estrutura zapista.
- Solução: indica a pasta manualmente:  
  `sudo ZAPISTA_INSTALL_DIR=/caminho/para/zapista bash /caminho/para/zapista/scripts/update_vps.sh`

### "Não é um repositório git"

- A pasta foi criada sem `git clone` (ex.: cópia manual).
- Solução: usa o instalador completo `install_vps.sh` (e restaura dados de um backup se tiveres).

### Falha no `git fetch` / `git pull` (privado ou 403)

- Repo privado ou rede com restrição: configura o token (Passo 4.1). Nunca commites o token.

### Falha no build Docker

- Falta de espaço: `df -h` e libertar espaço.
- Erro de rede ao baixar imagens: verifica conectividade no VPS.
- Ver o erro exato nas linhas que o script mostrar antes de parar.

### WhatsApp desligado após o update

- O bridge guarda a sessão em `data/whatsapp-auth/`. Se os contentores subiram e o volume é o mesmo, normalmente reconecta sozinho.
- Se aparecer 401 ou pedido de QR de novo: ver `DEBUG_WHATSAPP_DELIVERY.md` no repositório.

---

## Referências

- Repositório: https://github.com/rafaelrogel/lembretezap  
- Deploy geral: `DEPLOY.md`  
- Segurança: `SECURITY.md`
