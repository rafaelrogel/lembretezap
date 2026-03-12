# Plano de Features: Lembretes Avançados

## Implementado ✅

### 7. Reação = feito
- Bridge: evento `messages.reaction`, retorno de `message_id` no send
- Python: mapeamento `(chat_id, message_id) → job_id`, remoção do job ao reagir com 👍

### 8. Onboarding: emoji positivo/negativo
- Mensagem no fim do onboarding: "Nos lembretes: reage com 👍 (feito) ou 👎 (não feito, para reagendar)"
- Contexto do agente atualizado

### 9. Emoji negativo → reagendar
- Remove o job, envia "Queres alterar o horário? Diz o novo horário ou *não* para cancelar."
- A resposta do utilizador segue para o agente (cria novo lembrete normalmente)

---

## A implementar (2–6)

### 1. Lembrete com adiamento ✅
**"Lembra de novo em 10 min se eu não confirmar"**

- Implementado com `remind_again_if_unconfirmed_seconds` no payload.
- Fluxo: job dispara → envia mensagem → cria follow-up job em +X s. Reação 👍 cancela o follow-up. Sem reação, reenvia e cria novo follow-up (até 10x).

### 2. Lembrete encadeado ✅
**"Depois de terminar tarefa A, lembra de fazer B"**

- Implementado com `depends_on_job_id` no payload.
- Comando: `/lembrete B depois de PIX` ou `/lembrete B em 10 min depois de PIX`
- Interação: o agente usa `depends_on_job_id` na ferramenta cron.
- Fluxo: B fica desativado até A ser marcado 👍; então B dispara imediatamente.

### 3. Lembrete inteligente
**Sugerir tarefas pelo horário/local**

- **Horário:** usar hora actual + padrões (ex.: manhã → «beber água», tarde → «pausa»). Sugestões no agente ou job diário.
- **Localização:** exigir GPS/location do WhatsApp. Baileys pode receber `location`; adicionar handler e guardar última localização. Sugestões por proximidade exigem geofencing.
- **Escopo inicial:** só por horário (mais simples).

### 4. Soneca (snooze)
**Adiar lembrete com novo horário**

- **Opções:** reação ⏰ = "adiar 10 min" (ou botões quando houver WhatsApp Business API).
- **Fluxo:** reação ⏰ → remove job actual, cria novo job em +10 min (ou valor configurável).

### 5. Confirmar conclusão
**Pedir confirmação antes de considerar completo**

- Similar ao 1: job com `require_confirmation: true`. Primeira entrega diz "Reage com 👍 quando terminares." Não remove até haver reação (ou time-out para reenviar).

### 6. Lembrete com prazo
**"Se não fizer até X, alerta"**

- **Modelo:** job em X que verifica se houve conclusão. Se não, envia alerta ("Ainda não concluíste: ...") e opcionalmente escalada (ex.: novo prazo).
- **Fluxo:** job principal + job "deadline" em X. No deadline, verificar estado (ex.: reação no mapping). Se não feito, enviar alerta.

---

## Ordem sugerida

1. **Removed/Cancelled: Soneca (4)** – instrução removida para evitar frustração
2. **Lembrete com adiamento (1)** – base para 5 e 6
3. **Lembrete encadeado (2)** – usa o mesmo evento de "feito"
4. **Confirmar conclusão (5)** – variação de 1
5. **Lembrete com prazo (6)** – usa lógica de 1
6. **Lembrete inteligente (3)** – começar só por horário
