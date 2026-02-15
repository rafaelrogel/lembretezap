# Mensagens empáticas e positivas em lembretes

Quando um **lembrete é entregue** (cron), o sistema verifica se o texto do lembrete encaixa numa destas situações e, em caso afirmativo, **acrescenta** uma mensagem extra ao final da entrega.

## Dois tipos

| Tipo | Objetivo | Exemplos de situações | Exemplo de mensagem |
|------|----------|------------------------|---------------------|
| **Empatia** | Situações difíceis/graves | Enterro, médico, oncologia, cirurgia, advogado, falecimento, resultados de exames, veterinário (perda), etc. | «Espero que esteja tudo bem. Cuida-te.» / «Os meus sentimentos. Cuida de ti.» |
| **Positividade** | Estudos, trabalho, encontros, diversão | Encontro com amigos, date, filme, apresentação, exame, entrevista de emprego, campeonato, jantar, festa, viagem, reunião, concerto, treino, etc. | «Aproveita o jantar!» / «Boa sorte na apresentação!» / «Não bebas demais perto do chefe — só quando não estiver a olhar. 😉» |

**Prioridade:** primeiro tenta **empatia**; se não houver match, tenta **positividade**. Só se acrescenta **uma** mensagem por lembrete.

## Onde está implementado

- **Dados:** `backend/empathy_positive_data.py`  
  - `EMPATHY_CATEGORIES`: lista de categorias (keywords por idioma + mensagem por idioma).  
  - `POSITIVE_CATEGORIES`: idem para situações positivas.
- **Lógica:** `backend/empathy_positive_messages.py`  
  - `get_extra_message_for_reminder(content, user_lang)` → devolve a mensagem extra ou `""`.
- **Uso:** `zapista/cli/commands.py` no callback `on_cron_job`: antes de enviar o lembrete ao canal, chama `get_extra_message_for_reminder` e concatena ao texto da resposta.

## Idiomas

Cada categoria tem:
- `keywords`: dicionário por idioma (`pt-BR`, `pt-PT`, `es`, `en`) com lista de palavras/frases que disparam a categoria.
- `messages`: dicionário por idioma com a frase a acrescentar.

O idioma usado é o do utilizador (ex.: `get_user_language(db, chat_id)`).

## Contagens atuais (por idioma)

- **Empatia:** ~200 situações (keywords) por idioma, em ~18 categorias (enterro, médico, oncologia, psicólogo, cirurgia, emergência, advogado, falecimento, exames diagnósticos, dentista, fisioterapia, veterinário, hospício, desemprego, polícia/justiça, especialista, internamento, exame invasivo).
- **Positividade:** ~275+ situações por idioma, em ~24 categorias (amigos, date, filme, apresentação, exame, entrevista, campeonato, jantar, festa, viagem, reunião, concerto, treino, café, networking, casamento/família, primeiro dia de trabalho, entrega de projeto, série, hobby/aula, jogo, spa, compras, passeio).

Para chegar a **400 situações positivas** por idioma: acrescentar mais categorias em `POSITIVE_CATEGORIES` (ex.: mais tipos de encontros, eventos, desportos, cursos, celebrações) ou mais keywords em categorias já existentes.

## Exemplos de frases

- **Empatia (médico):** «Espero que esteja tudo bem. Cuida-te.»  
- **Empatia (enterro):** «Os meus sentimentos. Cuida de ti.»  
- **Empatia (oncologia):** «Força. Estou contigo. Cuida-te.»  
- **Positividade (jantar):** «Aproveita o jantar! (E não bebas demais perto do chefe — só quando não estiver a olhar. 😉)»  
- **Positividade (apresentação):** «Boa sorte na apresentação! Vais arrasar.»  
- **Positividade (encontro amigos):** «Aproveita o momento!»

## Como acrescentar situações

1. Abrir `backend/empathy_positive_data.py`.
2. Em `EMPATHY_CATEGORIES` ou `POSITIVE_CATEGORIES`, acrescentar um novo dicionário com:
   - `"keywords"`: `{"pt-BR": [...], "pt-PT": [...], "es": [...], "en": [...]}`  
   - `"messages"`: `{"pt-BR": "...", "pt-PT": "...", "es": "...", "en": "..."}`  
3. O match é por **substring** no texto do lembrete (em minúsculas). Colocar palavras/frases que o utilizador possa usar ao criar o lembrete.
