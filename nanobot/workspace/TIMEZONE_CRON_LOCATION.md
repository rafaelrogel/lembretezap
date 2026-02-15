# Onde localizar o código de timezone no Cron

Este ficheiro indica **os sítios exatos** onde verificar e, se necessário, alterar o código para que o **próximo run** e a **execução** dos jobs usem o timezone do utilizador (ideia MiniMax).

---

## 0. Localização real (VPS / repo)

| Ficheiro | Função |
|----------|--------|
| **`zapista/cron/service.py`** | `_compute_next_run(schedule, now_ms)` linhas 26–70: para `kind == "cron"` já usa `schedule.tz` com `ZoneInfo` + `croniter(expr, start_dt)`. Comparação em `_on_timer`: `now >= next_run_at_ms` (ambos em UTC). ✅ |
| **`zapista/cron/types.py`** | `CronSchedule` tem `tz: str \| None`. ✅ |
| **`zapista/agent/tools/cron.py`** | Para `cron_expr` obtém `tz_iana = get_user_timezone(db, self._chat_id)` e passa no `CronSchedule`. Se `tz_iana` for `None`, o service usa hora do servidor. **Ajuste:** fallback por idioma quando `tz_iana` é `None`. |

---

## 1. Onde o “próximo run” é calculado

Procurar por:

- **Nome de ficheiro típico:** `cron/service.py` ou `cron_service.py` (em `nanobot/`, `zapista/` ou `backend/`).
- **Função / método:** algo como `_compute_next_run`, `compute_next_run`, `get_next_run`, ou uso direto de `croniter(...).get_next(datetime)`.

**O que verificar:**

- Se o código usa `time.time()` ou `datetime.utcnow()` ou `datetime.now()` **sem** timezone como “agora” para passar ao croniter → **problema**: o “9h” será 9h no servidor.
- **Correção:** usar “agora” no timezone do utilizador, por exemplo:
  - `now = datetime.now(ZoneInfo(user_timezone))`
  - `cron = croniter(cron_expr, now)`
  - `next_run = cron.get_next(datetime)` (já no fuso do utilizador)
  - Guardar em UTC se for preciso: `next_run_utc = next_run.astimezone(ZoneInfo("UTC"))` e usar `.timestamp()` ou ms para persistência.

**Padrão correto** (já usado nos testes):  
`tests/test_timezone_stress.py` — por exemplo `test_cron_next_run_sao_paulo`, `test_timestamp_comparison_utc`: base em `datetime.now(ZoneInfo(tz))`, depois `next_run.astimezone(ZoneInfo("UTC")).timestamp()`.

---

## 2. Onde o job é criado (add_job / execute add)

Procurar por:

- **Handlers/tools:** ficheiros que chamam o “cron service” para adicionar lembrete (ex.: `handlers.py`, `reminder_flow.py`, ou um tool `cron.py` em `agent/tools/`).
- **Chamadas:** `add_job(...)`, ou `cron_tool.execute(action="add", ...)` ou equivalente.

**O que verificar:**

- Se ao criar o job é passado o **timezone do utilizador** (ex.: `user_timezone`, `tz_iana`) para quem calcula o próximo run.
- Se o modelo de job (em memória ou BD) tem um campo para guardar esse timezone (ex.: `user_timezone`, `tz_iana`) para uso no loop de execução.

---

## 3. Onde o loop de execução corre (run_pending / tick)

Procurar por:

- **Método / função:** `run_pending`, `tick`, `run_scheduler`, `check_pending_jobs`, ou um loop que percorre jobs e compara “agora” com a próxima execução.
- **Comparação típica:** `if now >= job.next_run` ou `if time.time() >= next_run_ts`.

**O que verificar:**

- Se `now` ou `next_run` estão no **mesmo referencial**:
  - **Opção A:** `next_run` guardado em UTC (timestamp ou datetime UTC) e comparação com `time.time()` ou `datetime.now(timezone.utc)` → correto.
  - **Opção B (estilo MiniMax):** `next_run` está no timezone do utilizador; então “agora” deve ser convertido para o timezone do utilizador antes de comparar: `now_user = now_utc.astimezone(ZoneInfo(job.user_timezone))` e `if now_user >= job.next_run`.

---

## 4. Modelo de dados do job

Procurar por:

- **Classe / tabela:** `CronJob`, `Job`, `Reminder`, ou tabela de jobs em `models.py` / `database/`.
- **Campo:** deve existir algo como `user_timezone`, `tz_iana` ou `timezone` por job (ou por user, e o job referencia o user).

Se não existir, acrescentar e preencher ao criar o job a partir do timezone do utilizador (BD → número → idioma).

---

## 5. Resumo por ficheiro (quando existirem no teu repo)

| Ficheiro (provável)              | O que fazer |
|---------------------------------|-------------|
| `*/cron/service.py` ou similar  | Localizar `_compute_next_run` (ou equivalente) e o loop que chama “run pending”; garantir base em `user_timezone` e comparação consistente (UTC ou no fuso do user). |
| `*/database/models.py`          | Garantir campo timezone no user e/ou no job. |
| `*/agent/tools/cron.py`         | Ao chamar o serviço para `add`, passar `tz_iana` / `user_timezone` obtido do user (ex.: `get_user_timezone(db, chat_id)`). |
| `*/handlers.py` / `reminder_flow.py` | Já usam `tz_iana` na criação (parse + compute in_seconds). Garantir que esse `tz_iana` chega ao cron service quando o job for agendado (one-shot ou recorrente). |

---

## 6. O que já está correto (não mexer)

- **Criação do lembrete (texto → data/hora):**  
  `parse_lembrete_time(text, tz_iana)` e `compute_in_seconds_from_date_hour(..., tz_iana)` com `now = datetime.now(ZoneInfo(tz_iana))` — já usam o fuso do utilizador.
- **Prioridade do timezone:**  
  BD → número → idioma (`get_user_timezone`, `get_user_timezone_and_source`) — manter como está.

Quando abrires a pasta que contiver o **cron service** e os **handlers/tools** que o chamam, podemos apontar linhas exatas e aplicar as alterações em cima deste mapa.

---

## 7. Encontrar o código no VPS (Linux)

Se a app corre num VPS Linux e não tens a certeza onde está o código do cron, entra no VPS por SSH e corre estes comandos a partir da **pasta da aplicação** (onde está o teu código, ex.: `/var/www/nanobot`, `~/nanobot`, ou onde fazes `git pull`).

**Assumindo que estás na raiz do projeto no VPS:**

```bash
# Diretório de trabalho (ajusta ao teu path)
cd /caminho/para/o/teu/projeto   # ex: cd ~/nanobot ou cd /opt/nanobot

# 1) Ficheiros que mencionam next_run, run_pending, add_job, croniter
grep -rln "next_run\|run_pending\|add_job\|croniter" --include="*.py" .

# 2) Ficheiros com "CronService" ou "cron_tool"
grep -rln "CronService\|cron_tool" --include="*.py" .

# 3) Onde o próximo run é calculado (time.time / get_next)
grep -rn "time\.time()\|get_next\|_compute_next" --include="*.py" .

# 4) Onde jobs são executados (run_pending, tick, pending)
grep -rn "run_pending\|\.tick\|pending.*job" --include="*.py" .

# 5) Listar estrutura de pastas (para ver se existe backend/, nanobot/, zapista/)
find . -name "*.py" -path "*cron*" 2>/dev/null
find . -name "service.py" 2>/dev/null
find . -name "cron.py" 2>/dev/null
```

**Resultado esperado:** vês caminhos do tipo `./backend/cron/service.py`, `./nanobot/agent/tools/cron.py`, etc. Copia esses caminhos e partilha (ou abre esse projeto no Cursor) para podermos apontar as linhas exatas.

**Se não souberes onde está o código no VPS:**

```bash
# Onde está o processo da tua app (ex.: python, uvicorn, gunicorn)
ps aux | grep -E "python|uvicorn|gunicorn" | grep -v grep

# A partir do resultado, vê o working directory do processo (ex.: /opt/nanobot)
# ou procura por ficheiros .py em pastas comuns
sudo find /opt /var/www /home -name "*.py" -exec grep -l "croniter\|next_run\|CronService" {} \; 2>/dev/null | head -20
```
