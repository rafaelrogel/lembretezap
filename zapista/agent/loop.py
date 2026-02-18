"""Agent loop: the core processing engine."""

import asyncio
import json
import random
import re
import time
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from zapista.bus.events import InboundMessage, OutboundMessage
from zapista.utils.logging_config import set_trace_id, reset_trace_id
from zapista.bus.queue import MessageBus
from zapista.providers.base import LLMProvider
from zapista.agent.context import ContextBuilder
from zapista.agent.tools.registry import ToolRegistry
from zapista.agent.tools.message import MessageTool
from zapista.agent.tools.cron import CronTool
from zapista.agent.tools.list_tool import ListTool
from zapista.agent.tools.event_tool import EventTool
from zapista.agent.tools.read_file import ReadFileTool
from zapista.session.manager import Session, SessionManager
from zapista.utils.circuit_breaker import CircuitBreaker

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
        max_tokens: int = 2048,
        cron_service: "CronService | None" = None,
        perplexity_api_key: str | None = None,
    ):
        from zapista.cron.service import CronService
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.scope_model = scope_model or self.model
        self.scope_provider = scope_provider  # quando setado, scope filter e heartbeat usam este (ex.: Xiaomi)
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.cron_service = cron_service
        self._perplexity_api_key = (perplexity_api_key or "").strip()

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
        except Exception as e:
            logger.warning("init_db failed (listas/eventos podem falhar): {}", e)
        try:
            from backend.database import SessionLocal
            from backend.models_db import List
            _db = SessionLocal()
            try:
                _db.query(List).limit(1).first()
            finally:
                _db.close()
        except Exception as e:
            logger.exception("Listas: verificação de BD ao arranque falhou (listas/eventos vão dar erro): {}", e)
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Cron tool (for scheduling; MIMO opcional para sugerir ID quando fora da lista de palavras)
        if self.cron_service:
            self.tools.register(CronTool(
                self.cron_service,
                scope_provider=self.scope_provider,
                scope_model=self.scope_model or "",
                session_manager=self.sessions,
            ))
        # List and event tools (per-user DB)
        self.tools.register(ListTool(
            scope_provider=self.scope_provider,
            scope_model=self.scope_model or "",
        ))
        self.tools.register(EventTool())
        # Search tool (Perplexity) — só quando API key disponível
        if self._perplexity_api_key:
            from zapista.agent.tools.search_tool import SearchTool
            self.tools.register(SearchTool(api_key=self._perplexity_api_key))
        # Read file: carregar bootstrap, rules e skills on demand (reduz tokens)
        self.tools.register(ReadFileTool(workspace=self.workspace))
    
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

    async def _maybe_compress_session(
        self,
        session: Session,
        session_key: str,
    ) -> None:
        """
        Se a sessão tiver >= 45 mensagens, condensa as primeiras 25 via Mimo:
        - Cria mensagem de resumo no histórico
        - Guarda bullets condensados em MEMORY.md (2-4 pontos essenciais)
        """
        from datetime import datetime

        if len(session.messages) < 45:
            return
        if not self.scope_provider or not self.scope_model:
            return

        to_compress = session.messages[:25]
        lines = []
        for m in to_compress:
            role = m.get("role", "")
            cont = (m.get("content") or "").strip()
            if m.get("_type") == "summary":
                lines.append(f"[Resumo anterior] {cont[:200]}")
            else:
                label = "Utilizador" if role == "user" else "Assistente"
                lines.append(f"[{label}] {cont}")
        data_text = "\n".join(lines) if lines else ""

        try:
            prompt = (
                "Resume esta conversa em 4-5 frases curtas. Foco em: lembretes criados, listas tocadas, decisões, pedidos. "
                "Depois, na linha seguinte, começa por BULLETS: e lista 2-4 pontos essenciais para memória longa (um por linha, com -)."
            )
            r = await self.scope_provider.chat(
                messages=[{"role": "user", "content": f"{prompt}\n\nConversa:\n{data_text}"}],
                model=self.scope_model,
                profile="parser",
            )
            out = (r.content or "").strip()
            if not out:
                return

            # Extrair bullets (após BULLETS:)
            bullets = ""
            if "BULLETS:" in out:
                summary_part, _, bullets_raw = out.partition("BULLETS:")
                summary = summary_part.strip()
                bullets = bullets_raw.strip()
                # Normalizar bullets: garantir que cada linha começa com -
                bullet_lines = [line.strip() for line in bullets.split("\n") if line.strip()]
                bullets = "\n".join(f"- {b.lstrip('- ')}" for b in bullet_lines)[:600]
            else:
                summary = out[:500]

            summary_msg = {
                "role": "user",
                "content": f"[Resumo da conversa anterior]\n{summary}",
                "_type": "summary",
                "timestamp": datetime.now().isoformat(),
            }
            session.messages = [summary_msg] + session.messages[25:]
            self.sessions.save(session)

            # Guardar em MEMORY.md (versão condensada: 2-4 bullets)
            if bullets and session_key:
                try:
                    self.context.memory.upsert_section(
                        session_key,
                        "## Resumo de conversas",
                        bullets[:500].strip(),
                    )
                except Exception as e:
                    logger.debug(f"Memory upsert failed: {e}")
        except Exception as e:
            logger.debug(f"Session compression failed: {e}")

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

    def _set_tool_context(self, channel: str, chat_id: str, phone_for_locale: str | None = None) -> None:
        """Define canal/chat (e phone_for_locale para cron) em todas as tools que suportam."""
        for name, tool in (("message", MessageTool), ("cron", CronTool), ("list", ListTool), ("event", EventTool)):
            t = self.tools.get(name)
            if t and isinstance(t, tool):
                if isinstance(t, CronTool):
                    t.set_context(channel, chat_id, phone_for_locale)
                else:
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
                    "Out of scope: \""
                    + (user_content[:150] if user_content else "")
                    + "\". Reply in 1 SHORT sentence. Say you help with reminders and lists. "
                    "Tell them they can type the command /help to see the full list of commands, and that they can also send a message or audio. 1 emoji. "
                    "Use only normal quotes in your reply, never guillemets. Reply ONLY the message, " + lang_instruction + ". No preamble."
                )
                r = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.scope_model,
                    profile="parser",
                )
                out = (r.content or "").strip()
                if out and len(out) <= 245:
                    return out
            except Exception as e:
                logger.debug(f"Out-of-scope message (Xiaomi) failed: {e}")
        return random.choice(fallbacks)

    async def _get_onboarding_intro(self, user_lang: str) -> str:
        """Mensagem de apresentação na primeira interação. Xiaomi primeiro. Fluxo: intro → idioma (1/4) → nome (2/4) → cidade (3/4)."""
        lang_instruction = {
            "pt-PT": "em português de Portugal",
            "pt-BR": "em português do Brasil",
            "es": "en español",
            "en": "in English",
        }.get(user_lang, "in the user's language")
        prompt = (
            "AI org assistant. First contact. One SHORT paragraph (2-3 sentences): intro, what you do (lists, reminders, events). "
            "End with 'Let\\'s get started!' or equivalent. 1 emoji. Do NOT ask for their name yet. "
            f"Reply ONLY the message, {lang_instruction}. No preamble."
        )
        if self.scope_provider and self.scope_model:
            try:
                r = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.scope_model,
                    profile="parser",
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
                profile="assistant",
            )
            out = (r.content or "").strip().strip('"\'')
            if out and len(out) <= 385:
                return out
        except Exception as e:
            logger.debug(f"Onboarding intro (DeepSeek) failed: {e}")
        fallbacks = {
            "pt-PT": "Olá! Sou a tua assistente de organização. 📋 Listas (compras, receitas), lembretes e eventos. Vamos começar! 😊",
            "pt-BR": "Oi! Sou sua assistente de organização. 📋 Listas (compras, receitas), lembretes e eventos. Vamos começar! 😊",
            "es": "¡Hola! Soy tu asistente de organización. 📋 Listas, recordatorios y eventos. ¡Empecemos! 😊",
            "en": "Hi! I'm your organization assistant. 📋 Lists, reminders and events. Let's get started! 😊",
        }
        return fallbacks.get(user_lang, fallbacks["en"])

    async def _ask_preferred_name_question(self, user_lang: str) -> str:
        """Pergunta amigável 'como gostaria de ser chamado' no idioma do utilizador (Xiaomi ou fallback)."""
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
                    f"Reply only with that question, {lang_instruction}. Use only normal quotes, never guillemets (« »). No other text."
                )
                r = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.scope_model,
                    profile="parser",
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
                    "The user was asked which city they are in. They replied: \"" + (user_content[:200] or "") + "\". "
                    "Extract the city name (one city only). Use standard English name (e.g. Lisbon, São Paulo, London, Tokyo). "
                    "If they mention a country/region without a city, use the capital. Reply with ONLY the city name, nothing else."
                )
                r1 = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt1}],
                    model=self.scope_model,
                    profile="parser",
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
                    "What is the IANA timezone for the city \"" + city_name + "\"? "
                    "Reply with ONLY the IANA timezone identifier, e.g. Europe/Lisbon or America/Sao_Paulo or Asia/Tokyo. One line only."
                )
                r2 = await self.scope_provider.chat(
                    messages=[{"role": "user", "content": prompt2}],
                    model=self.scope_model,
                    profile="parser",
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
                profile="parser",
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
                    profile="parser",
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
                profile="assistant",
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

    def _write_client_memory_file(self, db, chat_id: str) -> None:
        """Atualiza o ficheiro de memória do cliente (workspace/users/<chat_id>.md) com nome, timezone, idioma da BD."""
        try:
            from backend.client_memory import build_client_memory_content, write_client_memory_file
            content = build_client_memory_content(db, chat_id)
            if content.strip():
                write_client_memory_file(self.workspace, chat_id, content)
        except Exception as e:
            logger.debug(f"Client memory file write failed: {e}")

    def _sync_onboarding_to_memory(self, db, chat_id: str, session_key: str) -> None:
        """Regista os dados do onboarding na memória longa do agente e no ficheiro do cliente (workspace/users/<chat_id>.md)."""
        try:
            from backend.onboarding_memory import build_onboarding_profile_md, SECTION_HEADING
            md = build_onboarding_profile_md(db, chat_id)
            self.context.memory.upsert_section(session_key, SECTION_HEADING, md)
            self._write_client_memory_file(db, chat_id)
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
        # Regista mensagem do cliente para contagem diária (lembrete inteligente só após >= 2 msgs no dia)
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_user_timezone
            from backend.smart_reminder import record_user_message_sent
            _db = SessionLocal()
            try:
                _tz = get_user_timezone(_db, msg.chat_id) or "UTC"
                record_user_message_sent(msg.chat_id, _tz)
            finally:
                _db.close()
        except Exception:
            pass
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

        # Notificação atrasada: lembretes removidos (no passado) — enviar só após 2 msgs do cliente (anti-spam)
        try:
            from backend.stale_removal_notifications import consume as consume_stale_removal
            send_apology, apology_text = consume_stale_removal(msg.channel, msg.chat_id)
            if send_apology and apology_text:
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=apology_text,
                ))
        except Exception:
            pass

        self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("phone_for_locale") if msg.metadata else None)

        # Resumo da semana/mês: entregar apenas no primeiro contacto (aproveitar sessão aberta pelo cliente)
        # Estado "já entregue" fica na BD (AuditLog) para não reenviar em cada mensagem.
        # Só ativo a partir de abril de 2026.
        try:
            from datetime import date, datetime
            from zoneinfo import ZoneInfo
            from backend.database import SessionLocal
            from backend.user_store import get_or_create_user, get_user_timezone
            from backend.models_db import AuditLog
            from backend.weekly_recap import get_pending_recap_on_first_contact
            RECAP_ACTIVE_FROM = date(2026, 4, 1)
            db = SessionLocal()
            try:
                user = get_or_create_user(db, msg.chat_id)
                tz_iana = get_user_timezone(db, msg.chat_id) or "UTC"
                try:
                    tz = ZoneInfo(tz_iana)
                except Exception:
                    tz = ZoneInfo("UTC")
                today_user = date(datetime.now(tz).year, datetime.now(tz).month, datetime.now(tz).day) if tz else date.today()
                if today_user >= RECAP_ACTIVE_FROM:
                    weekly_content, weekly_period_id, monthly_content, monthly_period_id = get_pending_recap_on_first_contact(
                        db, msg.chat_id, tz
                    )
                    # Só enviar se ainda não tivermos registado entrega para este período (por user_id na BD)
                    if weekly_content and weekly_period_id:
                        already = db.query(AuditLog).filter(
                            AuditLog.user_id == user.id,
                            AuditLog.action == "recap_weekly_delivered",
                            AuditLog.resource == weekly_period_id,
                        ).first()
                        if not already:
                            await self.bus.publish_outbound(OutboundMessage(
                                channel=msg.channel,
                                chat_id=msg.chat_id,
                                content=weekly_content,
                            ))
                            db.add(AuditLog(user_id=user.id, action="recap_weekly_delivered", resource=weekly_period_id))
                            db.commit()
                    if monthly_content and monthly_period_id:
                        already = db.query(AuditLog).filter(
                            AuditLog.user_id == user.id,
                            AuditLog.action == "recap_monthly_delivered",
                            AuditLog.resource == monthly_period_id,
                        ).first()
                        if not already:
                            await self.bus.publish_outbound(OutboundMessage(
                                channel=msg.channel,
                                chat_id=msg.chat_id,
                                content=monthly_content,
                            ))
                            db.add(AuditLog(user_id=user.id, action="recap_monthly_delivered", resource=monthly_period_id))
                            db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Pending recap on first contact failed: {e}")

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
            from zapista.utils.research_hint import is_research_intent, get_searching_message
            if is_research_intent(content):
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=get_searching_message(content),
                ))
        except Exception:
            pass

        # Pedido de mudança de idioma ANTES do calling — para "fale comigo em português" não ser tratado como chamada
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_user_language, set_user_language
            from backend.locale import (
                parse_language_switch_request,
                language_switch_confirmation_message,
                LANGUAGE_ALREADY_MSG,
            )
            db = SessionLocal()
            try:
                phone_for_locale = msg.metadata.get("phone_for_locale")
                user_lang = get_user_language(db, msg.chat_id, phone_for_locale)
                requested_lang = parse_language_switch_request(
                    msg.content, msg.metadata.get("phone_for_locale") or msg.chat_id
                )
                if requested_lang is not None:
                    if requested_lang != user_lang:
                        set_user_language(db, msg.chat_id, requested_lang)
                        self._write_client_memory_file(db, msg.chat_id)
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=language_switch_confirmation_message(requested_lang),
                        )
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=LANGUAGE_ALREADY_MSG.get(requested_lang, LANGUAGE_ALREADY_MSG["pt-BR"]),
                    )
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Language switch check failed: {e}")

        # Resposta rápida quando o utilizador "chama" o bot (ex.: "Organizador?", "Rapaz?", "Tá aí?") — não tratar como chamada se for evento+data+hora (ex.: "preciso ir ao médico amanhã às 17h")
        try:
            from backend.calling_phrases import is_calling_message
            from backend.reminder_flow import has_full_event_datetime
            from backend.locale import phone_to_default_language
            if has_full_event_datetime(content or ""):
                pass  # deixa seguir para o router/handler (agenda + lembrete)
            elif is_calling_message(content):
                id_for_locale = msg.metadata.get("phone_for_locale") or msg.chat_id
                reply_lang = phone_to_default_language(id_for_locale)
                reply = await self._reply_calling_organizer_with_mimo(reply_lang)
                if reply:
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=reply,
                        metadata=dict(msg.metadata or {}),
                    )
        except Exception as e:
            logger.debug(f"Calling-phrases check failed: {e}")

        # Idioma: preferência guardada (fala em ptbr, /lang) tem prioridade; senão infere pelo número (phone_for_locale).
        # Timezone é independente. Em falha de DB usa número para não assumir "en" à toa.
        user_lang: str = "en"
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_user_language, set_user_language
            from backend.locale import (
                phone_to_default_language,
                resolve_response_language,
                SUPPORTED_LANGS,
            )
            db = SessionLocal()
            try:
                phone_for_locale = msg.metadata.get("phone_for_locale")
                user_lang = get_user_language(db, msg.chat_id, phone_for_locale)
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"User language check failed: {e}")
            id_for_locale = msg.metadata.get("phone_for_locale") or msg.chat_id
            user_lang = phone_to_default_language(id_for_locale)

        user_lang = resolve_response_language(
            user_lang, msg.chat_id, msg.metadata.get("phone_for_locale")
        )

        # Filtragem de comandos perigosos (shell, SQL, path): blocklist com logging
        try:
            from backend.command_filter import is_blocked, record_blocked
            blocked, reason = is_blocked(content)
            if blocked:
                logger.warning(f"Command blocked: reason={reason} from {msg.chat_id[:16]}...")
                record_blocked(msg.channel, msg.chat_id, (content or "")[:80], reason)
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="Não posso processar esta mensagem.",
                )
        except Exception as e:
            logger.debug(f"Command filter failed: {e}")

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

        # Onboarding simplificado: só fuso (cidade ou hora). Não bloqueia o sistema — quem não responde segue para comandos/LLM.
        if msg.channel != "cli":
            try:
                from datetime import datetime
                from zoneinfo import ZoneInfo
                from backend.database import SessionLocal
                from backend.user_store import (
                    get_or_create_user, get_user_city, set_user_city, set_user_timezone,
                    get_user_language as _get_user_lang, set_user_preferred_name, get_user_preferred_name,
                )
                from backend.locale import (
                    phone_to_default_language as _phone_lang,
                    ONBOARDING_INTRO_TZ_FIRST,
                    ONBOARDING_ASK_CITY_OR_TIME,
                    ONBOARDING_ASK_TIME_FALLBACK,
                    onboarding_time_confirm_message,
                    ONBOARDING_COMPLETE,
                    ONBOARDING_DAILY_USE_APPEAL,
                    ONBOARDING_EMOJI_TIP,
                    ONBOARDING_RESET_HINT,
                    ONBOARDING_TZ_SET_FROM_TIME,
                    NUDGE_TZ_WHEN_MISSING,
                    PREFERRED_NAME_QUESTION,
                    preferred_name_confirmation,
                )
                from backend.onboarding_skip import is_likely_not_city, is_likely_valid_name, is_onboarding_refusal_or_skip
                from backend.onboarding_time import parse_local_time_from_message
                from backend.timezone import iana_from_offset_minutes, phone_to_default_timezone, is_valid_iana
                db = SessionLocal()
                try:
                    user = get_or_create_user(db, msg.chat_id)
                    session = self.sessions.get_or_create(msg.session_key)
                    has_tz_set = bool((user.timezone or "").strip())
                    has_name = bool((get_user_preferred_name(db, msg.chat_id) or "").strip())
                    pending_preferred_name = session.metadata.get("pending_preferred_name") is True
                    id_for_locale = msg.metadata.get("phone_for_locale") or msg.chat_id
                    intro_lang = _phone_lang(id_for_locale)
                    intro_sent = session.metadata.get("onboarding_intro_sent") is True
                    pending_timezone = session.metadata.get("pending_timezone") is True
                    pending_time_confirm = session.metadata.get("pending_time_confirm") is True
                    try:
                        user_lang = _get_user_lang(db, msg.chat_id, msg.metadata.get("phone_for_locale"))
                    except Exception:
                        user_lang = intro_lang

                    # Resposta à pergunta «Como gostarias de ser chamado?» (após fuso definido)
                    if has_tz_set and pending_preferred_name and not (msg.content or "").strip().startswith("/"):
                        content_name = (msg.content or "").strip()
                        name_to_save = None
                        if content_name and is_likely_valid_name(content_name):
                            name_to_save = content_name[:128]
                        if name_to_save is None:
                            # Fallback: nome do perfil WhatsApp (pushName)
                            wa_name = (msg.metadata.get("sender_display_name") or "").strip()
                            if wa_name and len(wa_name) >= 2 and not wa_name.isdigit():
                                name_to_save = wa_name[:128]
                        if name_to_save is None:
                            name_to_save = "utilizador"
                        set_user_preferred_name(db, msg.chat_id, name_to_save)
                        session.metadata.pop("pending_preferred_name", None)
                        self._sync_onboarding_to_memory(db, msg.chat_id, msg.session_key)
                        self.sessions.save(session)
                        lang_key = user_lang if user_lang in ("pt-PT", "pt-BR", "es", "en") else "en"
                        conf = preferred_name_confirmation(lang_key, name_to_save)
                        session.add_message("user", msg.content)
                        session.add_message("assistant", conf)
                        self.sessions.save(session)
                        db.close()
                        return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=conf)

                    # Já tem fuso definido (e não estamos à espera do nome) → não bloquear
                    if has_tz_set:
                        pass  # fall through to handlers
                    else:
                        nudge_count = session.metadata.get("onboarding_nudge_count", 0)
                        # Retry gradual: após 2 mensagens sem responder à pergunta de fuso, perguntar «que horas são aí?»
                        if intro_sent and not pending_timezone and not pending_time_confirm and nudge_count >= 2:
                            ask = ONBOARDING_ASK_TIME_FALLBACK.get(user_lang, ONBOARDING_ASK_TIME_FALLBACK["en"])
                            session.metadata["pending_timezone"] = True
                            session.metadata["onboarding_nudge_count"] = 0
                            self.sessions.save(session)
                            session.add_message("user", msg.content)
                            session.add_message("assistant", ask)
                            self.sessions.save(session)
                            db.close()
                            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=ask)
                        # --- 1. Primeira mensagem: intro + pergunta única (cidade ou hora) ---
                        if not intro_sent:
                            intro = ONBOARDING_INTRO_TZ_FIRST.get(intro_lang, ONBOARDING_INTRO_TZ_FIRST["en"])
                            ask = ONBOARDING_ASK_CITY_OR_TIME.get(intro_lang, ONBOARDING_ASK_CITY_OR_TIME["en"])
                            full_msg = intro + "\n\n" + ask
                            session.metadata["onboarding_intro_sent"] = True
                            session.metadata["pending_timezone"] = True
                            self.sessions.save(session)
                            session.add_message("user", msg.content)
                            session.add_message("assistant", full_msg)
                            self.sessions.save(session)
                            db.close()
                            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=full_msg)

                        # --- 2. Resposta à confirmação «Ah, data, hora. Confere?» — confirmar ou atribuir mesmo assim ---
                        if pending_time_confirm and not (msg.content or "").strip().startswith("/"):
                            content_stripped = (msg.content or "").strip().lower()
                            confirmado = any(w in content_stripped for w in ("sim", "sí", "si", "yes", "ok", "confere", "confirmo", "certo", "isso", "é", "correto", "correto."))
                            recusado = any(w in content_stripped for w in ("não", "nao", "no ", "no.", "errado", "incorreto"))
                            proposed_tz = session.metadata.get("proposed_tz_iana")
                            if recusado and proposed_tz:
                                session.metadata.pop("pending_time_confirm", None)
                                session.metadata.pop("proposed_tz_iana", None)
                                session.metadata.pop("proposed_date_str", None)
                                session.metadata.pop("proposed_time_str", None)
                                session.metadata["pending_timezone"] = True
                                self.sessions.save(session)
                                # Perguntar de novo (hora ou cidade)
                                ask = ONBOARDING_ASK_TIME_FALLBACK.get(user_lang, ONBOARDING_ASK_TIME_FALLBACK["en"])
                                session.add_message("user", msg.content)
                                session.add_message("assistant", ask)
                                self.sessions.save(session)
                                db.close()
                                return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=ask)
                            if (confirmado or proposed_tz) and proposed_tz and is_valid_iana(proposed_tz):
                                set_user_timezone(db, msg.chat_id, proposed_tz)
                                session.metadata.pop("pending_time_confirm", None)
                                session.metadata.pop("pending_timezone", None)
                                session.metadata.pop("proposed_tz_iana", None)
                                session.metadata.pop("proposed_date_str", None)
                                session.metadata.pop("proposed_time_str", None)
                                self._sync_onboarding_to_memory(db, msg.chat_id, msg.session_key)
                                self.sessions.save(session)
                                complete_msg = ONBOARDING_TZ_SET_FROM_TIME.get(user_lang, ONBOARDING_TZ_SET_FROM_TIME["en"])
                                complete_msg += "\n\n" + ONBOARDING_COMPLETE.get(user_lang, ONBOARDING_COMPLETE["en"])
                                complete_msg += ONBOARDING_DAILY_USE_APPEAL.get(user_lang, ONBOARDING_DAILY_USE_APPEAL["en"])
                                complete_msg += ONBOARDING_EMOJI_TIP.get(user_lang, ONBOARDING_EMOJI_TIP["en"])
                                complete_msg += ONBOARDING_RESET_HINT.get(user_lang, ONBOARDING_RESET_HINT["en"])
                                name_q = PREFERRED_NAME_QUESTION.get(user_lang, PREFERRED_NAME_QUESTION["en"])
                                complete_msg += "\n\n" + name_q
                                session.metadata["pending_preferred_name"] = True
                                session.add_message("user", msg.content)
                                session.add_message("assistant", complete_msg)
                                self.sessions.save(session)
                                db.close()
                                return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=complete_msg)
                            # Sem confirmação explícita: atribuir mesmo assim (pedido do produto)
                            if proposed_tz and is_valid_iana(proposed_tz):
                                set_user_timezone(db, msg.chat_id, proposed_tz)
                                session.metadata.pop("pending_time_confirm", None)
                                session.metadata.pop("pending_timezone", None)
                                session.metadata.pop("proposed_tz_iana", None)
                                session.metadata.pop("proposed_date_str", None)
                                session.metadata.pop("proposed_time_str", None)
                                self._sync_onboarding_to_memory(db, msg.chat_id, msg.session_key)
                                self.sessions.save(session)
                                complete_msg = ONBOARDING_TZ_SET_FROM_TIME.get(user_lang, ONBOARDING_TZ_SET_FROM_TIME["en"])
                                complete_msg += "\n\n" + ONBOARDING_COMPLETE.get(user_lang, ONBOARDING_COMPLETE["en"])
                                complete_msg += ONBOARDING_DAILY_USE_APPEAL.get(user_lang, ONBOARDING_DAILY_USE_APPEAL["en"])
                                complete_msg += ONBOARDING_EMOJI_TIP.get(user_lang, ONBOARDING_EMOJI_TIP["en"])
                                complete_msg += ONBOARDING_RESET_HINT.get(user_lang, ONBOARDING_RESET_HINT["en"])
                                name_q = PREFERRED_NAME_QUESTION.get(user_lang, PREFERRED_NAME_QUESTION["en"])
                                complete_msg += "\n\n" + name_q
                                session.metadata["pending_preferred_name"] = True
                                session.add_message("user", msg.content)
                                session.add_message("assistant", complete_msg)
                                self.sessions.save(session)
                                db.close()
                                return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=complete_msg)

                        # --- 3. Resposta à pergunta cidade/hora (pending_timezone): tentar cidade ou hora ---
                        if pending_timezone and not pending_time_confirm and not (msg.content or "").strip().startswith("/"):
                            content_stripped = (msg.content or "").strip()
                            # 3a. Tentar interpretar como cidade
                            if content_stripped and not is_likely_not_city(content_stripped):
                                city_name, tz_iana = await self._extract_city_and_timezone_with_mimo(content_stripped)
                                if city_name and tz_iana and is_valid_iana(tz_iana):
                                    set_user_city(db, msg.chat_id, city_name, tz_iana=tz_iana)
                                    session.metadata.pop("pending_timezone", None)
                                    self._sync_onboarding_to_memory(db, msg.chat_id, msg.session_key)
                                    self.sessions.save(session)
                                    complete_msg = ONBOARDING_COMPLETE.get(user_lang, ONBOARDING_COMPLETE["en"])
                                    complete_msg += ONBOARDING_DAILY_USE_APPEAL.get(user_lang, ONBOARDING_DAILY_USE_APPEAL["en"])
                                    complete_msg += ONBOARDING_EMOJI_TIP.get(user_lang, ONBOARDING_EMOJI_TIP["en"])
                                    complete_msg += ONBOARDING_RESET_HINT.get(user_lang, ONBOARDING_RESET_HINT["en"])
                                    name_q = PREFERRED_NAME_QUESTION.get(user_lang, PREFERRED_NAME_QUESTION["en"])
                                    complete_msg += "\n\n" + name_q
                                    session.metadata["pending_preferred_name"] = True
                                    session.add_message("user", msg.content)
                                    session.add_message("assistant", complete_msg)
                                    self.sessions.save(session)
                                    db.close()
                                    return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=complete_msg)
                            # 3b. Tentar interpretar como hora («que horas são aí?»)
                            parsed = parse_local_time_from_message(content_stripped)
                            if parsed:
                                h, m = parsed
                                now_utc = datetime.now(ZoneInfo("UTC"))
                                utc_minutes = now_utc.hour * 60 + now_utc.minute
                                user_minutes = h * 60 + m
                                offset_minutes = user_minutes - utc_minutes
                                # Ajustar se diferença > 12h (provável outro dia)
                                if offset_minutes > 12 * 60:
                                    offset_minutes -= 24 * 60
                                elif offset_minutes < -12 * 60:
                                    offset_minutes += 24 * 60
                                tz_iana = iana_from_offset_minutes(offset_minutes)
                                if is_valid_iana(tz_iana):
                                    z = ZoneInfo(tz_iana)
                                    today = datetime.now(z).date()
                                    date_str = today.strftime("%d/%m") if hasattr(today, "strftime") else str(today)
                                    time_str = f"{h:02d}:{m:02d}"
                                    confirm_msg = onboarding_time_confirm_message(
                                        user_lang if user_lang in ("pt-PT", "pt-BR", "es", "en") else "en",
                                        date_str,
                                        time_str,
                                    )
                                    session.metadata["pending_time_confirm"] = True
                                    session.metadata["proposed_tz_iana"] = tz_iana
                                    session.metadata["proposed_date_str"] = date_str
                                    session.metadata["proposed_time_str"] = time_str
                                    session.metadata.pop("pending_timezone", None)
                                    self.sessions.save(session)
                                    session.add_message("user", msg.content)
                                    session.add_message("assistant", confirm_msg)
                                    self.sessions.save(session)
                                    db.close()
                                    return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=confirm_msg)
                            # 3c. Não é cidade nem hora → não bloquear; deixar seguir para handlers e retry depois
                            session.metadata.pop("pending_timezone", None)
                            session.metadata["onboarding_nudge_count"] = nudge_count + 1
                            self.sessions.save(session)
                finally:
                    db.close()
            except Exception as e:
                logger.debug(f"Onboarding (timezone) flow failed: {e}")

        # Handlers de comandos (README: /lembrete, /list, /feito, /add, /done, /start, etc.)
        # Confirmações sem botões: 1=sim 2=não. TODO: Após WhatsApp Business API, use buttons.
        try:
            from backend.handler_context import HandlerContext
            from backend.router import route as handlers_route
            from backend.handlers import handle_list as handle_list_fn
            from backend.command_parser import parse as parse_cmd
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
            # Listas: tratar primeiro para não cair no LLM (evita "sistema de listas com erro" por histórico)
            intent = None
            try:
                intent = parse_cmd(msg.content)
            except Exception as e:
                logger.debug("parse_cmd failed (using fallback): %s", e)
            if intent and intent.get("type") in ("list_add", "list_show") and ctx.list_tool:
                try:
                    result = await handle_list_fn(ctx, msg.content)
                    if result is not None:
                        logger.info("List intent handled early: type=%s list_name=%s", intent.get("type"), intent.get("list_name"))
                        try:
                            from backend.database import SessionLocal as _DB
                            _db = _DB()
                            try:
                                self._write_client_memory_file(_db, msg.chat_id)
                            finally:
                                _db.close()
                        except Exception:
                            pass
                        if isinstance(result, list):
                            for part in result[1:]:
                                await self.bus.publish_outbound(OutboundMessage(
                                    channel=msg.channel, chat_id=msg.chat_id, content=part,
                                ))
                            result = result[0]
                        try:
                            from backend.database import SessionLocal as _DB
                            from backend.user_store import get_or_create_user as _get_user, get_user_language as _get_lang
                            from backend.locale import NUDGE_TZ_WHEN_MISSING
                            _db = _DB()
                            try:
                                _u = _get_user(_db, msg.chat_id)
                                if not (_u.timezone and _u.timezone.strip()):
                                    _s = self.sessions.get_or_create(msg.session_key)
                                    if _s.metadata.get("onboarding_intro_sent") and _s.metadata.get("nudge_append_done") != True:
                                        _s.metadata["nudge_append_done"] = True
                                        self.sessions.save(_s)
                                        _lang = _get_lang(_db, msg.chat_id) or "en"
                                        result = result + "\n\n" + NUDGE_TZ_WHEN_MISSING.get(_lang, NUDGE_TZ_WHEN_MISSING["en"])
                            finally:
                                _db.close()
                        except Exception:
                            pass
                        try:
                            session = self.sessions.get_or_create(msg.session_key)
                            session.add_message("user", msg.content)
                            session.add_message("assistant", result)
                            self.sessions.save(session)
                            asyncio.create_task(self._maybe_sentiment_check(session, msg.channel, msg.chat_id))
                        except Exception:
                            pass
                        return OutboundMessage(
                            channel=msg.channel, chat_id=msg.chat_id, content=result, metadata=dict(msg.metadata or {}),
                        )
                except Exception as e:
                    logger.warning("Early list handle failed (falling through): %s", e)
            # Fallback: regex local "cria/faça/mostre lista de X" sem depender do backend (funciona mesmo com backend antigo)
            if ctx.list_tool and msg.content and (not intent or intent.get("type") not in ("list_add", "list_show")):
                t = (msg.content or "").strip()
                m = re.match(
                    r"^(?i)(?:cria|crie|faça|faz|mostre|mostra|exiba|me\s+d[êe]|de-me|dê-me|crea|haz|dame|muéstrame|muestra|create|make|give\s+me|show\s+me|show|display)\s+"
                    r"(?:uma\s+|una\s+|a\s+)?(?:lista|list)\s+(?:de\s+|of\s+)?(\w+)\s*(.*)$",
                    t,
                )
                if m:
                    list_name = m.group(1).strip().lower()
                    item = (m.group(2) or "").strip() or "—"
                    _norm = {"livros": "livro", "filmes": "filme", "receitas": "receita", "musicas": "musica", "compras": "mercado", "books": "livro", "movies": "filme", "recipes": "receita"}
                    list_name = _norm.get(list_name, list_name)
                    try:
                        ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
                        result = await ctx.list_tool.execute(action="add", list_name=list_name, item_text=item)
                        if result:
                            logger.info("List intent handled via fallback regex: list_name=%s", list_name)
                            try:
                                from backend.database import SessionLocal as _DB
                                _db = _DB()
                                try:
                                    self._write_client_memory_file(_db, msg.chat_id)
                                finally:
                                    _db.close()
                            except Exception:
                                pass
                            if isinstance(result, list):
                                for part in result[1:]:
                                    await self.bus.publish_outbound(OutboundMessage(
                                        channel=msg.channel, chat_id=msg.chat_id, content=part,
                                    ))
                                result = result[0]
                            try:
                                from backend.database import SessionLocal as _DB
                                from backend.user_store import get_or_create_user as _get_user, get_user_language as _get_lang
                                from backend.locale import NUDGE_TZ_WHEN_MISSING
                                _db = _DB()
                                try:
                                    _u = _get_user(_db, msg.chat_id)
                                    if not (_u.timezone and _u.timezone.strip()):
                                        _s = self.sessions.get_or_create(msg.session_key)
                                        if _s.metadata.get("onboarding_intro_sent") and _s.metadata.get("nudge_append_done") != True:
                                            _s.metadata["nudge_append_done"] = True
                                            self.sessions.save(_s)
                                            _lang = _get_lang(_db, msg.chat_id) or "en"
                                            result = result + "\n\n" + NUDGE_TZ_WHEN_MISSING.get(_lang, NUDGE_TZ_WHEN_MISSING["en"])
                                finally:
                                    _db.close()
                            except Exception:
                                pass
                            try:
                                session = self.sessions.get_or_create(msg.session_key)
                                session.add_message("user", msg.content)
                                session.add_message("assistant", result)
                                self.sessions.save(session)
                                asyncio.create_task(self._maybe_sentiment_check(session, msg.channel, msg.chat_id))
                            except Exception:
                                pass
                            return OutboundMessage(
                                channel=msg.channel, chat_id=msg.chat_id, content=result, metadata=dict(msg.metadata or {}),
                            )
                    except Exception as e:
                        logger.warning("Fallback list handle failed: %s", e)
            result = await handlers_route(ctx, msg.content)
            if result is not None:
                # Atualizar ficheiro de memória do cliente (ex.: /lang, /tz alteram dados na BD)
                try:
                    from backend.database import SessionLocal as _DB
                    _db = _DB()
                    try:
                        self._write_client_memory_file(_db, msg.chat_id)
                    finally:
                        _db.close()
                except Exception:
                    pass
                # Handler pode devolver lista (ex.: /help = [texto principal, comandos slash]) → enviar extras em mensagens separadas
                if isinstance(result, list):
                    for part in result[1:]:
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=part,
                        ))
                    result = result[0]
                # Nudge suave quando falta fuso (máx 1x por sessão para não incomodar)
                try:
                    from backend.database import SessionLocal as _DB
                    from backend.user_store import get_or_create_user as _get_user, get_user_language as _get_lang
                    from backend.locale import NUDGE_TZ_WHEN_MISSING
                    _db = _DB()
                    try:
                        _u = _get_user(_db, msg.chat_id)
                        if not (_u.timezone and _u.timezone.strip()):
                            _s = self.sessions.get_or_create(msg.session_key)
                            if _s.metadata.get("onboarding_intro_sent") and _s.metadata.get("nudge_append_done") != True:
                                _s.metadata["nudge_append_done"] = True
                                self.sessions.save(_s)
                                _lang = _get_lang(_db, msg.chat_id) or "en"
                                result = result + "\n\n" + NUDGE_TZ_WHEN_MISSING.get(_lang, NUDGE_TZ_WHEN_MISSING["en"])
                    finally:
                        _db.close()
                except Exception:
                    pass
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
                    metadata=dict(msg.metadata or {}),
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
                metadata=dict(msg.metadata or {}),
            )

        # Escolha de modelo: Mimo se (1) muita lógica/raciocínio (cálculos, otimizações, conflitos),
        # (2) pedidos de análise de histórico, (3) velocidade crítica (alto volume). Caso contrário → DeepSeek.
        try:
            from backend.handler_context import HandlerContext
            from backend.llm_handlers import is_analytical_message, handle_analytics
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
                        metadata=dict(msg.metadata or {}),
                    )
        except Exception as e:
            logger.debug(f"Analytics (Mimo) pre-agent check failed: {e}")

        # Circuit open: skip LLM, return degraded message (parser already ran above)
        if self.circuit_breaker.is_open():
            logger.warning("Circuit breaker open: responding in degraded mode (parser-only)")
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="Serviço temporariamente limitado. Digite /help para ver a lista de comandos.",
                metadata=dict(msg.metadata or {}),
            )

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {preview}")

        # Conversacional: agente principal (DeepSeek)
        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)

        # Resumo automático: se convo longa (>=45 msgs), condensa via Mimo e guarda em MEMORY.md
        await self._maybe_compress_session(session, msg.session_key)

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
        used_fallback = False  # Para tentar scope_provider (Mimo) como fallback

        while iteration < self.max_iterations:
            iteration += 1

            # Call LLM (main provider); fallback para scope_provider (Mimo) em erro
            response = None
            try:
                response = await self.provider.chat(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=self.model,
                    profile="assistant",
                )
                # LiteLLM retorna conteúdo de erro em vez de levantar
                is_error = (
                    response
                    and (response.content or "").strip().lower().startswith("error calling llm")
                )
                if is_error:
                    raise RuntimeError(response.content or "LLM error")
                self.circuit_breaker.record_success()
            except Exception as e:
                self.circuit_breaker.record_failure()
                logger.warning(f"LLM call failed: {e}")
                # Fallback: tentar scope_provider (Mimo) se disponível e ainda não usado
                if (
                    not used_fallback
                    and self.scope_provider
                    and (self.scope_model or "").strip()
                ):
                    used_fallback = True
                    logger.info("Retrying with fallback provider (scope_model)")
                    try:
                        response = await self.scope_provider.chat(
                            messages=messages,
                            tools=self.tools.get_definitions(),
                            model=self.scope_model,
                            profile="assistant",
                        )
                        if response and (response.content or "").strip().lower().startswith("error calling llm"):
                            response = None
                        else:
                            self.circuit_breaker.record_success()
                    except Exception as e2:
                        logger.warning(f"Fallback provider also failed: {e2}")
                        response = None
                if not response:
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content="Serviço temporariamente indisponível. Digite /help para ver a lista de comandos.",
                        metadata=dict(msg.metadata or {}),
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
        
        if not (final_content or "").strip():
            from backend.locale import AGENT_NO_RESPONSE_FALLBACK
            final_content = AGENT_NO_RESPONSE_FALLBACK.get(
                user_lang or "pt-BR", AGENT_NO_RESPONSE_FALLBACK["pt-BR"]
            )
        
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
            content=final_content,
            metadata=dict(msg.metadata or {}),
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
