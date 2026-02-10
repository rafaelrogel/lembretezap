"""Agent loop: the core processing engine."""

import asyncio
import json
import random
import time
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.utils.logging_config import set_trace_id, reset_trace_id
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.context import ContextBuilder
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.list_tool import ListTool
from nanobot.agent.tools.event_tool import EventTool
from nanobot.session.manager import SessionManager
from nanobot.utils.circuit_breaker import CircuitBreaker

# Evitar enviar "Muitas mensagens" várias vezes ao mesmo chat (1x por minuto)
_RATE_LIMIT_MSG_SENT: dict[tuple[str, str], float] = {}
_RATE_LIMIT_MSG_COOLDOWN = 60.0


def _should_send_rate_limit_message(channel: str, chat_id: str) -> bool:
    """True se podemos enviar a mensagem de rate limit (não enviamos nos últimos 60s para este chat)."""
    now = time.time()
    key = (channel, str(chat_id))
    to_del = [k for k, t in _RATE_LIMIT_MSG_SENT.items() if now - t > _RATE_LIMIT_MSG_COOLDOWN]
    for k in to_del:
        del _RATE_LIMIT_MSG_SENT[k]
    if key in _RATE_LIMIT_MSG_SENT:
        return False
    _RATE_LIMIT_MSG_SENT[key] = now
    return True


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        scope_model: str | None = None,
        scope_provider: "LLMProvider | None" = None,
        max_iterations: int = 20,
        cron_service: "CronService | None" = None,
    ):
        from nanobot.cron.service import CronService
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.scope_model = scope_model or self.model
        self.scope_provider = scope_provider  # quando setado, scope filter e heartbeat usam este (ex.: Xiaomi)
        self.max_iterations = max_iterations
        self.cron_service = cron_service
        
        self.context = ContextBuilder(workspace)
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=60.0)

        self._running = False
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        try:
            from backend.database import init_db
            init_db()
        except Exception:
            pass
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Cron tool (for scheduling; MIMO opcional para sugerir ID quando fora da lista de palavras)
        if self.cron_service:
            self.tools.register(CronTool(
                self.cron_service,
                scope_provider=self.scope_provider,
                scope_model=self.scope_model or "",
            ))
        # List and event tools (per-user DB)
        self.tools.register(ListTool())
        self.tools.register(EventTool())
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    def _set_tool_context(self, channel: str, chat_id: str) -> None:
        """Define canal/chat em todas as tools que suportam (parser e LLM usam o mesmo contexto)."""
        for name, tool in (("message", MessageTool), ("cron", CronTool), ("list", ListTool), ("event", EventTool)):
            t = self.tools.get(name)
            if t and isinstance(t, tool):
                t.set_context(channel, chat_id)

    async def _execute_parsed_intent(self, intent: dict, msg: InboundMessage) -> str | None:
        """Executa intent do parser (cron, list, event). Retorna texto da resposta ou None para seguir ao LLM."""
        from backend.guardrails import is_absurd_request

        cron_tool = self.tools.get("cron")
        list_tool = self.tools.get("list")
        event_tool = self.tools.get("event")

        t = intent.get("type")
        if t == "lembrete":
            absurd = is_absurd_request(msg.content)
            if absurd:
                return absurd
            if not self.cron_service or not cron_tool:
                return None
            msg_text = intent.get("message", "").strip()
            if not msg_text:
                return None
            in_sec = intent.get("in_seconds")
            every_sec = intent.get("every_seconds")
            cron_expr = intent.get("cron_expr")
            if in_sec or every_sec or cron_expr:
                return await cron_tool.execute(
                    action="add",
                    message=msg_text,
                    in_seconds=in_sec,
                    every_seconds=every_sec,
                    cron_expr=cron_expr,
                )
            return None  # tempo não parseado, deixar para o LLM
        if t == "list_add":
            if not list_tool:
                return None
            list_name = intent.get("list_name", "")
            item_text = intent.get("item", "")
            if list_name in ("filme", "livro", "musica", "receita") and is_absurd_request(item_text):
                return is_absurd_request(item_text)
            return await list_tool.execute(
                action="add",
                list_name=list_name,
                item_text=item_text,
            )
        if t == "list_show":
            if not list_tool:
                return None
            list_name = intent.get("list_name")
            return await list_tool.execute(action="list", list_name=list_name or "")
        if t == "feito":
            if not list_tool:
                return None
            list_name = intent.get("list_name")
            item_id = intent.get("item_id")
            if list_name is None:
                return "Use: /feito nome_da_lista id (ex: /feito mercado 1)"
            return await list_tool.execute(action="feito", list_name=list_name, item_id=item_id)
        return None

    async def _out_of_scope_message(self, user_content: str, lang: str = "en") -> str:
        """Resposta natural e amigável quando o pedido está fora do escopo (Xiaomi ou fallback). Explica o que o bot faz, sugere acção e CTA."""
        from backend.locale import OUT_OF_SCOPE_FALLBACKS
        fallbacks = OUT_OF_SCOPE_FALLBACKS.get(lang if lang in OUT_OF_SCOPE_FALLBACKS else "en", OUT_OF_SCOPE_FALLBACKS["en"])
        lang_instruction = {
            "pt-PT": "em português de Portugal",
            "pt-BR": "em português do Brasil",
            "es": "en español",
            "en": "in English",
        }.get(lang, "in English")
        if self.scope_provider and self.scope_model:
            try:
                prompt = (
                    "You are a friendly organization assistant. The user said something that is OUT OF YOUR SCOPE: «"
                    + (user_content[:200] if user_content else "")
                    + "». Reply in 2-4 short sentences, natural and warm (not robotic). "
                    "1) Politely say you can't help with that. "
                    "2) Briefly say what you CAN do: reminders, lists, and noting films/books/music they want to see. "
                    "3) Tell them they can use /help to see all commands, OR simply chat with you — you are their personal AI assistant. Do NOT list specific commands like /lembrete or /list. "
                    "Use 1-2 emojis. Reply ONLY with the message text, "
                    + lang_instruction + ". No preamble."
                )
                r = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.scope_model,
                    max_tokens=180,
                    temperature=0.7,
                )
                out = (r.content or "").strip()
                if out and len(out) <= 500:
                    return out
            except Exception as e:
                logger.debug(f"Out-of-scope message (Xiaomi) failed: {e}")
        return random.choice(fallbacks)

    async def _get_onboarding_intro(self, user_lang: str) -> str:
        """Mensagem de apresentação na primeira interação: quem somos, o que fazemos, engajadora (DeepSeek)."""
        lang_instruction = {
            "pt-PT": "em português de Portugal",
            "pt-BR": "em português do Brasil",
            "es": "en español",
            "en": "in English",
        }.get(user_lang, "in the user's language")
        prompt = (
            "You are an AI assistant for personal organization. The user is seeing you for the FIRST time. "
            "Write a single welcome message (2-4 short paragraphs) that:\n"
            "1) Introduces yourself as their AI for organization — friendly and warm, not robotic.\n"
            "2) Explains clearly what you can do. Use this structure (do NOT mix the two):\n"
            "   - LISTS: shopping, to-do, recipes, ingredients, books, films, music, sites to visit — things to note and look up later.\n"
            "   - EVENTS: appointments, consultations, meetings, special dates, commitments — things with a date/time to remember.\n"
            "   You can also set reminders and search for ingredient lists online. 'The sky is the limit' within organization and reminders.\n"
            "   IMPORTANT: Do NOT put recipes, books or films under 'events' or 'eventos'; they belong in LISTS.\n"
            "3) Makes the user feel excited and eager to try you. Be concise and scannable (short sentences, no wall of text).\n"
            "4) End by asking how they would like to be called (first name or nickname).\n"
            f"Use 1-2 emojis. Reply ONLY with the message, {lang_instruction}. No preamble, no quotes."
        )
        try:
            r = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=420,
                temperature=0.6,
            )
            out = (r.content or "").strip().strip('"\'')
            if out and len(out) <= 800:
                return out
        except Exception as e:
            logger.debug(f"Onboarding intro (DeepSeek) failed: {e}")
        fallbacks = {
            "pt-PT": (
                "Olá! Sou a tua assistente de organização. 📋\n\n"
                "Posso criar listas (compras, tarefas, receitas, ingredientes), definir lembretes, "
                "registar consultas e compromissos, datas especiais, reuniões — e até pesquisar listas de ingredientes na Internet. "
                "Livros, filmes, sites a visitar: tudo o que precisares para não esquecer nada.\n\n"
                "Como gostarias de ser chamado? 😊"
            ),
            "pt-BR": (
                "Oi! Sou sua assistente de organização. 📋\n\n"
                "Posso criar listas (compras, tarefas, receitas, ingredientes), definir lembretes, "
                "registrar consultas e compromissos, datas especiais, reuniões — e até pesquisar listas de ingredientes na internet. "
                "Livros, filmes, sites para visitar: tudo que você precisar para não esquecer nada.\n\n"
                "Como você gostaria de ser chamado? 😊"
            ),
            "es": (
                "¡Hola! Soy tu asistente de organización. 📋\n\n"
                "Puedo crear listas (compras, tareas, recetas, ingredientes), definir recordatorios, "
                "registrar consultas y compromisos, fechas especiales, reuniones — y hasta buscar listas de ingredientes en internet. "
                "Libros, películas, sitios para visitar: todo lo que necesites para no olvidar nada.\n\n"
                "¿Cómo te gustaría que te llamara? 😊"
            ),
            "en": (
                "Hi! I'm your organization assistant. 📋\n\n"
                "I can create lists (shopping, to-do, recipes, ingredients), set reminders, "
                "register appointments and commitments, special dates, meetings — and even search for ingredient lists online. "
                "Books, films, sites to visit: whatever you need so nothing slips through the cracks.\n\n"
                "How would you like to be called? 😊"
            ),
        }
        return fallbacks.get(user_lang, fallbacks["en"])

    async def _ask_preferred_name_question(self, user_lang: str) -> str:
        """Pergunta amigável «como gostaria de ser chamado» no idioma do utilizador (Xiaomi ou fallback)."""
        from backend.locale import PREFERRED_NAME_QUESTION, LangCode, SUPPORTED_LANGS
        lang_instruction = {
            "pt-PT": "em português de Portugal",
            "pt-BR": "em português do Brasil",
            "es": "en español",
            "en": "in English",
        }.get(user_lang, "in English")
        if self.scope_provider and self.scope_model:
            try:
                prompt = (
                    "You are a friendly assistant. Ask the user in ONE short sentence how they would like to be called. "
                    f"Reply only with that question, {lang_instruction}. No other text."
                )
                r = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.scope_model,
                    max_tokens=80,
                    temperature=0.3,
                )
                out = (r.content or "").strip()
                if out and len(out) <= 200:
                    return out
            except Exception as e:
                logger.debug(f"Ask preferred name (Xiaomi) failed: {e}")
        lang = user_lang if user_lang in SUPPORTED_LANGS else "en"
        return PREFERRED_NAME_QUESTION.get(lang, PREFERRED_NAME_QUESTION["en"])

    async def _extract_city_and_timezone_with_mimo(self, user_content: str) -> tuple[str | None, str | None]:
        """Usa Mimo para extrair cidade da mensagem do utilizador e obter IANA timezone. Retorna (city_name, tz_iana)."""
        if not user_content or not user_content.strip():
            return None, None
        city_name = None
        tz_iana = None
        # 1) Mimo: extrair nome da cidade (uma só, forma normalizada)
        if self.scope_provider and self.scope_model:
            try:
                prompt1 = (
                    "The user was asked which city they are in. They replied: «" + (user_content[:200] or "") + "». "
                    "Extract the city name (one city only). Use standard English name (e.g. Lisbon, São Paulo, London, Tokyo). "
                    "If they mention a country/region without a city, use the capital. Reply with ONLY the city name, nothing else."
                )
                r1 = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt1}],
                    model=self.scope_model,
                    max_tokens=60,
                    temperature=0,
                )
                raw = (r1.content or "").strip()
                if raw:
                    city_name = raw.split("\n")[0].strip()[:128]
            except Exception as e:
                logger.debug(f"Mimo extract city failed: {e}")
        if not city_name:
            city_name = (user_content or "").strip()[:128]
        if not city_name:
            return None, None
        # 2) Tentar lista local
        from backend.timezone import city_to_iana, is_valid_iana
        key = city_name.lower().replace("-", " ").replace("_", " ")
        tz_iana = city_to_iana(key) or city_to_iana(city_name)
        # 3) Se não está na lista, pedir IANA ao Mimo
        if (not tz_iana or not is_valid_iana(tz_iana)) and self.scope_provider and self.scope_model:
            try:
                prompt2 = (
                    "What is the IANA timezone for the city «" + city_name + "»? "
                    "Reply with ONLY the IANA timezone identifier, e.g. Europe/Lisbon or America/Sao_Paulo or Asia/Tokyo. One line only."
                )
                r2 = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt2}],
                    model=self.scope_model,
                    max_tokens=40,
                    temperature=0,
                )
                raw_tz = (r2.content or "").strip().split("\n")[0].strip()
                if raw_tz and is_valid_iana(raw_tz):
                    tz_iana = raw_tz
            except Exception as e:
                logger.debug(f"Mimo timezone for city failed: {e}")
        return city_name, tz_iana if (tz_iana and is_valid_iana(tz_iana)) else None

    def _is_calling_organizer(self, content: str) -> bool:
        """True se a mensagem parece ser só uma 'chamada' ao bot (organizador?, cadê você?), sem pedido concreto."""
        if not content or not content.strip():
            return False
        text = content.strip()
        # Só mensagens curtas: evita que "Organizador, você consegue lembrar de tudo..." vire só "Estou aqui!"
        if len(text) > 50:
            return False
        if text.startswith("/"):
            return False
        lower = text.lower()
        keywords = (
            "organizador", "organizadora", "robô", "robot", "secretária", "secretario",
            "cadê você", "cadê tu", "onde você", "tá aí", "está aí", "estou aqui?",
            "assistente", "oi organizador", "olá organizador", "e aí organizador",
        )
        return any(k in lower for k in keywords)

    async def _reply_calling_organizer_with_mimo(self) -> str:
        """Resposta curta e proativa ao ser 'chamado' (Mimo, barato). Uma só frase, à postos."""
        if not self.scope_provider or not self.scope_model:
            return "Estou aqui! Em que posso ajudar?"
        try:
            prompt = (
                "The user just called the assistant (e.g. 'Organizador?', 'Cadê você?'). "
                "Reply with ONE very short, friendly, proactive phrase in Portuguese (Brazil) showing you're here and ready to help. "
                "Examples: Estou aqui!, Opa!, Chamou?, À postos!, Estou aqui, em que posso ajudar? "
                "Output ONLY that phrase, nothing else. No quotes."
            )
            r = await self.scope_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.scope_model,
                max_tokens=40,
                temperature=0.3,
            )
            out = (r.content or "").strip().strip('"\'')
            if out and len(out) <= 120:
                return out
        except Exception as e:
            logger.debug(f"Mimo reply calling organizer failed: {e}")
        return "Estou aqui! Em que posso ajudar?"

    async def _ask_city_question(self, user_lang: str, name: str) -> str:
        """Pergunta natural (DeepSeek) em que cidade está (para fuso horário). Aceita qualquer cidade do mundo."""
        lang_instruction = {
            "pt-PT": "em português de Portugal",
            "pt-BR": "em português do Brasil",
            "es": "en español",
            "en": "in English",
        }.get(user_lang, "in the user's language")
        prompt = (
            f"The user is {name}. We are onboarding: we need to ask which city they are in (to set their timezone for reminders). "
            "Accept any city in the world. Write ONE short, friendly question. Use 1 emoji (e.g. 🌍). "
            "Reply only with the question, no preamble. " + lang_instruction + "."
        )
        try:
            r = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=100,
                temperature=0.5,
            )
            out = (r.content or "").strip()
            if out and len(out) <= 220:
                return out
        except Exception as e:
            logger.debug(f"Ask city (DeepSeek) failed: {e}")
        fallbacks = {
            "pt-PT": "Em que cidade estás? (para acertarmos o fuso dos lembretes) 🌍",
            "pt-BR": "Em que cidade você está? (para acertarmos o fuso dos lembretes) 🌍",
            "es": "¿En qué ciudad estás? (para ajustar el huso de los recordatorios) 🌍",
            "en": "Which city are you in? (so we can set the right timezone for reminders) 🌍",
        }
        return fallbacks.get(user_lang, fallbacks["en"])

    async def _ask_lead_time_question(self, user_lang: str, name: str) -> str:
        """Pergunta natural (DeepSeek) quanto tempo antes do evento deseja o primeiro aviso."""
        lang_instruction = {
            "pt-PT": "em português de Portugal",
            "pt-BR": "em português do Brasil",
            "es": "en español",
            "en": "in English",
        }.get(user_lang, "in the user's language")
        prompt = (
            f"The user is {name}. We are onboarding: we need to ask how much time BEFORE an event they want "
            "the first reminder (e.g. 1 day before, 2 hours before, 30 min before). "
            "Write ONE short, friendly question. Give examples like 1 dia, 2 horas, 30 min. "
            "Use 1-2 emojis (e.g. ⏰ 📋). Reply only with the question, no preamble. "
            f"{lang_instruction}."
        )
        try:
            r = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=120,
                temperature=0.5,
            )
            out = (r.content or "").strip()
            if out and len(out) <= 250:
                return out
        except Exception as e:
            logger.debug(f"Ask lead time (DeepSeek) failed: {e}")
        fallbacks = {
            "pt-PT": "Quanto tempo antes do evento queres o primeiro aviso? (ex.: 1 dia, 2 horas, 30 min) ⏰",
            "pt-BR": "Quanto tempo antes do evento você quer o primeiro aviso? (ex.: 1 dia, 2 horas, 30 min) ⏰",
            "es": "¿Cuánto tiempo antes del evento quieres el primer aviso? (ej.: 1 día, 2 horas, 30 min) ⏰",
            "en": "How long before the event do you want the first reminder? (e.g. 1 day, 2 hours, 30 min) ⏰",
        }
        return fallbacks.get(user_lang, fallbacks["en"])

    async def _ask_extra_leads_question(self, user_lang: str, name: str) -> str:
        """Pergunta natural (DeepSeek) se quer mais avisos antes (até 3)."""
        lang_instruction = {
            "pt-PT": "em português de Portugal",
            "pt-BR": "em português do Brasil",
            "es": "en español",
            "en": "in English",
        }.get(user_lang, "in the user's language")
        prompt = (
            f"The user is {name}. We already set the first reminder (X before event). Now ask if they want "
            "UP TO 3 MORE reminders before the event (same idea: e.g. 3 days before, 1 day before, 30 min before). "
            "Say they can say 'no' if they don't want any. One short, friendly sentence with 1 emoji. "
            f"Reply only with the question. {lang_instruction}."
        )
        try:
            r = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=120,
                temperature=0.5,
            )
            out = (r.content or "").strip()
            if out and len(out) <= 250:
                return out
        except Exception as e:
            logger.debug(f"Ask extra leads (DeepSeek) failed: {e}")
        fallbacks = {
            "pt-PT": "Queres mais algum aviso antes? (até 3, ex.: 3 dias, 1 dia, 30 min — ou diz «não») 📌",
            "pt-BR": "Quer mais algum aviso antes? (até 3, ex.: 3 dias, 1 dia, 30 min — ou diga «não») 📌",
            "es": "¿Quieres más avisos antes? (hasta 3, ej.: 3 días, 1 día, 30 min — o di «no») 📌",
            "en": "Want more reminders before? (up to 3, e.g. 3 days, 1 day, 30 min — or say no) 📌",
        }
        return fallbacks.get(user_lang, fallbacks["en"])

    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.
        Parser-first: structured commands (/lembrete, /list, /feito, /filme) are
        executed directly without LLM; only natural language or ambiguous cases use the LLM.
        """
        trace_id = msg.trace_id or uuid.uuid4().hex[:12]
        token = set_trace_id(trace_id)
        try:
            return await self._process_message_impl(msg)
        finally:
            reset_trace_id(token)

    async def _process_message_impl(self, msg: InboundMessage) -> OutboundMessage | None:
        """Implementation of message processing (rate limit → parser → scope filter → LLM)."""
        # Sanitize input (evita injeção e payloads excessivos)
        from backend.sanitize import sanitize_string, MAX_MESSAGE_LEN
        content = sanitize_string(msg.content, MAX_MESSAGE_LEN)
        msg = InboundMessage(
            channel=msg.channel,
            sender_id=msg.sender_id,
            chat_id=msg.chat_id,
            content=content,
            timestamp=msg.timestamp,
            media=msg.media,
            metadata=msg.metadata,
            trace_id=msg.trace_id,
        )
        # Não responder a mensagens triviais (ok, tá, não, emojis soltos) — evita loop e custo de tokens
        try:
            from backend.guardrails import should_skip_reply
            if should_skip_reply(content):
                logger.debug("Skip reply: trivial message (ok/tá/não/emoji)")
                return None
        except Exception:
            pass
        # Rate limit per user (channel:chat_id); enviar a mensagem no máximo 1x por minuto por chat
        try:
            from backend.rate_limit import is_rate_limited
            if is_rate_limited(msg.channel, msg.chat_id):
                if not _should_send_rate_limit_message(msg.channel, msg.chat_id):
                    return None  # já enviamos "Muitas mensagens" a este chat há pouco
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="Muitas mensagens. Aguarde um minuto antes de enviar de novo.",
                )
        except Exception:
            pass

        self._set_tool_context(msg.channel, msg.chat_id)

        # Aviso "Estou a pesquisar" quando o pedido pode demorar (receita, lista de compras, URL)
        try:
            from nanobot.utils.research_hint import is_research_intent, get_searching_message
            if is_research_intent(content):
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=get_searching_message(),
                ))
        except Exception:
            pass

        # Resposta rápida quando o utilizador "chama" o organizador (ex.: "Organizador?", "Cadê você?") — Mimo, barato e proativo
        if self._is_calling_organizer(content):
            reply = await self._reply_calling_organizer_with_mimo()
            if reply:
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=reply,
                )

        # Idioma do utilizador (por número: pt-BR, pt-PT, es, en) e pedidos explícitos de mudança
        user_lang: str = "en"
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_user_language, set_user_language
            from backend.locale import parse_language_switch_request, language_switch_confirmation_message
            db = SessionLocal()
            try:
                user_lang = get_user_language(db, msg.chat_id)
                requested_lang = parse_language_switch_request(msg.content)
                if requested_lang is not None and requested_lang != user_lang:
                    set_user_language(db, msg.chat_id, requested_lang)
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=language_switch_confirmation_message(requested_lang),
                    )
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"User language check failed: {e}")
            user_lang = "en"

        # Perguntar como gostaria de ser chamado (uma vez por cliente), usando Xiaomi para a pergunta
        # Skip no canal cli (testes e uso por terminal) para não interceptar comandos
        if msg.channel != "cli":
            try:
                from backend.database import SessionLocal
                from backend.user_store import get_or_create_user, set_user_preferred_name
                from backend.locale import preferred_name_confirmation, PREFERRED_NAME_QUESTION
                db = SessionLocal()
                try:
                    user = get_or_create_user(db, msg.chat_id)
                    session = self.sessions.get_or_create(msg.session_key)
                    has_name = bool((user.preferred_name or "").strip())
                    pending = session.metadata.get("pending_preferred_name") is True

                    if not has_name and pending:
                        # Esta mensagem é a resposta: gravar nome e confirmar (ignorar comandos que começam com /)
                        content_stripped = (msg.content or "").strip()
                        if not content_stripped.startswith("/"):
                            name_raw = content_stripped[:128]
                            if name_raw and set_user_preferred_name(db, msg.chat_id, name_raw):
                                session.metadata.pop("pending_preferred_name", None)
                                self.sessions.save(session)
                                conf = preferred_name_confirmation(user_lang, name_raw)
                                session.add_message("user", msg.content)
                                session.add_message("assistant", conf)
                                self.sessions.save(session)
                                return OutboundMessage(
                                    channel=msg.channel,
                                    chat_id=msg.chat_id,
                                    content=conf,
                                )
                        session.metadata.pop("pending_preferred_name", None)
                        self.sessions.save(session)

                    if not has_name and not pending:
                        # Primeira interação: apresentação clara e engajadora (DeepSeek), depois pedir nome
                        intro_sent = session.metadata.get("onboarding_intro_sent") is True
                        if not intro_sent:
                            intro = await self._get_onboarding_intro(user_lang)
                            session.metadata["onboarding_intro_sent"] = True
                            session.metadata["pending_preferred_name"] = True
                            self.sessions.save(session)
                            session.add_message("user", msg.content)
                            session.add_message("assistant", intro)
                            self.sessions.save(session)
                            return OutboundMessage(
                                channel=msg.channel,
                                chat_id=msg.chat_id,
                                content=intro,
                            )
                        question = await self._ask_preferred_name_question(user_lang)
                        session.metadata["pending_preferred_name"] = True
                        self.sessions.save(session)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", question)
                        self.sessions.save(session)
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=question,
                        )

                    # --- Cidade (qualquer cidade do mundo; reconhecidas ajustam o fuso) ---
                    from backend.user_store import (
                        get_user_city,
                        set_user_city,
                        get_default_reminder_lead_seconds,
                        set_default_reminder_lead_seconds,
                        get_extra_reminder_leads_seconds,
                        set_extra_reminder_leads_seconds,
                        get_user_preferred_name,
                    )
                    from backend.lead_time import parse_lead_time_to_seconds, parse_lead_times_to_seconds
                    from backend.locale import lead_time_confirmation

                    has_city = get_user_city(db, msg.chat_id) is not None
                    pending_city = session.metadata.get("pending_city") is True
                    default_lead = get_default_reminder_lead_seconds(db, msg.chat_id)
                    pending_lead = session.metadata.get("pending_lead_time") is True
                    pending_extra = session.metadata.get("pending_extra_leads") is True
                    name_for_prompt = get_user_preferred_name(db, msg.chat_id) or "utilizador"

                    if has_name and not has_city and not pending_city and not pending_lead and not pending_extra:
                        question = await self._ask_city_question(user_lang, name_for_prompt)
                        session.metadata["pending_city"] = True
                        self.sessions.save(session)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", question)
                        self.sessions.save(session)
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=question,
                        )

                    if has_name and pending_city:
                        city_raw = (msg.content or "").strip()
                        if not city_raw.startswith("/") and city_raw:
                            city_name, tz_iana = await self._extract_city_and_timezone_with_mimo(city_raw)
                            if city_name:
                                set_user_city(db, msg.chat_id, city_name, tz_iana=tz_iana)
                            else:
                                set_user_city(db, msg.chat_id, city_raw[:128])
                        session.metadata.pop("pending_city", None)
                        question = await self._ask_lead_time_question(user_lang, name_for_prompt)
                        session.metadata["pending_lead_time"] = True
                        self.sessions.save(session)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", question)
                        self.sessions.save(session)
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=question,
                        )

                    # --- Lead time: quanto tempo antes do evento (default + até 3 extras) ---
                    if has_name and has_city and default_lead is None and not pending_lead and not pending_extra:
                        question = await self._ask_lead_time_question(user_lang, name_for_prompt)
                        session.metadata["pending_lead_time"] = True
                        self.sessions.save(session)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", question)
                        self.sessions.save(session)
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=question,
                        )

                    if has_name and pending_lead:
                        sec = parse_lead_time_to_seconds(msg.content or "")
                        session.metadata.pop("pending_lead_time", None)
                        if sec and 60 <= sec <= 86400 * 365:
                            set_default_reminder_lead_seconds(db, msg.chat_id, sec)
                        question = await self._ask_extra_leads_question(user_lang, name_for_prompt)
                        session.metadata["pending_extra_leads"] = True
                        self.sessions.save(session)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", question)
                        self.sessions.save(session)
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=question,
                        )

                    if has_name and pending_extra:
                        session.metadata.pop("pending_extra_leads", None)
                        current_default = get_default_reminder_lead_seconds(db, msg.chat_id)
                        content_lower = (msg.content or "").strip().lower()
                        if content_lower in ("não", "nao", "no", "nope") or content_lower.startswith("não ") or content_lower.startswith("nao "):
                            set_extra_reminder_leads_seconds(db, msg.chat_id, [])
                            conf = lead_time_confirmation(user_lang, current_default, [])
                        else:
                            leads = parse_lead_times_to_seconds(msg.content or "", 3)
                            leads = [s for s in leads if 60 <= s <= 86400 * 365][:3]
                            set_extra_reminder_leads_seconds(db, msg.chat_id, leads)
                            conf = lead_time_confirmation(user_lang, current_default, leads)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", conf)
                        self.sessions.save(session)
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=conf,
                        )
                finally:
                    db.close()
            except Exception as e:
                logger.debug(f"Preferred name flow failed: {e}")

        # Handlers de comandos (README: /lembrete, /list, /feito, /add, /done, /start, etc.)
        # Confirmações sem botões: 1=sim 2=não. TODO: Após WhatsApp Business API, use buttons.
        try:
            from backend.handlers import HandlerContext, route as handlers_route
            ctx = HandlerContext(
                channel=msg.channel,
                chat_id=msg.chat_id,
                cron_service=self.cron_service,
                cron_tool=self.tools.get("cron"),
                list_tool=self.tools.get("list"),
                event_tool=self.tools.get("event"),
                session_manager=self.sessions,
                scope_provider=self.scope_provider,
                scope_model=self.scope_model,
            )
            result = await handlers_route(ctx, msg.content)
            if result is not None:
                # Persistir também na sessão para o histórico da conversa ficar completo
                try:
                    session = self.sessions.get_or_create(msg.session_key)
                    session.add_message("user", msg.content)
                    session.add_message("assistant", result)
                    self.sessions.save(session)
                except Exception:
                    pass
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=result,
                )
        except Exception as e:
            logger.debug(f"Handlers route failed: {e}")

        # Scope filter: LLM SIM/NAO (fallback: regex). Follow-ups: se a última mensagem do user estava no escopo, considerar esta também.
        from backend.scope_filter import is_in_scope_fast, is_in_scope_llm, is_follow_up_llm
        session = self.sessions.get_or_create(msg.session_key)
        try:
            if self.circuit_breaker.is_open():
                in_scope = is_in_scope_fast(msg.content)
            else:
                try:
                    scope_p = self.scope_provider if self.scope_provider else self.provider
                    in_scope = await is_in_scope_llm(msg.content, provider=scope_p, model=self.scope_model)
                except Exception:
                    self.circuit_breaker.record_failure()
                    in_scope = is_in_scope_fast(msg.content)
        except Exception:
            in_scope = is_in_scope_fast(msg.content)
        if not in_scope:
            # Follow-up: última mensagem do user no escopo (regex) ou Mimo quando o regex não considera a anterior no escopo
            try:
                history = session.get_history(max_messages=20)
                for m in reversed(history):
                    if m.get("role") == "user":
                        prev = (m.get("content") or "").strip()
                        if not prev:
                            break
                        if is_in_scope_fast(prev):
                            in_scope = True
                        elif self.scope_provider and (self.scope_model or "").strip():
                            if await is_follow_up_llm(
                                prev, msg.content or "",
                                provider=self.scope_provider,
                                model=self.scope_model,
                            ):
                                in_scope = True
                        break
            except Exception:
                pass
        if not in_scope:
            content = await self._out_of_scope_message(msg.content, user_lang)
            try:
                session.add_message("user", msg.content)
                session.add_message("assistant", content)
                self.sessions.save(session)
            except Exception:
                pass
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=content,
            )

        # Escolha de modelo: Mimo se (1) muita lógica/raciocínio (cálculos, otimizações, conflitos),
        # (2) pedidos de análise de histórico, (3) velocidade crítica (alto volume). Caso contrário → DeepSeek.
        try:
            from backend.handlers import is_analytical_message, HandlerContext, handle_analytics
            if is_analytical_message(msg.content):
                ctx = HandlerContext(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    cron_service=self.cron_service,
                    cron_tool=self.tools.get("cron"),
                    list_tool=self.tools.get("list"),
                    event_tool=self.tools.get("event"),
                    session_manager=self.sessions,
                    scope_provider=self.scope_provider,
                    scope_model=self.scope_model,
                )
                result = await handle_analytics(ctx, msg.content)
                if result is not None:
                    try:
                        session = self.sessions.get_or_create(msg.session_key)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", result)
                        self.sessions.save(session)
                    except Exception:
                        pass
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=result,
                    )
        except Exception as e:
            logger.debug(f"Analytics (Mimo) pre-agent check failed: {e}")

        # Circuit open: skip LLM, return degraded message (parser already ran above)
        if self.circuit_breaker.is_open():
            logger.warning("Circuit breaker open: responding in degraded mode (parser-only)")
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="Serviço temporariamente limitado. Use /help para ver os comandos.",
            )

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {preview}")

        # Conversacional: agente principal (DeepSeek)
        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)

        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )
        
        # Agent loop
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1

            # Call LLM (circuit breaker records success/failure)
            try:
                response = await self.provider.chat(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=self.model
                )
                self.circuit_breaker.record_success()
            except Exception as e:
                self.circuit_breaker.record_failure()
                logger.warning(f"LLM call failed (circuit breaker): {e}")
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="Serviço temporariamente indisponível. Tente /help para ver os comandos.",
                )

            # Handle tool calls
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                # Execute tools
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info(f"Tool call: {tool_call.name}({args_str[:200]})")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                # No tool calls, we're done
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "I've completed processing but have no response to give."
        
        # Log response preview
        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info(f"Response to {msg.channel}:{msg.sender_id}: {preview}")
        
        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content
        )
    
    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).
        
        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            trace_id=uuid.uuid4().hex[:12],
        )

        response = await self._process_message(msg)
        return response.content if response else ""
