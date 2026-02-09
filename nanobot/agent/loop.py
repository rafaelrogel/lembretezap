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
        
        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))
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
            return await list_tool.execute(
                action="add",
                list_name=intent.get("list_name", ""),
                item_text=intent.get("item", ""),
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
        if t == "filme":
            absurd = is_absurd_request(msg.content) or is_absurd_request(intent.get("nome", "") or "")
            if absurd:
                return absurd
            if not event_tool:
                return None
            return await event_tool.execute(action="add", tipo="filme", nome=intent.get("nome", ""))
        return None

    async def _out_of_scope_message(self, user_content: str, lang: str = "en") -> str:
        """Resposta variada e amigável quando o pedido está fora do escopo (Xiaomi ou fallback). Respeita idioma (pt-PT, pt-BR, es, en)."""
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
                    "You are an organization assistant (reminders, lists, events). The user said: «"
                    + (user_content[:200] if user_content else "")
                    + "». Reply in ONE short, friendly sentence with personality: say you only help with reminders, lists and events and suggest /lembrete, /list or /filme. You may use 1 emoji. Reply only with the message text, "
                    + lang_instruction + "."
                )
                r = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.scope_model,
                    max_tokens=100,
                    temperature=0.6,
                )
                out = (r.content or "").strip()
                if out and len(out) <= 300:
                    return out
            except Exception as e:
                logger.debug(f"Out-of-scope message (Xiaomi) failed: {e}")
        return random.choice(fallbacks)

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

        # Scope filter: LLM SIM/NAO (fallback: regex). Skip LLM when circuit is open.
        from backend.scope_filter import is_in_scope_fast, is_in_scope_llm
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
            content = await self._out_of_scope_message(msg.content, user_lang)
            try:
                session = self.sessions.get_or_create(msg.session_key)
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
                content="Serviço temporariamente limitado. Use comandos /lembrete, /list ou /filme.",
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
                    content="Serviço temporariamente indisponível. Tente /lembrete, /list ou /filme.",
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
