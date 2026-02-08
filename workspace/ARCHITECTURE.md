# Arquitetura e decisões

## Parser-first (baixa latência)

Comandos estruturados conhecidos (**/lembrete**, **/list**, **/feito**, **/filme**) são tratados **antes** do LLM:

1. **Rate limit** → 2. **Parser** (`backend.command_parser.parse`) → se houver intent, **execução direta** (tools cron/list/event) e resposta imediata.
2. Só se o parser não reconhecer a mensagem é que entram o **scope filter** (LLM ou regex) e o **loop do agente** (LLM + tools).

Assim reduz-se latência e custo para comandos simples; o LLM é usado para linguagem natural ou casos ambíguos.

## Volume único e escala horizontal

O `docker-compose` usa um **único volume** (`nanobot_data`) partilhado por bridge, gateway e API. Isto é adequado para **uma instância** (um gateway + um bridge + uma API).

- **Várias instâncias** (escala horizontal) com o mesmo volume podem causar **conflitos** (cron store, SQLite, sessões).
- Para escalar horizontalmente é necessário:
  - **Armazenamento distribuído** ou **BD centralizado** (ex.: PostgreSQL em vez de SQLite, Redis para filas/cron), e
  - Não partilhar o mesmo ficheiro de cron/DB entre gateways.

Por agora a arquitetura assume **uma instância** por deploy.

## Logs estruturados e correlação

- Cada mensagem recebida tem um **trace_id** (gerado no canal ou em `process_direct`).
- O **trace_id** é definido no contexto da request e incluído nos logs (formato texto ou JSON), permitindo seguir uma mensagem em todos os componentes.
- **JSON logs:** definir `NANOBOT_LOG_JSON=1` (e opcionalmente `NANOBOT_LOG_LEVEL=DEBUG`) para saída em JSON, adequada a agregadores (e.g. ELK, Datadog).

## Circuit breaker (LLM e chamadas externas)

- **Implementado:** um circuit breaker protege as chamadas ao LLM (incluindo o scope filter).
- Após **N falhas** (ex.: 3) seguidas, o circuito abre e o sistema entra em **modo degradado**: só o parser de comandos e o scope rápido (regex) são usados; não se chama a API do LLM.
- Resposta em modo degradado: *"Serviço temporariamente limitado. Use comandos /lembrete, /list ou /filme."*
- Após um **timeout de recuperação** (ex.: 60 s), o circuito passa a half-open e uma nova chamada é tentada; sucesso fecha o circuito, falha reabre.
- Assim evita-se cascata de falhas quando a API do LLM está lenta ou indisponível.

## Otimizações futuras (roadmap)

### Cache de respostas do LLM
- **Vale a pena?** Sim, para reduzir custo e latência em perguntas repetidas ou muito parecidas.
- **Implementação sugerida:** cache com TTL por tipo de contexto (ex.: 60 s para perguntas genéricas, invalidação quando listas/eventos do utilizador mudam). Pode começar com um cache em memória (chave = hash do prompt + user/session) e depois migrar para Redis com TTL e invalidação explícita.
- **Estado atual:** não implementado; o parser-first já reduz muitas chamadas ao LLM.

### Message queue (Redis / RabbitMQ)
- **Vale a pena?** Sim para produção com maior resiliência e escala: fila permite retry, múltiplos workers e resposta imediata do bridge (“mensagem recebida”) com processamento em background.
- **Implementação sugerida:** o bridge publica na fila e responde “ok” ao utilizador; um ou mais workers consomem a fila e chamam o agente; em falha a mensagem volta para a fila ou dead-letter.
- **Estado atual:** não implementado; o fluxo é síncrono (bridge → gateway → agente → resposta). Para escalar horizontalmente e tolerar falhas, a fila é o próximo passo natural.
