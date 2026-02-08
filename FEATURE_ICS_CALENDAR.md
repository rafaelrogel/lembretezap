# Viabilidade: anexo .ics / iCalendar

## É possível receber um anexo .ics e registar eventos no sistema?

**Sim.** É perfeitamente possível programar o seguinte fluxo:

1. **Recepção do anexo**  
   O bridge WhatsApp (Baileys) já pode receber mensagens com anexos. É preciso:
   - No bridge (Node): detetar mensagem com documento/ficheiro.
   - Fazer download do ficheiro (URL ou buffer).
   - Se a extensão for `.ics` (ou o mime type `text/calendar`), enviar o conteúdo (ou o ficheiro) para o gateway/backend.

2. **Leitura do .ics**  
   O formato iCalendar (.ics) é texto (RFC 5545). Em Python pode usar-se:
   - **`icalendar`** (pip install icalendar): ler o .ics e obter eventos (nome, data/hora início e fim, descrição, local, URL, etc.).
   - Exemplo de campos por evento: `summary` (nome), `dtstart`/`dtend`, `description`, `location`, `url`.

3. **Registo no sistema**  
   Para cada evento lido do .ics:
   - Criar um **lembrete** (cron) para a data/hora do evento (e opcionalmente notificação antes).
   - Ou criar um **evento** na tabela `Event` (tipo `evento`, payload com nome, data, link, observação).
   - Associar ao `user_id` (pelo número de telefone do remetente).

4. **Resposta ao utilizador**  
   Enviar uma mensagem do tipo: “Encontrados 3 eventos no calendário: «Reunião X» (dia D às H), … Registados. Quer que eu lembre antes?”

### Resumo

| Aspecto              | Viabilidade |
|----------------------|------------|
| Receber anexo no WA  | Sim (bridge já suporta; falta encaminhar .ics). |
| Ler .ics em Python  | Sim (biblioteca `icalendar`). |
| Extrair nome, data, hora, link, notas | Sim (campos standard do RFC 5545). |
| Guardar como lembrete/evento | Sim (cron + BD já existentes). |

### Próximos passos sugeridos

1. **Bridge (Node):** ao receber mensagem com anexo, verificar se é `.ics` ou `text/calendar`; fazer download e enviar o corpo do .ics (ou URL temporária) para o gateway, por exemplo num campo `attachment_ics` no payload da mensagem.
2. **Backend (Python):** novo handler ou tool, por exemplo `handle_ics_payload(chat_id, ics_content)` que:
   - Parse com `icalendar`;
   - Para cada `VEVENT`, extrair summary, dtstart, dtend, description, location, url;
   - Criar eventos/lembretes na BD e no cron;
   - Devolver texto de resumo para enviar ao utilizador.

Com isto, o fluxo “enviar anexo .ics → ler → registar eventos com nome, data, hora e outros dados importantes” fica implementável de forma direta.
