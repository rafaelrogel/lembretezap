# Fluxos de onboarding e uso — exemplos

Exemplos de caminhos possíveis com o onboarding simplificado (fuso primeiro, sem bloquear o sistema).

---

## Símbolos

- **U** = utilizador
- **B** = bot
- `[session]` = estado na sessão (metadata)
- `[db]` = estado na base de dados

---

## Fluxo 1: Primeira mensagem → responde com cidade → fim

```
[db: user novo, sem timezone]
[session: vazio]

U: (abre conversa, primeira mensagem)

B: Olá! Sou a tua assistente de organização — listas, lembretes e agenda. 📋

     Para enviar os lembretes na hora certa, preciso saber onde estás. Em que cidade vives? (Ou diz-me que horas são aí agora.)

[session: onboarding_intro_sent=True, pending_timezone=True]

---

U: Lisboa

B: Tudo certo! ✨ Já podes pedir lembretes, listas e eventos...
    💡 Quando receberes um lembrete, reage à mensagem...
    /reset para refazer o cadastro quando quiseres.

[db: city=Lisboa, timezone=Europe/Lisbon]
[session: pending_timezone removido]
```

**Caminho:** primeira mensagem → pergunta única → resposta = cidade → timezone definido por cidade → onboarding concluído.

---

## Fluxo 2: Primeira mensagem → responde com hora → confirma → fim

```
[db: user novo]
[session: intro_sent, pending_timezone]

U: (já viu intro + pergunta cidade/hora)

U: São 14h30

B: Ah, 08/02, 14:30. Confere?

[session: pending_time_confirm=True, proposed_tz_iana=Etc/GMT-1 (ou similar), proposed_date_str, proposed_time_str]

---

U: Sim

B: Fuso definido. Podes mudar quando quiseres com /tz ou /fuso.

     Tudo certo! ✨ Já podes pedir lembretes...

[db: timezone=Etc/GMT-1]
[session: pending_time_confirm e proposed_* removidos]
```

**Caminho:** pergunta cidade/hora → resposta = hora → bot pede confirmação (data + hora) → utilizador confirma → fuso guardado.

---

## Fluxo 3: Responde com hora → não confirma (bot atribui na mesma)

```
[session: pending_time_confirm=True, proposed_tz_iana=Etc/GMT-2]

U: (ignora ou manda outra coisa)
U: lembrete comprar leite

B: Fuso definido. Podes mudar quando quiseres com /tz ou /fuso.

     Tudo certo! ✨ Já podes pedir lembretes...

[db: timezone atribuído com proposed_tz_iana]
```

**Caminho:** em estado de confirmação, qualquer resposta (ou não confirmar) → bot **atribui o fuso na mesma** e segue. Depois o utilizador pode usar /tz ou /fuso para corrigir.

---

## Fluxo 4: Responde com hora → diz «não» / «errado» → pergunta de novo

```
[session: pending_time_confirm=True, proposed_tz_iana=Etc/GMT-2]

U: Não, está errado

B: Que horas são aí agora? (Assim acerto o fuso dos teus lembretes.)

[session: pending_time_confirm removido, pending_timezone=True, proposed_* removidos]

---

U: 15h00

B: Ah, 08/02, 15:00. Confere?

[session: pending_time_confirm=True, novo proposed_tz_iana]
```

**Caminho:** confirmação → utilizador corrige → bot pergunta de novo a hora → novo ciclo de confirmação.

---

## Fluxo 5: Não responde à pergunta — usa comando (não bloqueia)

```
[session: intro_sent, pending_timezone=True]

U: /help

B: (resposta normal do /help — lista de comandos)

[session: pending_timezone continua True — próxima mensagem não-comando ainda será interpretada como cidade/hora]
```

**Caminho:** utilizador manda comando → **não bloqueia**; handlers respondem. Estado «pending_timezone» mantém-se para a próxima mensagem “livre”.

---

## Fluxo 6: Não responde com cidade nem hora — fallthrough + nudge

```
[session: intro_sent, pending_timezone=True]

U: Lembrete amanhã às 10h comprar pão

B: (handler processa: cria lembrete)
    Lembrete agendado (id: XY). ...

    Quando puderes, diz a tua cidade ou que horas são aí para os lembretes chegarem na hora. 😊

[session: pending_timezone removido, onboarding_nudge_count=1, nudge_append_done=True]
```

**Caminho:** mensagem não é cidade nem hora → **não bloqueia**; segue para handlers; resposta inclui **nudge** (só 1x por sessão). Contador de “ignorar” incrementado para retry depois.

---

## Fluxo 7: Retry gradual — após 2 “ignores”, pergunta a hora

```
[session: intro_sent, pending_timezone=False, onboarding_nudge_count=1]

U: /hoje

B: (resposta de /hoje, sem nudge pois nudge_append_done já True)

---

[session: onboarding_nudge_count=1 — ainda não 2]

U: lista compras add leite

B: (handler: adiciona à lista, responde)

---

[session: intro_sent, pending_timezone=False, onboarding_nudge_count=2]

U: ok

B: Que horas são aí agora? (Assim acerto o fuso dos teus lembretes.)

[session: pending_timezone=True, onboarding_nudge_count=0]
```

**Caminho:** após **2 mensagens** em que não se respondeu à pergunta de fuso (fallthrough), na **próxima** mensagem o bot pergunta de novo só a hora («Que horas são aí?»).

---

## Fluxo 8: Já tem fuso (onboarding concluído ou /tz) — zero bloqueio

```
[db: user.timezone=Europe/Lisbon]

U: (qualquer mensagem)

B: (nunca entra no bloco de onboarding; segue direto para handlers ou LLM)
```

**Caminho:** com timezone já definido (por onboarding ou /tz), o bloco de onboarding é **sempre ignorado**; toda a mensagem segue para o fluxo normal.

---

## Fluxo 9: /reset → volta a perguntar fuso na próxima mensagem

```
[db: tinha city + timezone]
[session: tinha vários flags]

U: /reset

B: Cadastro apagado. Na próxima mensagem, pergunto de novo onde estás (cidade ou hora) para acertar o fuso. /tz ou /fuso para mudar depois. LGPD: só o essencial. 😊

[db: clear_onboarding_data — city/timezone limpos]
[session: pending_timezone, pending_time_confirm, proposed_*, onboarding_nudge_count, nudge_append_done, etc. removidos]

---

U: (próxima mensagem)

B: Olá! Sou a tua assistente... Para enviar os lembretes na hora certa... Em que cidade vives? (Ou diz-me que horas são aí agora.)
```

**Caminho:** /reset limpa dados e flags → próxima mensagem é tratada como “primeira” de novo (intro + pergunta cidade/hora).

---

## Resumo dos caminhos

| Situação | Comportamento |
|----------|----------------|
| Primeira mensagem | Intro + pergunta única (cidade ou hora). |
| Resposta = cidade | Extrai cidade + IANA → guarda → mensagem de conclusão. |
| Resposta = hora | Calcula offset → «Ah, data, hora. Confere?» → confirmar ou atribuir na mesma. |
| Resposta = «não» na confirmação | Limpa proposta → pergunta de novo «Que horas são aí?». |
| Resposta ≠ cidade nem hora | Fallthrough para handlers; incrementa contador; nudge na 1ª resposta. |
| Comando (/help, /lembrete, etc.) | Não bloqueia; handlers respondem. |
| Após 2 fallthroughs | Próxima mensagem → «Que horas são aí agora?». |
| Já tem timezone | Onboarding nunca bloqueia; tudo vai para handlers/LLM. |
| /reset | Limpa dados e sessão; próxima mensagem = novo “início”. |

---

## Diagrama simplificado

```
                    [Primeira mensagem]
                            │
                            ▼
              ┌─────────────────────────────┐
              │  Intro + «Cidade ou hora?»  │
              │  pending_timezone = True     │
              └──────────────┬──────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    [Resposta]          [Comando]          [Outro texto]
    cidade/hora         /help, etc.       lembrete, etc.
         │                   │                   │
         ▼                   ▼                   ▼
  Parse cidade?         Handlers            Parse cidade?
  Parse hora?           (não bloqueia)     Parse hora?
       │                                          │
   Sim │ Não                                  Sim │ Não
       │  │                                        │  │
       ▼  ▼                                        ▼  ▼
  [Cidade] → set tz                          [Hora] → «Confere?»
  [Hora]  → «Confere?»                            │
       │                                          │
       ▼                                          ▼
  [Concluído]                          [Confirmou?] → set tz
                                       [Não?]      → pergunta hora de novo
                                       [Ignorou]   → set tz na mesma
                                                         │
                                              [Não parse] → fallthrough
                                                         │
                                                         ▼
                                              Handlers + nudge (1x)
                                              nudge_count += 1
                                                         │
                                              nudge_count >= 2?
                                                         │ Sim
                                                         ▼
                                              «Que horas são aí?»
                                              pending_timezone = True
```

Estes exemplos cobrem os principais caminhos e possibilidades do onboarding e do uso do sistema.
