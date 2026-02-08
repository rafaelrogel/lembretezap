# Testadores: allow-list e instruções

## 1. Adicionar números à allow-list no VPS

Para permitir que estes números enviem mensagens ao bot:

- **351910070509**
- **351915485840**
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
  "allow_from": ["351910070509", "351915485840", "557187811002", "557196611125", "557199686684"]
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
