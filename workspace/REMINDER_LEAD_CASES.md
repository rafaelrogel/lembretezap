# Casos: aviso antes do evento vs só lembrete na hora

O sistema classifica cada lembrete para decidir se deve ou não criar avisos **antes** do evento (usando a preferência do utilizador do onboarding) ou apenas o lembrete na hora.

- **Precisa de aviso antes:** reunião, consulta, voo, ônibus, encontro, entrevista, etc. → aplicam-se o “primeiro aviso” e os “avisos extras” configurados no onboarding.
- **Não precisa:** tomar remédio às 15h, acordar, ligar, enviar email, beber água, etc. → só o lembrete no momento.
- **Evento muito longo** (ex.: daqui a mais de 5 dias): um único aviso **24h antes**, automático, sem perguntar ao cliente.

Listas completas em `backend/reminder_lead_classifier.py` (NEED_ADVANCE_KEYWORDS e NO_ADVANCE_KEYWORDS). Resumo por categoria:

---

## ~200+ casos em que **é necessário** aviso antes (exemplos)

| Categoria | Exemplos |
|-----------|----------|
| Reuniões e trabalho | reunião, meeting, apresentação, entrevista, conferência, workshop, webinar, call, zoom, daily, standup, deadline, entrega de projeto |
| Consultas e saúde (compromissos) | consulta médica, médico, doutor, clínica, hospital, exame, vacina, dentista, fisioterapia, psicólogo, oftalmologista, cirurgia |
| Viagens e transportes | voo, flight, embarque, aeroporto, ônibus, barco, ferry, trem, comboio, metro, viagem, transfer, aluguel de carro |
| Encontros e eventos sociais | encontro, compromisso, appointment, casamento, festa, aniversário, formatura, jantar, visita |
| Educação e provas | prova, exame escolar, aula, curso, defesa de tese, TCC, matrícula, entrega de trabalho |
| Serviços e compromissos externos | corte de cabelo, barbearia, advogado, contador, banco, cartório, vistoria, instalação |
| Eventos culturais/desportivos | jogo, partida, cinema, teatro, show, concerto, exposição, museu, festival |
| Outros | treino, aula de condução, veterinário, oficina, seguro, passaporte, visto, reunião de condomínio, abertura de empresa, etc. |

---

## ~200+ casos em que **não é necessário** aviso antes (exemplos)

| Categoria | Exemplos |
|-----------|----------|
| Medicação e saúde rotineira | tomar remédio, tomar medicamento, comprimido, insulina, colírio, beber água, alongar, medir pressão, dormir, acordar |
| Tarefas domésticas | lavar louça, lavar roupa, passar roupa, varrer, aspirar, limpar, tirar lixo, regar plantas, comida do gato |
| Chamadas e comunicações | ligar, enviar email, mensagem, devolver chamada |
| Pagamentos (sem deslocação) | pagar conta, PIX, transferência, boleto, recarga |
| Compras/rotinas | comprar, mercado, farmácia, lista de compras |
| Trabalho (tarefas pontuais) | enviar relatório, enviar proposta, revisar, estudar, fechar planilha |
| Rotinas pessoais | café da manhã, almoço, banho, escovar dentes, exercício, caminhada |
| Lembretes simples | verificar, desligar, tirar do forno, trocar fralda, tomar sol, cortar unha, hidratar, etc. |

---

## Opção escolhida no fluxo

- **Não perguntar por lembrete:** o sistema **não** pergunta “quer aviso antes?” em cada lembrete.
- Usa a **preferência do onboarding** (primeiro aviso + até 3 extras) **só** quando o classificador decide que aquele tipo de lembrete **precisa** de aviso antes (reunião, consulta, voo, etc.).
- Para “tomar remédio às 15h” → nenhum aviso antes, só o lembrete às 15h.
- Para “reunião amanhã 10h” → avisos antes conforme o que o utilizador definiu no onboarding.
- Para eventos muito longos (ex.: daqui a 20 dias) → um aviso 24h antes, automático.

Em caso de **ambiguidade**, o MiMo é usado para responder YES/NO (precisa ou não de aviso antes).
