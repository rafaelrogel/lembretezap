# Memória do cliente (contexto persistente)

O sistema regista e usa **sempre** as informações básicas de cada cliente para que a LLM e o sistema forneçam horários corretos e respostas no idioma certo. Cada cliente tem um ficheiro de memória e o conteúdo é injetado no contexto do agente em todas as interações.

## O que fica registado (sempre)

Para cada cliente, o sistema guarda e expõe à LLM:

| Dado | Origem | Uso |
|------|--------|-----|
| **Nome** | `User.preferred_name` (onboarding ou definido depois) | Tratamento pessoal; respostas e lembretes podem usar o nome |
| **Timezone** | `User.timezone` (onboarding /tz ou cidade) ou inferido do número | **Horários sempre no fuso do cliente**; lembretes na hora local certa |
| **Idioma de comunicação** | `User.language` (onboarding /lang ou inferido) | Respostas e lembretes neste idioma |

O servidor/VPS pode estar em UTC ou outro fuso. O sistema e a LLM comparam com a hora local do servidor e fazem a conversão para o fuso do cliente, para que:

- Os lembretes disparem **no horário local do cliente**.
- Respostas como "que horas são?" e quaisquer referências a horas estejam **no fuso do cliente**.

## Onde é usado

1. **System prompt do agente**  
   Em cada conversa, é injetada uma secção **"Cliente (memória)"** com nome, timezone, idioma e a instrução de usar sempre o fuso do cliente para horários. A LLM acede a isto em todas as respostas.

2. **Ficheiro por cliente**  
   É criado/atualizado um ficheiro por cliente em:
   - `workspace/users/<chat_id_safe>.md`  
   O conteúdo é o mesmo da secção "Cliente (memória)" (nome, timezone, idioma, instrução de fuso e, se existir, `context_notes`). O sistema e a LLM podem sempre aceder a este ficheiro; ele é atualizado sempre que o contexto do agente é construído para esse cliente (refletindo assim alterações na BD).

3. **Entrega de lembretes**  
   O cron e a entrega de lembretes já usam o timezone do utilizador (BD) para agendar e enviar na hora local. A memória do cliente reforça esse comportamento no contexto da LLM.

## Notas adicionais (`context_notes`)

Na BD, o campo opcional **`User.context_notes`** (texto livre) é incluído na mesma secção "Cliente (memória)" e no ficheiro do cliente. Serve para informações extra (preferências, restrições, dados que o utilizador partilhou). Exemplos:

- "Prefere ser lembrado com 15 min de antecedência para reuniões."
- "Não sugerir lembretes após as 22h."
- "Toma amoxilina de 8 em 8 horas até dia X."

Para instalações já existentes, se a coluna não existir:

```sql
ALTER TABLE users ADD COLUMN context_notes TEXT;
```

## Resumo

| Onde | O quê | Uso |
|------|--------|-----|
| BD | `User.preferred_name`, `User.timezone`, `User.language` (e opcionalmente `context_notes`) | Fonte de verdade; usado para construir a memória e o ficheiro |
| System prompt | Secção "Cliente (memória)" | LLM vê sempre nome, timezone, idioma e instrução de fuso |
| Ficheiro | `workspace/users/<chat_id_safe>.md` | Um ficheiro por cliente; criado/atualizado ao construir o contexto; sistema e LLM podem aceder |

Assim, o nome, o timezone e o idioma de comunicação ficam registados na memória do cliente, o sistema e a LLM acedem sempre a esse contexto, e os horários são fornecidos no fuso do cliente, com a devida conversão em relação ao horário do servidor/VPS, para que os lembretes cheguem na hora certa no local do cliente.
