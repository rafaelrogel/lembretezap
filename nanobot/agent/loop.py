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

    async def _maybe_sentiment_check(
        self, session, channel: str, chat_id: str
    ) -> None:
        """A cada 20 mensagens: Mimo verifica frustração/reclamação; se houver, regista em painpoints."""
        try:
            total = len(session.messages)
            if total < 20 or total % 20 != 0:
                return
            if not self.scope_provider or not self.scope_model:
                return
            from backend.sentiment_check import check_frustration_or_complaint
            from backend.painpoints_store import add_painpoint
            history = session.get_history(max_messages=25)
            if await check_frustration_or_complaint(
                history, self.scope_provider, self.scope_model
            ):
                add_painpoint(chat_id, "frustração/reclamação detectada pelo Mimo")
                logger.info(f"Painpoint registado: {chat_id[:20]}... (frustração/reclamação)")
        except Exception as e:
            logger.debug(f"Sentiment check failed: {e}")

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
            start_date = intent.get("start_date")
            if in_sec or every_sec or cron_expr:
                return await cron_tool.execute(
                    action="add",
                    message=msg_text,
                    in_seconds=in_sec,
                    every_seconds=every_sec,
                    cron_expr=cron_expr,
                    start_date=start_date,
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
                    "Out of scope: «"
                    + (user_content[:150] if user_content else "")
                    + "». Reply in 1 SHORT sentence. Say you help with reminders and lists. /help. 1 emoji. "
                    "Reply ONLY the message, " + lang_instruction + ". No preamble."
                )
                r = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.scope_model,
                    max_tokens=70,
                    temperature=0.7,
                )
                out = (r.content or "").strip()
                if out and len(out) <= 245:
                    return out
            except Exception as e:
                logger.debug(f"Out-of-scope message (Xiaomi) failed: {e}")
        return random.choice(fallbacks)

    async def _get_onboarding_intro(self, user_lang: str) -> str:
        """Mensagem de apresentação na primeira interação. Xiaomi primeiro (fluxo simples), fallback DeepSeek."""
        lang_instruction = {
            "pt-PT": "em português de Portugal",
            "pt-BR": "em português do Brasil",
            "es": "en español",
            "en": "in English",
        }.get(user_lang, "in the user's language")
        prompt = (
            "AI org assistant. First contact. One SHORT paragraph (2-3 sentences): intro, what you do (lists+events), ask their name. 1 emoji. "
            f"Reply ONLY the message, {lang_instruction}. No preamble."
        )
        if self.scope_provider and self.scope_model:
            try:
                r = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.scope_model,
                    max_tokens=196,
                    temperature=0.6,
                )
                out = (r.content or "").strip().strip('"\'')
                if out and len(out) <= 385:
                    return out
            except Exception as e:
                logger.debug(f"Onboarding intro (Xiaomi) failed: {e}")
        try:
            r = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=196,
                temperature=0.6,
            )
            out = (r.content or "").strip().strip('"\'')
            if out and len(out) <= 385:
                return out
        except Exception as e:
            logger.debug(f"Onboarding intro (DeepSeek) failed: {e}")
        fallbacks = {
            "pt-PT": "Olá! Sou a tua assistente de organização. 📋 Listas (compras, receitas), lembretes e eventos. Como gostarias de ser chamado? 😊",
            "pt-BR": "Oi! Sou sua assistente de organização. 📋 Listas (compras, receitas), lembretes e eventos. Como gostaria de ser chamado? 😊",
            "es": "¡Hola! Soy tu asistente de organización. 📋 Listas, recordatorios y eventos. ¿Cómo te gustaría que te llamara? 😊",
            "en": "Hi! I'm your organization assistant. 📋 Lists, reminders and events. How would you like to be called? 😊",
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

    async def _reply_calling_organizer_with_mimo(self, user_lang: str) -> str:
        """Resposta curta e proativa ao ser 'chamado' (Mimo, barato). Uma só frase, no idioma do utilizador."""
        lang_instruction = {
            "pt-PT": "in European Portuguese (Portugal). Examples: Estou aqui!, À postos!, Chamou?",
            "pt-BR": "in Brazilian Portuguese. Examples: Estou aqui!, Opa!, Chamou?, À postos!",
            "es": "in Spanish. Examples: ¡Estoy aquí!, ¿Sí?, ¡Aquí!",
            "en": "in English. Examples: I'm here!, Hey!, What's up?",
        }.get(user_lang, "in English. Examples: I'm here!, What's up?")
        if not self.scope_provider or not self.scope_model:
            fallbacks = {
                "pt-PT": "Estou aqui! O que precisa?",
                "pt-BR": "Estou aqui! O que precisa?",
                "es": "¡Aquí! ¿Qué necesitas?",
                "en": "Here! What do you need?",
            }
            return fallbacks.get(user_lang, fallbacks["en"])
        try:
            prompt = (
                "The user just called the assistant (short call like 'Organizador?', 'Tá aí?', 'Are you there?', 'Rapaz?'). "
                f"Reply with ONE very short, friendly, proactive phrase {lang_instruction}. "
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
        fallbacks = {
            "pt-PT": "Estou aqui! O que precisa?",
            "pt-BR": "Estou aqui! O que precisa?",
            "es": "¡Aquí! ¿Qué necesitas?",
            "en": "Here! What do you need?",
        }
        return fallbacks.get(user_lang, fallbacks["en"])

    async def _ask_city_question(self, user_lang: str, name: str) -> str:
        """Pergunta natural em que cidade está (para fuso horário). Xiaomi primeiro (fluxo simples), fallback DeepSeek."""
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
        if self.scope_provider and self.scope_model:
            try:
                r = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.scope_model,
                    max_tokens=100,
                    temperature=0.5,
                )
                out = (r.content or "").strip()
                if out and len(out) <= 220:
                    return out
            except Exception as e:
                logger.debug(f"Ask city (Xiaomi) failed: {e}")
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

    def _sync_onboarding_to_memory(self, db, chat_id: str, session_key: str) -> None:
        """Regista os dados do onboarding na memória longa do cliente (MEMORY.md) para o agente saber e aceder."""
        try:
            from backend.onboarding_memory import build_onboarding_profile_md, SECTION_HEADING
            md = build_onboarding_profile_md(db, chat_id)
            self.context.memory.upsert_section(session_key, SECTION_HEADING, md)
        except Exception as e:
            logger.debug(f"Onboarding memory sync failed: {e}")

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
        # Reset + set: se o cliente insistir/reclamar após rejeição por intervalo, permitir até 30 min
        cron_tool = self.tools.get("cron")
        if cron_tool:
            cron_tool.set_allow_relaxed_interval(False)
            try:
                from backend.guardrails import user_insisting_on_interval_rejection
                insisting = await user_insisting_on_interval_rejection(
                    self.sessions, msg.channel, msg.chat_id, content or "",
                    self.scope_provider, self.scope_model or "",
                )
                if insisting:
                    cron_tool.set_allow_relaxed_interval(True)
            except Exception:
                pass

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

        # Resposta rápida quando o utilizador "chama" o bot (ex.: "Organizador?", "Rapaz?", "Tá aí?", "Are you there?") — Mimo, barato e proativo
        try:
            from backend.calling_phrases import is_calling_message
            from backend.locale import phone_to_default_language
            if is_calling_message(content):
                reply_lang = phone_to_default_language(msg.chat_id)
                reply = await self._reply_calling_organizer_with_mimo(reply_lang)
                if reply:
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=reply,
                    )
        except Exception as e:
            logger.debug(f"Calling-phrases check failed: {e}")

        # Idioma: 1º número do telemóvel, 2º configuração guardada, 3º língua do chat (se pt-PT/pt-BR/es/en)
        # Em caso de falha (ex.: DB), usar sempre idioma do número — nunca assumir "en" sem número.
        user_lang: str = "en"
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_user_language, set_user_language
            from backend.locale import (
                parse_language_switch_request,
                language_switch_confirmation_message,
                phone_to_default_language,
                SUPPORTED_LANGS,
            )
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
            user_lang = phone_to_default_language(msg.chat_id)

        # Proteção contra prompt injection: rejeitar antes de chegar ao agente
        try:
            from backend.injection_guard import is_injection_attempt, get_injection_response, record_injection_blocked
            if is_injection_attempt(content):
                logger.info(f"Injection attempt blocked: {content[:80]}...")
                record_injection_blocked(msg.chat_id, (content or "")[:80])
                injection_msg = get_injection_response(user_lang)
                try:
                    session = self.sessions.get_or_create(msg.session_key)
                    session.add_message("user", msg.content)
                    session.add_message("assistant", injection_msg)
                    self.sessions.save(session)
                except Exception:
                    pass
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=injection_msg,
                )
        except Exception as e:
            logger.debug(f"Injection guard failed: {e}")

        # Perguntar como gostaria de ser chamado (uma vez por cliente), usando Xiaomi para a pergunta
        # Skip no canal cli (testes e uso por terminal) para não interceptar comandos
        # Intro e pergunta do nome: sempre no idioma do número (nunca assumir inglês por defeito).
        if msg.channel != "cli":
            try:
                from backend.database import SessionLocal
                from backend.user_store import get_or_create_user, set_user_preferred_name, get_user_preferred_name
                from backend.locale import (
                    preferred_name_confirmation,
                    PREFERRED_NAME_QUESTION,
                    phone_to_default_language as _phone_lang,
                )
                db = SessionLocal()
                try:
                    user = get_or_create_user(db, msg.chat_id)
                    session = self.sessions.get_or_create(msg.session_key)
                    has_name = bool((user.preferred_name or "").strip())
                    pending = session.metadata.get("pending_preferred_name") is True
                    intro_lang = _phone_lang(msg.chat_id)  # 1.º idioma = número; usado na intro e no pedido do nome

                    if not has_name and pending:
                        # Esta mensagem é a resposta: gravar nome e confirmar (ignorar comandos que começam com /)
                        content_stripped = (msg.content or "").strip()
                        if not content_stripped.startswith("/"):
                            name_raw = content_stripped[:128]
                            if name_raw and set_user_preferred_name(db, msg.chat_id, name_raw):
                                session.metadata.pop("pending_preferred_name", None)
                                self.sessions.save(session)
                                self._sync_onboarding_to_memory(db, msg.chat_id, msg.session_key)
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
                        # Primeira interação: apresentação no idioma do número, depois pedir nome
                        intro_sent = session.metadata.get("onboarding_intro_sent") is True
                        if not intro_sent:
                            intro = await self._get_onboarding_intro(intro_lang)
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
                        question = await self._ask_preferred_name_question(intro_lang)
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

                    # --- Idioma preferido (após o nome): "quer comunicar noutro idioma?" ---
                    from backend.user_store import set_user_language
                    from backend.locale import ONBOARDING_LANGUAGE_QUESTION, parse_language_switch_request as _parse_lang

                    onboarding_language_asked = session.metadata.get("onboarding_language_asked") is True
                    pending_language_choice = session.metadata.get("pending_language_choice") is True

                    if has_name and pending_language_choice:
                        # Resposta à pergunta "quer outro idioma?": aplicar se escolheu um idioma e seguir para cidade
                        content_stripped = (msg.content or "").strip()
                        if not content_stripped.startswith("/"):
                            chosen = _parse_lang(content_stripped)
                            if chosen:
                                set_user_language(db, msg.chat_id, chosen)
                                user_lang = chosen
                                self._sync_onboarding_to_memory(db, msg.chat_id, msg.session_key)
                        session.metadata.pop("pending_language_choice", None)
                        session.metadata["onboarding_language_asked"] = True
                        self.sessions.save(session)
                        name_for_prompt = get_user_preferred_name(db, msg.chat_id) or "utilizador"
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

                    # --- Cidade (qualquer cidade do mundo; reconhecidas ajustam o fuso). Onboarding termina aqui (sem perguntar avisos antes do evento). ---
                    from backend.user_store import (
                        get_user_city,
                        set_user_city,
                        get_user_preferred_name,
                        get_user_language as _get_user_lang,
                    )
                    from backend.locale import ONBOARDING_COMPLETE

                    has_city = get_user_city(db, msg.chat_id) is not None
                    pending_city = session.metadata.get("pending_city") is True
                    name_for_prompt = get_user_preferred_name(db, msg.chat_id) or "utilizador"
                    if has_name:
                        try:
                            user_lang = _get_user_lang(db, msg.chat_id)
                        except Exception:
                            pass

                    if has_name and pending_language_choice is False and not onboarding_language_asked and not has_city and not pending_city:
                        # Perguntar se quer comunicar noutro idioma (pt-PT, pt-BR, es, en)
                        lang_question = ONBOARDING_LANGUAGE_QUESTION.get(user_lang, ONBOARDING_LANGUAGE_QUESTION["en"])
                        session.metadata["pending_language_choice"] = True
                        self.sessions.save(session)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", lang_question)
                        self.sessions.save(session)
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=lang_question,
                        )

                    if has_name and not has_city and not pending_city:
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
                            self._sync_onboarding_to_memory(db, msg.chat_id, msg.session_key)
                        session.metadata.pop("pending_city", None)
                        complete_msg = ONBOARDING_COMPLETE.get(user_lang, ONBOARDING_COMPLETE["en"])
                        self.sessions.save(session)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", complete_msg)
                        self.sessions.save(session)
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=complete_msg,
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
                main_provider=self.provider,
                main_model=self.model,
            )
            result = await handlers_route(ctx, msg.content)
            if result is not None:
                # Persistir também na sessão para o histórico da conversa ficar completo
                try:
                    session = self.sessions.get_or_create(msg.session_key)
                    session.add_message("user", msg.content)
                    session.add_message("assistant", result)
                    self.sessions.save(session)
                    asyncio.create_task(self._maybe_sentiment_check(session, msg.channel, msg.chat_id))
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
                asyncio.create_task(self._maybe_sentiment_check(session, msg.channel, msg.chat_id))
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
                    main_provider=self.provider,
                    main_model=self.model,
                )
                result = await handle_analytics(ctx, msg.content)
                if result is not None:
                    try:
                        session = self.sessions.get_or_create(msg.session_key)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", result)
                        self.sessions.save(session)
                        asyncio.create_task(self._maybe_sentiment_check(session, msg.channel, msg.chat_id))
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
        # user_lang já definido acima: 1.º número, 2.º config, 3.º mensagem (se pt-PT/pt-BR/es/en)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
            user_lang=user_lang,
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

        # A cada 20 mensagens: Mimo analisa frustração/reclamação → painpoints
        asyncio.create_task(self._maybe_sentiment_check(session, msg.channel, msg.chat_id))

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
