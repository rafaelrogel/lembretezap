# Testadores: allow-list e instruções

## 1. Adicionar números à allow-list no VPS

Para permitir que estes números enviem mensagens ao bot:

- **351910070509**
- **351912540117**
- **557187811002**
- **557196611125**
- **557199686684**

### No servidor (SSH)

Conecta ao VPS e edita o `config.json` dos dados:

```bash
cd /opt/zapassist
sudo nano data/config.json
```

Na secção `channels` → `whatsapp`, altera `allow_from` para (podes juntar outros números na mesma lista):

```json
"whatsapp": {
  "enabled": true,
  "bridge_url": "ws://bridge:3001",
  "allow_from": ["351910070509", "351912540117", "557187811002", "557196611125", "557199686684"]
}
```

Guarda com **Ctrl+O**, Enter, e sai com **Ctrl+X**.

Reinicia o gateway para carregar a nova config:

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml restart gateway
```

(Se instalaste sem o ficheiro VPS, usa só:  
`sudo docker compose restart gateway`.)

---

## 2. Iterações básicas que os testadores devem fazer

Cada tester pode testar o seguinte (tudo em **chat privado** com o número do bot; grupos não são suportados):

| O quê | Exemplo de mensagem |
|-------|----------------------|
| Lembrete daqui a X min | `Lembra-me de beber água daqui a 2 minutos` ou `/lembrete beber água daqui a 5 min` |
| Lembrete diário | `/lembrete todo dia às 9h tomar remédio` |
| Lista – adicionar | `/list mercado add leite` ou `/list pendentes add pagar contas` |
| Lista – ver | `/list mercado` ou `/list` (lista todas) |
| Marcar feito | `/feito mercado 1` (remove o item 1 da lista mercado) |
| Anotar filme | `/filme Matrix` ou `/filme O Senhor dos Anéis` |
| Mensagem livre (organizador) | *"Adiciona comprar pão à lista compras"* — o bot tenta interpretar |

Sugestão: cada tester faz pelo menos **um lembrete**, **uma lista** (add + list + feito) e **um filme**.

---

## 2.1 Se um tester não receber resposta

1. **Confirmar allow_from:** O número dele deve estar em `allow_from` no `config.json`, com **código do país** e **sem espaços nem +** (ex.: `351912540117`, `557187811002`).
2. **Ver os logs do gateway:** No VPS, `docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f gateway`. Quando esse tester envia uma mensagem, deve aparecer uma linha do tipo:
   - `WhatsApp from sender='...' → sender_id='...'` — o **sender_id** é o que é comparado com a allow_list.
   - Se aparecer **"Access denied for sender XXX"**, adiciona esse **XXX** exatamente ao `allow_from` no `config.json` (pode ser um LID em vez de número) e reinicia o gateway: `docker compose restart gateway`.
3. **Só dígitos:** Podes escrever o número no config com espaços ou traços (ex.: `351 915 485 840`); o sistema compara só os dígitos. Mas o ideal é um número limpo: `351912540117`.

---

## 2.2 "Muitas mensagens. Aguarde um minuto antes de enviar de novo."

Por defeito cada utilizador pode enviar **15 mensagens por minuto**. Se os testadores (ou tu) enviarem muitas mensagens seguidas, o bot responde com isso.

Para **aumentar o limite** (ex.: 60 por minuto) durante os testes:

1. No servidor, no `.env` da pasta do projeto (ex.: `/opt/zapassist/.env`), adiciona:
   ```bash
   RATE_LIMIT_MAX_PER_MINUTE=60
   ```
2. Reinicia o gateway:
   ```bash
   sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml restart gateway
   ```
O valor pode ser entre 5 e 300. Em produção podes voltar a 15 ou 20.

---

## 3. Mensagem para enviar aos testadores (Zap)

Copia o texto abaixo e envia no WhatsApp aos testadores.

---

**Mensagem para enviar:**

```
Olá! 👋

Estamos a testar o ZapAssist, um bot de organização por WhatsApp (lembretes, listas, filmes). O teu número já está na lista de teste.

Por favor testa em CHAT PRIVADO com este número (não em grupos). Podes fazer:

• Lembrete: "Lembra-me de beber água daqui a 2 minutos" ou /lembrete beber água em 5 min
• Lembrete diário: /lembrete todo dia às 9h tomar remédio
• Lista: /list mercado add leite → depois /list mercado → e /feito mercado 1 (quando fizeres o 1)
• Filme: /filme Matrix

Resumo de comandos:
/lembrete [texto] daqui a X min
/list [nome] add [item]
/list [nome]  ou  /list
/feito [lista] [número do item]
/filme [nome]

Qualquer dúvida ou bug, avisa. Obrigado! 🙏
```

---

Se quiseres, podes encurtar a mensagem ou adaptar o tom (mais formal/informal).
