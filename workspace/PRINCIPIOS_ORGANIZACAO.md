# Princípios da organização do cliente

A base do produto se baseia em **três pilares**: agenda (eventos), lembretes e listas. O agente e os fluxos devem respeitar estas regras.

---

## 1. Agenda (evento)

- **Agenda** = compromissos/eventos do cliente com **data** (e normalmente **hora**).
- Exemplo: *"Amanhã tenho de ir ao médico"* → é um **item da agenda** (um evento): o cliente disse o evento e o dia.
- **A agenda não dispara mensagens de lembrete por si.** Ela apenas registra o que o cliente tem marcado (consultas, reuniões, etc.).
- Quando o cliente indica um evento e o dia, deve-se:
  1. **Registrar na agenda** (evento com data).
  2. Como eventos costumam ter horário, **perguntar a que horas**.
  3. Quando o cliente disser a hora, **registrar o horário na agenda**.

---

## 2. Lembretes

- **Lembrete** = mensagem que **dispara** num momento (uma vez ou recorrente) para avisar o cliente.
- Um lembrete **pode** estar ligado a um evento da agenda (ex.: lembrete "ir ao médico" a disparar no horário da consulta).
- Um lembrete **não precisa** de ser um item da agenda.

**Exemplos de coisas que são apenas lembrete (não agenda/evento):** tomar remédio, beber água, desligar o fogão, ir buscar o celular, comprar feijão. Não se registra na agenda — só se cria o aviso que dispara na hora.

**Distinção importante:**

- **Todo item de agenda pode também ser um lembrete** (o cliente pode querer ser avisado na hora ou antes).
- **Um lembrete não precisa de ser um item de agenda.**

**Fluxo quando o cliente registra um evento na agenda:**

1. Cliente diz evento + dia (ex.: "amanhã tenho de ir ao médico") → registrar na **agenda**.
2. Perguntar **a que horas**.
3. Cliente diz a hora → registrar o horário na **agenda**.
4. Perguntar se o cliente **quer também um lembrete** para esse evento.
5. Se **sim**:
   - Perguntar **com quanto tempo de antecedência** (ou apenas na hora).
   - Ex.: se disser "15 minutos antes", disparar **duas mensagens**: uma 15 min antes e outra na hora indicada.
6. Se **não**, fica só na agenda (sem disparar mensagens).

Resumo: **agenda não dispara mensagens**; só dispara se o cliente indicar ou confirmar que quer lembrete. O agente deve perguntar e só criar o(s) job(s) de lembrete após confirmação.

---

## 3. Listas

- **Listas** podem ser o que o cliente quiser (compras, livros, músicas, filmes, receitas, notas, etc.).
- **Categorização automática por AI:** o agente deve inferir a categoria a partir do conteúdo.
  - Ex.: *"Adicione Entre o Céu e o Mar à lista"* → reconhecer que é um livro (Amyr Klink) e adicionar à **lista de livros**.
  - Ex.: *"Radio Gaga"* → reconhecer que é uma música (Queen) e **perguntar** se o cliente quer adicionar à **lista de músicas** (e depois adicionar).
- Quando não for óbvio (ex.: título ambíguo), **perguntar** em que lista o cliente quer guardar, ou sugerir a categoria mais provável e confirmar.

**Lembrete de comprar algo → lista de mercado proativa:**  
Quando o cliente pedir um lembrete para **comprar** algo (ex.: "lembra-me de comprar feijão"), o agente deve **automaticamente e de forma proativa** perguntar se ele quer fazer uma **lista de mercado** e se quer **adicionar mais algum item** à lista. Criar o lembrete e, conforme a resposta, criar ou atualizar a lista de compras (ex.: lista "compras" ou "mercado") e adicionar os itens que o cliente indicar.

---

## Recorrência (eventos e lembretes)

- **Reconhecer recorrência:** Quando o cliente indicar **evento ou lembrete recorrente** (ex.: "preciso ir ao médico toda segunda às 17h", "beber água todo dia às 8h", "academia segunda e quarta 19h"), o sistema deve **detectar** (toda segunda, todo dia, diariamente, semanalmente, etc.), **solicitar a recorrência** se não estiver completa (ex.: "Quando? Ex: todo dia às 8h, toda segunda 17h") e **registrar** com a expressão cron adequada (agenda/lembrete recorrente).
- **Padrões suportados:** "toda segunda às 17h", "toda segunda e quarta 19h", "segunda a sexta 8h", "todo dia às 8h", "diariamente 8h", além de eventos tipicamente recorrentes (academia, aulas, etc.). Após confirmação, perguntar **até quando** (indefinido, fim da semana, fim do mês) e registrar no cron (e opcionalmente na agenda quando for evento).
- **Não tratar como evento único:** Se a mensagem tiver indicador de recorrência (toda segunda, todo dia, …), **não** registrar como evento único na agenda; encaminhar para o fluxo de recorrência.

## Comandos /hoje, /semana e /recorrente

- **/hoje** (e aliases /hoy, /today): mostra **agenda + lembretes** do dia. Duas seções: Lembretes (horários e mensagens que vão disparar hoje) e Agenda (eventos do dia).
- **/semana** (e alias /week): mostra **apenas a agenda** da semana (eventos); não mostra lembretes.
- **/recorrente** (e aliases /recurrente, /recurring): serve **tanto para lembretes quanto para agenda**. Lembretes recorrentes (ex.: beber água todo dia 8h) e eventos recorrentes (ex.: academia segunda e quarta 19h, preciso ir ao médico toda segunda 17h) usam o mesmo fluxo: detectar recorrência, confirmar, perguntar até quando, registrar no cron.

---

## Distinção: evento só agenda, agenda+lembrete, só lembrete, lembrete+evento

Em dados e fluxo, a distinção é esta:

| Caso | O que é | Onde fica | Exemplo |
|------|--------|-----------|---------|
| **Evento apenas agenda** | Compromisso sem aviso | Só na agenda (Event com data_at). Sem job de cron. | Cliente registra "reunião quinta 15h" e diz que não quer lembrete. |
| **Evento que é agenda e lembrete** | Compromisso com aviso | Agenda (Event) + job(s) de cron que disparam na hora (e opcionalmente antes). | Cliente registra "consulta amanhã 10h" e confirma que quer lembrete (e.g. 15 min antes) → evento na agenda + 2 mensagens (15 min antes e às 10h). |
| **Lembrete apenas** | Aviso que dispara, sem compromisso na agenda | Só cron (job). Sem Event. | "Me lembre de tomar remédio às 8h", "me lembre de comprar feijão amanhã 18h", "beber água todo dia 9h". |
| **Lembrete que também é evento** | O mesmo que "Evento que é agenda e lembrete". | Agenda + cron. | Idem segundo caso. |

Resumo operacional: **(1)** Só agenda = Event, sem cron. **(2)** Agenda + lembrete = Event + cron. **(3)** Só lembrete = cron, sem Event. O agente pergunta "quer lembrete?" quando registra um evento; não cria cron para eventos sem confirmação.

---

## Resumo

| Pilar    | O que é                          | Dispara mensagens? | Regra principal                                                                 |
|----------|----------------------------------|--------------------|----------------------------------------------------------------------------------|
| Agenda   | Eventos/compromissos (data, hora)| Não                | Registra na agenda; perguntar hora; perguntar se quer lembrete; só então criar. |
| Lembretes| Avisos que disparam no tempo     | Sim                | Podem estar ligados a um evento da agenda ou ser independentes.                  |
| Listas   | Itens categorizados              | Não                | Categorizar automaticamente por AI; em caso de dúvida, perguntar ou sugerir.   |

Estes princípios devem refletir-se nas instruções do agente (`AGENTS.md`), nos fluxos de handlers e nos prompts de classificação/intenção quando aplicável.
