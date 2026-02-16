# Lógica temporal de contactos proativos

## 1. Lembrete inteligente diário (smart_reminder_daily)

**O que é:** Mensagem proativa enviada ao utilizador com sugestões baseadas em histórico (lembretes, eventos, listas). O texto é gerado por LLM (Mimo + DeepSeek); se o utilizador tiver poucos dados, o modelo pode sugerir coisas como "verifique a sincronização" ou "crie um evento de teste".

**Quando corre:** O **cron** dispara a cada **3 horas** (00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 **UTC**).  
Cada execução percorre todos os utilizadores com sessão; **só envia** a quem estiver na **janela local 8h–10h** (no fuso do utilizador) e **máx 1x por utilizador por dia** (controlo em `~/.zapista/smart_reminder_sent.json`).

**Resumo temporal:**
- **Frequência do job:** a cada 3 h (UTC).
- **Por utilizador:** no máximo **1 mensagem por dia**, e só quando a hora local dele for entre **8h e 10h**.

**Onde ajustar:**
- Janela horária (8h–10h): `backend/smart_reminder.py` → `_is_in_smart_reminder_window(tz_iana, hour_start=8, hour_end=10)`. Alterar `hour_start` / `hour_end` para mudar a janela.
- Frequência do cron: `zapista/cli/commands.py` → job "Lembrete inteligente diário" → `expr="0 0,3,6,9,12,15,18,21 * * *"`. Para 1x por dia à mesma hora UTC, usar por exemplo `expr="0 12 * * *"` (12:00 UTC todos os dias).
- Máx 1 por dia: lógica em `_load_sent_tracking()` / `_mark_sent_today()` no mesmo ficheiro; remover ou alterar se quiseres mais de 1 por dia.

---

## 2. Onboarding (quem não terminou cadastro)

**Não há follow-up proativo.** O robô **não** envia mensagens sozinho a quem não completou o onboarding.

- **Nudge ao responder:** Quando o utilizador **envia uma mensagem** e ainda não tem timezone, o robô pode **acrescentar** ao fim da resposta a frase de NUDGE_TZ_WHEN_MISSING (máx **1x por sessão**, flag `nudge_append_done`).
- **Reperguntar cidade:** Se já tiver enviado o intro e o utilizador ainda não tem timezone, após **2 “nudges”** (`onboarding_nudge_count >= 2`) o robô volta a perguntar a cidade na próxima mensagem do utilizador.

Ou seja: contacto só **quando o utilizador escreve**; nada de envio automático tipo “lembrete de completar onboarding”.

---

## 3. Resumo da semana / mês

Entregue **no primeiro contacto** do cliente após o período (a partir de abril/2026). Ver `backend/weekly_recap.py` e o bloco no agent loop; não é enviado em horário fixo por cron.

---

## Resumo rápido

| Tipo                    | Proativo? | Frequência (por user)     | Onde configurar                          |
|-------------------------|-----------|----------------------------|------------------------------------------|
| Lembrete inteligente    | Sim       | Máx 1x/dia, janela 8h–10h local | `smart_reminder.py`, cron em `commands.py` |
| Onboarding incompleto   | Não       | Só quando o user manda msg | Nudge no agent loop                      |
| Resumo semana/mês      | Não (só no 1.º contacto) | 1x por período           | `weekly_recap.py` + agent loop           |
