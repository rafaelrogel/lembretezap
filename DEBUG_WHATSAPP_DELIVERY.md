# Debug: entrega de lembretes no WhatsApp

Quando um lembrete agendado não chega no WhatsApp, siga este checklist e use os logs para achar o ponto de falha.

## Verificação do código (fluxo ok)

O fluxo foi revisado e está consistente:

- **Entrada WhatsApp:** bridge envia `sender` (JID completo) e o canal usa `chat_id=sender` para respostas; `set_context("whatsapp", chat_id)` é chamado em `_process_message` antes do LLM, então o CronTool grava `channel=whatsapp` e `to=JID`.
- **Resposta imediata:** `_process_message` retorna `OutboundMessage(channel=msg.channel, chat_id=msg.chat_id)`; o `run()` do agent faz `publish_outbound(response)`; o ChannelManager consome e chama `channels["whatsapp"].send(msg)`; o canal envia `{ type: "send", to: msg.chat_id, text: msg.content }` ao bridge (Baileys espera JID em `to`).
- **Lembrete (cron):** ao disparar, `on_cron_job` usa `job.payload.channel` e `job.payload.to`; se forem `whatsapp` + JID, publica OutboundMessage e o mesmo caminho acima entrega. Se forem `cli`/`direct` (lembrete criado pelo terminal), não existe canal `cli` e o log mostra "Unknown channel: cli".
- **Bridge:** ao conectar WhatsApp envia `status: "connected"` e o canal Python marca `_connected = True`; o `send()` só envia se `_connected` e `_ws` estiverem definidos.

## Checklist rápido

1. **Lembrete criado pelo WhatsApp**  
   Se você criou o lembrete pelo CLI (`zapista agent -m "me lembre em 2 min"`), o job fica com `channel=cli` e `to=direct`. O gateway **só envia** para o canal `whatsapp`; não existe canal `cli` para entrega.  
   → Crie o lembrete **enviando a mensagem pelo WhatsApp** (ex.: “me lembre em 2 minutos”).

2. **Gateway rodando na hora do disparo**  
   O cron roda **dentro** do processo do gateway. Se o gateway estiver fechado na hora do lembrete, o job não executa e nada é enviado.  
   → Deixe `zapista gateway` rodando até depois do horário do lembrete.

3. **WhatsApp conectado**  
   O bridge (Node) precisa estar conectado (QR já escaneado) e o gateway (Python) conectado ao bridge via WebSocket.  
   → No terminal do gateway deve aparecer algo como “WhatsApp channel enabled” e, no bridge, “Connected to WhatsApp”.

4. **WhatsApp habilitado no config**  
   Em `~/.zapista/config.json` deve ter `channels.whatsapp.enabled: true` e a URL do bridge correta.

5. **Falar contigo mesmo (mensagens guardadas)**  
   Por defeito o bridge **ignora** mensagens em que `fromMe === true` (quando envias para ti mesmo / mensagens guardadas). Para o bot responder quando falas contigo mesmo, define no ambiente do **bridge** `ALLOW_SELF_MESSAGES=1` e reinicia o bridge. No Docker: no `.env` adiciona `ALLOW_SELF_MESSAGES=1` e faz `docker compose restart bridge`. O teu número deve estar em `allow_from` no config.

## Fluxo (para correlacionar com os logs)

```
Cron dispara → on_cron_job → agent.process_direct → bus.publish_outbound(OutboundMessage)
    → ChannelManager._dispatch_outbound → channels["whatsapp"].send()
    → WebSocket para o bridge → bridge envia para o WhatsApp
```

## Logs que foram adicionados

- **Cron deliver:** quando o job tem `deliver=true` e `to` preenchido:  
  `Cron deliver: channel=... to=... content_len=...`
- **Dispatch outbound:** quando a mensagem é enviada para um canal:  
  `Dispatch outbound: channel=whatsapp chat_id=...`
- **Unknown channel:** quando o canal do job não existe (ex.: `cli`):  
  `Unknown channel: cli (message not delivered; enable WhatsApp and add reminder from WhatsApp)`
- **WhatsApp send:** quando o canal WhatsApp envia para o bridge:  
  `WhatsApp send: to=... len=...`
- **WhatsApp send skipped:** quando o bridge não está conectado:  
  `WhatsApp send skipped: bridge not connected`

## Como debugar

1. Rode o gateway com logs visíveis (não em background):  
   `zapista gateway`
2. Crie um lembrete **pelo WhatsApp**, ex.: “me lembre em 2 minutos”.
3. Quando der a hora, observe a sequência no terminal:
   - Aparece `Cron deliver: channel=whatsapp to=...`?  
     - **Não** → job foi criado com outro canal (ex. CLI) ou sem `to`; crie o lembrete pelo WhatsApp.
   - Aparece `Dispatch outbound: channel=whatsapp`?  
     - **Não** → dispatcher não está recebendo a mensagem (bus/outbound).
   - Aparece `WhatsApp send: to=...`?  
     - **Não** → canal WhatsApp não está no manager ou deu erro antes.
   - Aparece `WhatsApp send skipped: bridge not connected`?  
     - **Sim** → bridge/Node não está rodando ou WebSocket desconectado; suba o bridge e escaneie o QR se precisar.

4. **Verificar jobs agendados**  
   Os jobs ficam em `~/.zapista/cron/jobs.json`. Confira se o job tem `channel: "whatsapp"` e `to: "<jid_do_usuario>"` (ex.: `5511999999999@s.whatsapp.net`).

## Resumo das causas mais comuns

| Sintoma | Causa provável |
|--------|-----------------|
| Nenhum log “Cron deliver” na hora | Cron não disparou (gateway parado) ou job com `deliver=false` / `to` vazio |
| “Unknown channel: cli” | Lembrete criado pelo CLI; crie pelo WhatsApp |
| “WhatsApp send skipped: bridge not connected” | Bridge não está rodando ou WebSocket caiu; reinicie bridge e gateway |
| “Dispatch outbound” e “WhatsApp send” aparecem mas não chega no celular | Problema no bridge/Baileys (ver logs do Node) ou número/JID incorreto |
