# Onboarding: nome, cidade e preferências de lembretes

## Ideia

Quando o utilizador agenda um evento (ex.: consulta médico 01/10/2026 às 15h), o sistema envia **duas mensagens** por defeito:

1. **Uma X tempo antes** do evento (ex.: 1 dia antes, 2 horas antes) — o utilizador escolhe este “X” no onboarding.
2. **Uma no dia e hora** do evento (01/10/2026 15:00).

Além disso, perguntamos no onboarding se quer **até 3 avisos extra antes** do evento (“lembrete do lembrete”), cada um com o seu “X” (ex.: 3 dias antes, 1 dia antes, 30 min antes). Assim o cliente pode receber, por exemplo:

- 3 dias antes  
- 1 dia antes  
- 2 horas antes  
- No momento do evento (15:00 do dia 01/10)

Tudo é explicado de forma clara durante o onboarding, com mensagens geradas pelo **DeepSeek** (natural, fluida, simpática, com emojis).

---

## Resumo para o cliente

- **Nome:** como queres que te chamemos.  
- **Cidade:** em que cidade estás? Aceitamos **qualquer cidade do mundo**. Se a reconhecermos, ajustamos o fuso; senão guardamos e podes usar `/tz Cidade` depois.  
- **Primeiro aviso:** “Quanto tempo antes do evento queres o primeiro lembrete?” (ex.: 1 dia, 2 horas).  
- **Avisos extra:** “Queres mais algum aviso antes do evento? Até 3, no mesmo estilo (ex.: 3 dias, 1 dia, 30 min).”  

Para cada evento que agendares, recebes sempre o lembrete **na hora** do evento e ainda os avisos **X tempo antes** que definiste.

---

## Exemplo 1 — Onboarding completo (pt-PT)

**Sistema:**  
Olá! 👋 Para personalizar as tuas lembranças, como gostarias que eu te chamasse?

**Utilizador:**  
Marta.

**Sistema:**  
Obrigado, Marta! 📋  
Próximo passo: em que cidade estás? (Assim acertamos o fuso para as horas dos lembretes.)

**Utilizador:**  
Lisboa.

**Sistema:**  
Perfeito, Lisboa está registada. 🌍  
Agora os avisos: quando agendas um evento (ex.: médico às 15h do dia 1 de outubro), enviamos-te **um lembrete na hora** (15h do dia 1) e **outro X tempo antes**. Quanto tempo antes queres esse primeiro aviso? (Ex.: 1 dia, 2 horas ou 30 minutos.)

**Utilizador:**  
1 dia antes.

**Sistema:**  
Combinado! 👍 Receberás um aviso 1 dia antes e outro na hora do evento.  
Queres mais algum aviso antes? (Até 3, no mesmo esquema — ex.: 3 dias antes, 2 horas antes. Se não quiseres, diz «não».)

**Utilizador:**  
Sim, 3 dias e 2 horas antes.

**Sistema:**  
Tudo certo, Marta! ✨ Fica assim:  
• 3 dias antes do evento  
• 1 dia antes  
• 2 horas antes  
• E no dia e hora do evento  

Ou seja, 4 mensagens por evento. Qualquer coisa, é só dizeres. 😊

---

## Exemplo 2 — Onboarding curto (pt-BR)

**Sistema:**  
Oi! 👋 Como você gostaria que eu te chamasse?

**Utilizador:**  
Rodrigo.

**Sistema:**  
Valeu, Rodrigo! 💙  
Quanto tempo antes de um evento você quer o primeiro aviso? (Ex.: 1 dia, 2 horas ou 30 min.)

**Utilizador:**  
2 horas.

**Sistema:**  
Anotado! 📌 Então você recebe um aviso 2 horas antes e outro na hora.  
Quer mais algum aviso antes? (Até 3 — ex.: 1 dia, 30 min. Ou diga «não».)

**Utilizador:**  
Não.

**Sistema:**  
Beleza! Fica só o aviso 2 horas antes + o lembrete na hora. Qualquer coisa, manda mensagem. ✨

---

## Exemplo 3 — Onboarding com 3 avisos extra (es)

**Sistema:**  
¡Hola! 👋 ¿Cómo te gustaría que te llamara?

**Utilizador:**  
Carmen.

**Sistema:**  
Gracias, Carmen. 📋  
¿Cuánto tiempo antes del evento quieres el primer aviso? (Ej.: 1 día, 2 horas, 30 min.)

**Utilizador:**  
1 día.

**Sistema:**  
Perfecto. 👍 Recibirás un aviso 1 día antes y otro en el momento del evento.  
¿Quieres más avisos antes? (Hasta 3, ej.: 3 días, 12 horas, 30 min. Di «no» si no.)

**Utilizador:**  
Sí: 3 días, 1 día y 30 minutos antes.

**Sistema:**  
Listo, Carmen. ✨ Quedan 4 avisos por evento:  
• 3 días antes  
• 1 día antes  
• 30 min antes  
• Y en el día y hora del evento  

Así no se te escapa nada. 😊

---

## Notas técnicas

- **Armazenamento:** `User.default_reminder_lead_seconds` (um valor) e `User.extra_reminder_leads` (lista de até 3 valores, em segundos).  
- **Criação de jobs:** Para um evento em `in_seconds` a partir de agora: 1 job em `in_seconds` (na hora) + 1 job em `in_seconds - default_lead` + 1 job por cada valor em `extra_reminder_leads` em `in_seconds - extra_lead`.  
- **Mensagens do onboarding:** Geradas pelo DeepSeek (prompt por passo) para ficarem naturais, fluidas e com emojis.
