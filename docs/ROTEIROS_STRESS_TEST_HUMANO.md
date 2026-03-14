# Roteiros de Stress Test - Testadores Humanos

**Data:** Março 2026  
**Objetivo:** Validar o sistema em condições reais de uso intensivo  
**Duração:** 30-45 minutos por testador

---

## Instruções Gerais para Todos os Testadores

1. **Anote TUDO que parecer errado** (prints, descrição do problema)
2. **Não espere respostas** - envie mensagens em rajada quando indicado
3. **Use o WhatsApp normalmente** - pode ser no celular ou WhatsApp Web
4. **Horário:** Combinar para todos testarem simultaneamente (stress máximo)
5. **Reporte:** Enviar feedback no grupo de testadores após terminar

---

## ROTEIRO 1 - BRASIL 🇧🇷
### Foco: Volume de Listas e Itens em Rajada

**Testador:** _____________  
**Telefone:** _____________  
**Início:** ___:___  

#### Fase 1: Aquecimento (5 min)
```
/start
meu nome é [seu nome]
moro em São Paulo
```

#### Fase 2: Rajada de Itens - Lista Mercado (10 min)
Envie TODAS estas mensagens em sequência RÁPIDA (não espere resposta):

```
adiciona na lista: arroz, feijão, macarrão, óleo, sal, açúcar
coloca na lista: leite, ovos, queijo, presunto, manteiga
põe na lista: tomate, cebola, alho, batata, cenoura, abobrinha
adiciona na lista: frango, carne moída, linguiça, bacon, peixe
coloca na lista: café, chá, suco, refrigerante, água mineral
adiciona na lista: sabão em pó, detergente, amaciante, esponja
põe na lista: shampoo, condicionador, sabonete, pasta de dente
coloca na lista: papel higiênico, guardanapo, papel toalha
adiciona na lista: biscoito, chocolate, sorvete, bolo, pudim
coloca na lista: pão de forma, pão francês, torrada, cream cheese
```

#### Fase 3: Operações na Lista (5 min)
```
/list mercado
feito arroz
feito leite
remove sabão em pó
/list mercado
```

#### Fase 4: Criar Múltiplas Listas (5 min)
Envie em rajada:
```
/list filmes add Matrix, Interestelar, Inception, Coringa, Parasita
/list livros add O Alquimista, 1984, Dom Casmurro, Harry Potter
/list músicas add Bohemian Rhapsody, Imagine, Hotel California
/list séries add Breaking Bad, Game of Thrones, Stranger Things, The Office
/list jogos add FIFA 24, GTA VI, Zelda, Mario Kart, Minecraft
```

#### Fase 5: Ver Todas as Listas (3 min)
```
/list
/list filmes
/list livros
/list músicas
minhas listas
```

#### Fase 6: Lembretes em Rajada (5 min)
Envie em rajada:
```
me lembra de ligar pro médico em 10 minutos
lembra de pagar a conta de luz amanhã às 9h
me avisa pra tomar remédio daqui 2 horas
lembrete: reunião sexta às 14h
me lembra de comprar presente da mãe no sábado
```

#### Fase 7: Consultas (5 min)
```
/hoje
/semana
minha agenda
o que tenho pra fazer?
```

#### Fase 8: Reset e Novo Ciclo (5 min)
```
/nuke
```
(Confirme com `1`)
```
oi
meu nome é Teste
adiciona leite na lista
```

#### Checklist de Problemas:
- [ ] Mensagens não respondidas
- [ ] Itens duplicados na lista
- [ ] Lembretes não criados
- [ ] Erros ou mensagens estranhas
- [ ] Demora excessiva (>30 segundos)
- [ ] Bot travou/parou de responder

---

## ROTEIRO 2 - BRASIL 🇧🇷
### Foco: Áudios e Linguagem Natural

**Testador:** _____________  
**Telefone:** _____________  
**Início:** ___:___  

#### Fase 1: Onboarding por Áudio (5 min)
```
/start
```
Depois envie ÁUDIOS (não texto):
- 🎤 "Meu nome é [seu nome]"
- 🎤 "Eu moro no Rio de Janeiro"

#### Fase 2: Comandos por Áudio (10 min)
Envie tudo como ÁUDIO:
- 🎤 "Preciso comprar arroz, feijão, macarrão e óleo"
- 🎤 "Adiciona na lista leite, ovos e queijo"
- 🎤 "Coloca frango e carne moída na lista de compras"
- 🎤 "Me lembra de ligar pro dentista amanhã às dez da manhã"
- 🎤 "Tenho consulta médica na sexta-feira às três da tarde"
- 🎤 "Preciso pagar a conta de internet até dia quinze"

#### Fase 3: Áudios Longos (5 min)
Envie um áudio de ~30 segundos:
- 🎤 "Olha, essa semana tá bem corrida. Segunda eu tenho reunião às nove, terça preciso ir no banco pagar umas contas, quarta tenho dentista às duas da tarde, quinta é o aniversário do meu irmão então preciso comprar um presente, e sexta tenho que entregar aquele relatório do trabalho. Ah, e não posso esquecer de comprar remédio pra minha mãe."

#### Fase 4: Mistura Texto + Áudio (5 min)
```
mostra minha lista
```
- 🎤 "Adiciona sabonete e pasta de dente"
```
/hoje
```
- 🎤 "O que eu tenho pra fazer essa semana?"

#### Fase 5: Áudios em Sequência Rápida (5 min)
Envie 5 áudios seguidos SEM esperar resposta:
- 🎤 "Comprar pão"
- 🎤 "Levar o cachorro no veterinário"
- 🎤 "Ligar pra vó"
- 🎤 "Estudar inglês"
- 🎤 "Fazer exercício"

#### Fase 6: Pedidos de Áudio (5 min)
```
responde em áudio
```
- 🎤 "O que tenho na minha lista de compras?"
```
responde em áudio: quais são meus lembretes?
```

#### Fase 7: Consultas Finais (5 min)
```
/semana
/agenda
/list
```

#### Checklist de Problemas:
- [ ] Áudio não foi transcrito
- [ ] Transcrição incorreta
- [ ] Bot não entendeu o pedido
- [ ] Resposta em áudio não funcionou
- [ ] Demora na transcrição (>10 segundos)
- [ ] Áudio longo foi cortado/ignorado

---

## ROTEIRO 3 - BRASIL 🇧🇷
### Foco: Lembretes Recorrentes e Agenda

**Testador:** _____________  
**Telefone:** _____________  
**Início:** ___:___  

#### Fase 1: Setup (3 min)
```
/start
meu nome é [seu nome]
moro em Belo Horizonte
/tz America/Sao_Paulo
```

#### Fase 2: Lembretes Simples em Rajada (5 min)
```
me lembra de beber água em 5 minutos
lembrete: tomar vitamina em 10 minutos
me avisa pra fazer alongamento em 15 minutos
lembra de olhar emails em 20 minutos
me lembra de fazer pausa em 25 minutos
```

#### Fase 3: Lembretes com Data/Hora (10 min)
```
me lembra de pagar aluguel dia 5 às 9h
lembrete: renovar carteira de motorista dia 15 às 10h
consulta com dermatologista dia 20 às 14h30
reunião de condomínio dia 25 às 19h
aniversário da minha mãe dia 30
me lembra de comprar flores dia 30 às 8h
```

#### Fase 4: Lembretes Recorrentes (10 min)
```
me lembra de tomar remédio todo dia às 8h
lembrete diário: beber 2 litros de água
toda segunda às 7h: academia
toda sexta às 18h: happy hour
todo dia 1: pagar contas
a cada 2 horas: fazer pausa
```

#### Fase 5: Verificar Agenda (5 min)
```
/hoje
/semana
/mes
minha agenda
o que tenho amanhã?
lembretes pendentes
/recorrente
```

#### Fase 6: Modificar Lembretes (5 min)
```
cancela o lembrete de beber água
remove a academia de segunda
/stop
```
(Escolha um lembrete para parar)

#### Fase 7: Eventos Complexos (5 min)
```
viagem pra praia de 20 a 25 de abril
reunião de trabalho segunda, quarta e sexta às 10h
curso de inglês às terças e quintas às 19h
```

#### Fase 8: Consulta Final (2 min)
```
/agenda
/pendente
```

#### Checklist de Problemas:
- [ ] Lembrete não foi criado
- [ ] Horário errado no lembrete
- [ ] Recorrente não repetiu
- [ ] /stop não funcionou
- [ ] Agenda mostrou dados errados
- [ ] Timezone incorreto

---

## ROTEIRO 4 - PORTUGAL 🇵🇹
### Foco: Português Europeu e Fuso Horário

**Testador:** _____________  
**Telefone:** _____________  
**Início:** ___:___  

#### Fase 1: Onboarding PT-PT (5 min)
```
/start
chamo-me [seu nome]
moro em Lisboa
/tz Europe/Lisbon
/lang pt-PT
```

#### Fase 2: Comandos em Português Europeu (10 min)
```
põe na lista: arroz, massa, azeite, sal, açúcar
adiciona à lista: leite, ovos, queijo, fiambre, manteiga
coloca na lista: tomate, cebola, alho, batata, cenoura
mete na lista: frango, carne picada, chouriço, bacalhau
adiciona: café, sumo, água, cerveja, vinho
```

#### Fase 3: Lembretes em PT-PT (10 min)
```
lembra-me de telefonar ao médico amanhã às 9h
avisa-me para tomar o comprimido daqui a 2 horas
tenho consulta na segunda-feira às 14h30
reunião de trabalho na quarta às 10h
lembra-me de ir ao multibanco na sexta
preciso de pagar a renda até dia 8
```

#### Fase 4: Expressões Típicas PT-PT (5 min)
```
preciso de comprar pastéis de nata
adiciona bifanas à lista
mete uma francesinha na lista de comidas
lembra-me de ver o Benfica no domingo
```

#### Fase 5: Consultas em PT-PT (5 min)
```
mostra-me a lista
o que tenho para fazer?
qual é a minha agenda?
/hoje
/semana
```

#### Fase 6: Mistura PT-BR e PT-PT (5 min)
```
adiciona na lista: guaraná, açaí, tapioca
me lembra de ver o jogo
lembra-me de comprar pastéis
põe bacalhau na lista
```

#### Fase 7: Reset (5 min)
```
/nuke
```
(Confirme com `1`)
```
olá
chamo-me Teste
põe leite na lista
```

#### Checklist de Problemas:
- [ ] Não entendeu português europeu
- [ ] Respostas em PT-BR em vez de PT-PT
- [ ] Fuso horário de Lisboa incorreto
- [ ] Expressões PT-PT não reconhecidas
- [ ] Conjugações verbais confusas

---

## ROTEIRO 5 - PORTUGAL 🇵🇹
### Foco: Comandos Simultâneos e Stress Extremo

**Testador:** _____________  
**Telefone:** _____________  
**Início:** ___:___  

#### Fase 1: Setup Rápido (2 min)
```
/start
sou o [nome]
Lisboa
```

#### Fase 2: RAJADA EXTREMA - 20 mensagens em 60 segundos (3 min)
**ATENÇÃO:** Envie TODAS estas mensagens o mais rápido possível, sem esperar resposta:

```
arroz
feijão
massa
azeite
sal
açúcar
leite
ovos
queijo
manteiga
tomate
cebola
alho
batata
frango
carne
peixe
pão
café
água
```

#### Fase 3: Verificar se Tudo Entrou (2 min)
```
/list mercado
```
(Conte se tem 20 itens)

#### Fase 4: Comandos Conflitantes (5 min)
Envie em rajada:
```
adiciona leite
remove leite
adiciona leite
feito leite
adiciona leite
```

#### Fase 5: Múltiplas Listas Simultâneas (5 min)
Envie em rajada:
```
/list filmes add Matrix
/list livros add 1984
/list músicas add Imagine
/list séries add Friends
/list jogos add FIFA
/list filmes add Inception
/list livros add O Hobbit
/list músicas add Yesterday
```

#### Fase 6: Lembretes em Rajada (5 min)
```
lembra em 1 min: teste1
lembra em 1 min: teste2
lembra em 1 min: teste3
lembra em 1 min: teste4
lembra em 1 min: teste5
```
(Espere 1-2 minutos e veja se TODOS chegam)

#### Fase 7: Consultas Simultâneas (3 min)
Envie em rajada:
```
/list
/hoje
/semana
/agenda
minhas listas
meus lembretes
```

#### Fase 8: Caracteres Especiais e Emojis (5 min)
```
adiciona 🍎 maçã na lista
põe café ☕ na lista
lembra-me de 🎂 aniversário
adiciona item com "aspas" e 'apóstrofo'
põe na lista: café/chá, pão+manteiga, 50% desconto
```

#### Fase 9: Mensagens Muito Longas (5 min)
Envie uma mensagem com 50+ itens:
```
adiciona na lista: item1, item2, item3, item4, item5, item6, item7, item8, item9, item10, item11, item12, item13, item14, item15, item16, item17, item18, item19, item20, item21, item22, item23, item24, item25, item26, item27, item28, item29, item30, item31, item32, item33, item34, item35, item36, item37, item38, item39, item40, item41, item42, item43, item44, item45, item46, item47, item48, item49, item50
```

#### Fase 10: Verificação Final (2 min)
```
/list mercado
```
(Quantos itens tem?)

#### Checklist de Problemas:
- [ ] Mensagens perdidas na rajada
- [ ] Itens duplicados
- [ ] Lembretes não chegaram todos
- [ ] Sistema travou
- [ ] Timeout/demora excessiva
- [ ] Emojis/caracteres especiais quebraram

---

## ROTEIRO 6 - PORTUGAL 🇵🇹
### Foco: Uso Real do Dia-a-Dia (Simulação de 1 Semana)

**Testador:** _____________  
**Telefone:** _____________  
**Início:** ___:___  

#### Contexto
Simule que está a usar o bot durante uma semana normal. Cada "dia" dura 5 minutos.

#### SEGUNDA-FEIRA (5 min)
```
bom dia
o que tenho para hoje?
preciso comprar pão, leite e ovos
tenho reunião às 10h
me lembra de ligar pro cliente às 14h
```

#### TERÇA-FEIRA (5 min)
```
olá
minha agenda
adiciona na lista: detergente, sabão, esponja
consulta médica quinta às 15h
```

#### QUARTA-FEIRA (5 min)
```
oi
o que tenho amanhã?
feito pão
feito leite
preciso de comprar presente pro aniversário do João
aniversário do João sábado às 20h
```

#### QUINTA-FEIRA (5 min)
```
bom dia
meus lembretes de hoje
feito detergente
adiciona vinho tinto pra levar no sábado
como faço lasanha?
```
(Teste de receita)

#### SEXTA-FEIRA (5 min)
```
última verificação antes do fim de semana
/semana
minhas listas
o que falta comprar?
me lembra de acordar cedo amanhã às 8h
```

#### SÁBADO (5 min)
```
bom dia
o que tenho hoje?
feito presente
feito vinho
fui ao aniversário do João, foi ótimo
```

#### DOMINGO (5 min)
```
olá
próxima semana
preciso de organizar a semana
segunda: reunião 9h, almoço com cliente 12h
terça: dentista 10h
quarta: home office
quinta: apresentação importante 14h
sexta: happy hour 18h
```

#### Verificação Final (5 min)
```
/agenda
/list
/stats
como foi minha semana?
```

#### Checklist de Problemas:
- [ ] Bot não lembrou contexto anterior
- [ ] Respostas não faziam sentido
- [ ] Comandos naturais não funcionaram
- [ ] Receita não apareceu
- [ ] Agenda ficou confusa
- [ ] Experiência não foi fluida

---

## FORMULÁRIO DE FEEDBACK

**Nome do Testador:** _____________  
**Roteiro:** _____________  
**Data/Hora:** _____________  
**País:** 🇧🇷 Brasil / 🇵🇹 Portugal

### Avaliação Geral (1-5)
- [ ] 1 - Péssimo, não funciona
- [ ] 2 - Ruim, muitos problemas
- [ ] 3 - Médio, funciona mas com falhas
- [ ] 4 - Bom, poucas falhas
- [ ] 5 - Excelente, tudo funcionou

### Problemas Encontrados
1. _____________________________________________
2. _____________________________________________
3. _____________________________________________
4. _____________________________________________
5. _____________________________________________

### O que funcionou bem?
_____________________________________________

### O que poderia melhorar?
_____________________________________________

### Usaria no dia-a-dia?
- [ ] Sim, com certeza
- [ ] Talvez, se melhorar X
- [ ] Não

### Prints/Screenshots
(Anexar no grupo de testadores)

---

## PARA O ADMINISTRADOR

### Checklist Pré-Teste
- [ ] VPS atualizado (`sudo bash scripts/update_vps.sh`)
- [ ] Redis funcionando (`docker compose ps`)
- [ ] Logs limpos (`docker compose logs --tail=0 -f gateway`)
- [ ] Backup feito (`sudo bash scripts/backup_zapista.sh`)
- [ ] Horário combinado com todos os testadores
- [ ] Grupo de feedback criado

### Durante o Teste
- Monitorar logs em tempo real:
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f gateway
  ```
- Verificar uso de recursos:
  ```bash
  docker stats
  ```

### Após o Teste
- [ ] Coletar feedback de todos
- [ ] Exportar logs do período
- [ ] Analisar erros
- [ ] Documentar bugs encontrados
