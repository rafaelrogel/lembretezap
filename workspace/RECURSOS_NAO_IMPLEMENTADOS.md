# Recursos estudados / documentados mas não implementados

Lista de funcionalidades com documento de viabilidade, “em breve” no código ou referidas em conformidade/plano e que **ainda não foram implementadas**. (O .ics já foi implementado e sai desta lista.)

---



## 4. /feito com só o ID (sem nome da lista)

**Onde:** `CONFORMIDADE_PEDIDO.md`; `backend/command_parser.py`, `handlers.py`  
**Estado:** Hoje é obrigatório **/feito nome_da_lista id**. O pedido era permitir **/feito 1** (apagar por ID global ou inferir lista).

**Ideia:**  
- Aceitar `/feito 1` e: ou (a) interpretar como “item id=1 em qualquer lista” (primeira que tiver esse id), ou (b) manter lista obrigatória mas aceitar um alias “principal” (ex.: /feito 1 = /feito pendentes 1).  

**Dependências:** Decisão de semântica; alteração do parser e da ListTool/handler.

---



## 6. Pagantes (#paid) e critério “assinatura ativa”

**Onde:** `backend/admin_commands.py` — #paid  
**Estado:** #paid existe; devolve *"Total pagantes: 0 (critério: assinatura ativa – a definir)"*. TODO: “coluna subscription_active ou tabela payments”.

**Ideia:**  
- Definir critério de “utilizador pagante” (ex.: coluna em User ou tabela de pagamentos).  
- #paid usar esse critério e devolver contagem real.

**Dependências:** Modelo de dados (subscription/payments) e migração; depois query no handler #paid.

---

## 7. Redis queue no deploy ✅ (implementado)

**Onde:** `docker-compose.yml`, `zapista/bus/redis_queue.py`, `zapista/bus/queue.py`  
**Estado:** Serviço redis no Compose; fila outbound com Redis quando REDIS_URL está definido. MessageBus usa push Redis + feeder task que drena para a queue local. Documentos referem “Redis queue” como opcional/em falta.

**Ideia:**  
- Fila assíncrona (ex.: para envio de mensagens ou jobs pesados) com Redis.  
- Adicionar serviço `redis` ao docker-compose e, se necessário, um worker que consuma a fila.

**Dependências:** Definir casos de uso (quê vai para a fila); implementar producer/consumer; opcional para MVP.

---

## 8. SQLite criptografado (produção) ✅ (implementado)

**Onde:** `backend/database.py`, `pyproject.toml` (optional-deps encryption), `.env.example`  
**Estado:** SQLite **sem** criptografia em repouso; documentos dizem “MVP sem cripto; prod: SQLCipher ou volume cripto”.

**Ideia:**  
- Em produção, usar SQLCipher ou volume já criptografado para o ficheiro da BD.  
- Não é MVP; fica como melhoria de segurança para produção.

---

## 9. Botões na confirmação (WhatsApp Business API)

**Onde:** `backend/handlers.py`, `backend/confirmations.py`, `zapista/agent/loop.py`, bridge  
**Estado:** Vários TODOs: *"Após WhatsApp Business API, use buttons: sendButtons(['Confirmar','Cancelar'])"*. Hoje as confirmações são por texto (1=sim, 2=não).

**Ideia:**  
- Quando a ligação for pela **API oficial** do WhatsApp Business, usar botões nativos para Confirmar/Cancelar em vez de "1=sim 2=não".  

**Dependências:** Migração para Business API; suporte a envio de botões no canal e parsing de respostas a botões.

---

## Resumo

| Recurso              | Documento / local           | Complexidade estimada |
|----------------------|----------------------------|---------------------------|
| /hoje, /semana       | handlers.py “em breve”     | Média                     |
| /quiet               | handlers.py “em breve”     | Média                     |
| /livro, /musica      | CONFORMIDADE_PEDIDO        | Baixa                     |
| /feito 1 (só id)     | CONFORMIDADE_PEDIDO        | Baixa–média               |

| #paid pagantes       | admin_commands.py          | Média (modelo de dados)   |
| Redis no deploy      | FEASIBILITY, CONFORMIDADE  | Média                     |
| SQLite cripto        | FEASIBILITY, CONFORMIDADE  | Média (opcional prod)     |
| Botões Business API  | TODOs em vários ficheiros  | Depende da migração API   |
| Summarization / filtragem histórico | session/context/loop (fase posterior) | Média–alta          |

Para implementar algo no estilo do .ics (documento de viabilidade + fluxo concreto), os candidatos mais diretos são **/hoje** e **/semana** (visões) e **/livro** e **/musica** (comandos espelhando /filme).

---

## 10. Otimização de tokens — summarization e filtragem de histórico (fase posterior)

**Onde:** `zapista/session/manager.py` (histórico), `zapista/agent/context.py` (contexto), `zapista/agent/loop.py` (build_messages).  
**Estado:** Não implementado. Registado para **fase posterior** (após medir uso real: tamanho das sessões, tokens, custo).

**Ideia:**  
- **Summarization do histórico:** em vez de manter todas as mensagens na janela de contexto, condensar periodicamente mensagens antigas em resumos que ocupam menos tokens mas preservam a essência das interações. Permite conversas mais longas sem atingir o limite da janela.  
- **Filtragem inteligente do histórico:** incluir no contexto apenas mensagens relevantes para a tarefa atual (ex.: ao processar um lembrete, não enviar todo o histórico de listas). Atenção: filtrar demais pode remover contexto útil (“como combinamos ontem”).

**Quando implementar:** Quando houver métricas que justifiquem (sessões longas, custo de tokens alto). Até lá, o limite atual de 50 mensagens recentes (`get_history(max_messages=50)`) e o uso do Xiaomi/MiMo em fluxos simples já reduzem custo.
