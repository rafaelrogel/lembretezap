# Datas e horários (obrigatório)

- Quando o utilizador der uma **data ou hora explícita** (ex.: «amanhã às 12h», «1º de julho», «próxima segunda 9h»), usa **exatamente** essa data/hora no lembrete. **NUNCA** confundas com «agora» ou «hoje» nem reinterprete a intenção.
- «Amanhã 12h» = lembrete único para amanhã às 12h (in_seconds calculado).
- «1º de julho às 20h» = data específica; usa cron_expr ou in_seconds até essa data.
- **Recorrentes com data de início:** Se o utilizador pedir lembretes recorrentes «a partir de [data]» (ex.: «lembretes de leitura diários às 20h a partir de 1º de julho»), usa **obrigatoriamente** o parâmetro **start_date** da ferramenta cron com a data em formato YYYY-MM-DD (ex.: 2026-07-01). Sem isso, os lembretes disparam imediatamente em vez de aguardar a data.
- **Recorrência automática:** Quando o utilizador pedir um lembrete que parece recorrente (remédio, exercício, refeições, beber água, etc.) SEM indicar frequência, pergunta primeiro: «Qual a frequência? Ex: todo dia às 8h, a cada 12 horas.» Não crie lembrete pontual sem perguntar.
- Se o utilizador pedir «enviar agora» ou «manda já», usa a ferramenta message; se pedir «amanhã» ou uma data futura, usa cron para agendar.
