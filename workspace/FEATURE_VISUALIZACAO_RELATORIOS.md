# Comandos de Visualização e Relatórios

Plano de implementação para calendário visual, estatísticas e timeline.

---

## 1. Calendário visual

### 1.1 Vale a pena ver **mês**?
**Sim.** Um mês cabe bem em mensagem WhatsApp (formato ASCII compacto) e dá visão útil para planeamento. Exemplo:
```
       FEV 2026
   D  S  T  Q  Q  S  S
 1  2  3  4  5  6  7  8
 9 10 11 *12 13 14 15
16 17 18 19 20 21 22
23 24 25 26 27 28
* = tem evento
```
Comandos: `/mes` ou `/mes 3` (Março).

### 1.2 Vale a pena ver **trimestre**?
**Talvez.** Um trimestre em texto fica denso (3 meses), mas pode ser resumido: "Jan: 5 eventos, Fev: 3, Mar: 2" ou mini-calendário por mês. Útil para visão de longo prazo. Sugestão: implementar **depois** de mês/semana/dia; prioridade média.

### 1.3 Visões propostas

| Comando | Escopo | Formato | Estado atual |
|---------|--------|---------|--------------|
| `/dia` ou `/hoje` | 1 dia | Lista eventos + lembretes por hora | ✅ Implementado |
| `/semana` | 7 dias | Lista por dia | ✅ Implementado |
| `/mes` | 1 mês | Calendário ASCII com marcadores | ✅ Implementado |
| `/trimestre` | 3 meses | Resumo ou mini-calendários | 🔲 Novo (baixa prioridade) |

**Dados:** Event (`data_at`), Cron jobs (next_run_at_ms), timezone do user.

---

## 2. Estatísticas pessoais

### 2.1 Tarefas feitas por dia/semana
**Fonte de dados:**
- `AuditLog` com `action='list_feito'` — quando o user marca item como feito (hoje remove o item; o audit fica).
- `ReminderHistory` com `status='sent'` — lembretes entregues (proxy de "tarefa feita" se confirmou 👍).
- Opcional: adicionar `ListItem.done_at` para itens marcados feito **sem** apagar (mudança de modelo).

**Hoje:** `feito` **apaga** o item; só o `AuditLog` guarda que houve "list_feito". Podemos contar por dia:
```sql
SELECT DATE(created_at), COUNT(*) FROM audit_log
WHERE user_id=? AND action='list_feito'
GROUP BY DATE(created_at)
```

**Comandos:** ✅ Implementado
- `/stats` — resumo: hoje X feitos, esta semana Y
- `/stats dia` — últimos 7 dias (tabela)
- `/stats semana` — últimas 4 semanas

---

## 3. Relatório de produtividade

### 3.1 Evolução ao longo do tempo
Agregar por semana ou mês:
- Itens feitos (list_feito)
- Lembretes recebidos (ReminderHistory sent)
- Eventos criados (Event)
- (Futuro) taxa de conclusão de lembretes (👍 vs total enviados)

**Formato:** texto curto, ex.:
```
📊 Produtividade (últimas 4 semanas)
S1: 5 tarefas | 3 lembretes
S2: 8 tarefas | 4 lembretes
S3: 4 tarefas | 2 lembretes
S4: 7 tarefas | 5 lembretes
```

**Comando:** `/produtividade` ou `/relatorio`

---

## 4. Timeline

### 4.1 Histórico cronológico
Unificar eventos, lembretes entregues, tarefas feitas e (opcional) mensagens de sessão num fluxo temporal.

**Fontes:**
- `Event` (criado, data_at)
- `ReminderHistory` (delivered_at)
- `AuditLog` (list_feito, event_add, etc.)
- Cron jobs executados (hoje não persiste; apenas ReminderHistory)

**Formato:** lista ordenada por data, ex.:
```
📜 Timeline (últimos 7 dias)
08/02 09:00 — Lembrete: tomar remédio ✓
08/02 14:00 — Feito: mercado #2 (leite)
07/02 20:00 — Evento: reunião com João
07/02 18:00 — Lembrete: PIX ✓
...
```

**Comando:** `/timeline` (ou `/timeline 14` para 14 dias) — ✅ Implementado

---

## 5. Ordem de implementação sugerida

1. **Calendário mês** (`/mes`) — reutiliza `_visao_hoje_semana`, nova função `_visao_mes`
2. **Timeline** (`/timeline`) — junta AuditLog + ReminderHistory + Event; ordena por data
3. **Estatísticas** (`/stats`) — conta AuditLog list_feito + ReminderHistory sent por dia/semana
4. **Relatório produtividade** (`/produtividade`) — agregação semanal/mensal
5. **Calendário trimestre** (`/trimestre`) — opcional, após feedback

---

## 6. Ficheiros a alterar

| Recurso | Ficheiros |
|---------|-----------|
| /mes | `command_parser.py`, `handlers.py` |
| /timeline | `handlers.py`, `routes.py` (API?) |
| /stats | `handlers.py` |
| /produtividade | `handlers.py` |
| /trimestre | `handlers.py` |

---

## 7. Considerações

### WhatsApp vs Web
- **WhatsApp:** texto, emojis, listas curtas. Calendário em ASCII; stats em blocos curtos.
- **Web/API:** poderia ter JSON para calendário, gráficos (frontend separado).

### Limites
- WhatsApp: mensagens longas podem ser cortadas; preferir resumos e paginação (`/timeline 2` = página 2).
- Performance: queries com `GROUP BY`, índices em `created_at`, `delivered_at`.
