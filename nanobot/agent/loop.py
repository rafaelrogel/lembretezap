"""Agent loop: the core processing engine."""

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.context import ContextBuilder
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.list_tool import ListTool
from nanobot.agent.tools.event_tool import EventTool
from nanobot.session.manager import SessionManager


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
        max_iterations: int = 20,
        cron_service: "CronService | None" = None,
    ):
        from nanobot.cron.service import CronService
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.cron_service = cron_service
        
        self.context = ContextBuilder(workspace)
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        
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

    async def _execute_parsed_intent(self, intent: dict, msg: InboundMessage) -> str | None:
        """Executa intent do parser (cron, list, event). Retorna texto da resposta ou None para seguir ao LLM."""
        cron_tool = self.tools.get("cron")
        list_tool = self.tools.get("list")
        event_tool = self.tools.get("event")
        if cron_tool and isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)
        if list_tool and isinstance(list_tool, ListTool):
            list_tool.set_context(msg.channel, msg.chat_id)
        if event_tool and isinstance(event_tool, EventTool):
            event_tool.set_context(msg.channel, msg.chat_id)

        t = intent.get("type")
        if t == "lembrete":
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
            if not event_tool:
                return None
            return await event_tool.execute(action="add", tipo="filme", nome=intent.get("nome", ""))
        return None

    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
        
        Returns:
            The response message, or None if no response needed.
        """
        # Rate limit per user (channel:chat_id)
        try:
            from backend.rate_limit import is_rate_limited
            if is_rate_limited(msg.channel, msg.chat_id):
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="Muitas mensagens. Aguarde um minuto antes de enviar de novo.",
                )
        except Exception:
            pass

        # Parser de comandos: execução direta sem LLM
        try:
            from backend.command_parser import parse
            intent = parse(msg.content)
            if intent:
                result = await self._execute_parsed_intent(intent, msg)
                if result is not None:
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=result,
                    )
        except Exception as e:
            logger.debug(f"Command parse/execute failed: {e}")

        # Scope filter: LLM SIM/NAO (fallback: regex)
        try:
            from backend.scope_filter import is_in_scope_fast, is_in_scope_llm
            in_scope = await is_in_scope_llm(
                msg.content,
                provider=self.provider,
                model=self.model,
            )
            if not in_scope:
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="Sou só seu organizador: lembretes, listas e eventos. Envie /lembrete, /list ou /filme.",
                )
        except Exception:
            try:
                from backend.scope_filter import is_in_scope_fast
                if not is_in_scope_fast(msg.content):
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content="Sou só seu organizador: lembretes, listas e eventos. Envie /lembrete, /list ou /filme.",
                    )
            except Exception:
                pass
        
        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {preview}")
        
        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)
        list_tool = self.tools.get("list")
        if isinstance(list_tool, ListTool):
            list_tool.set_context(msg.channel, msg.chat_id)
        event_tool = self.tools.get("event")
        if isinstance(event_tool, EventTool):
            event_tool.set_context(msg.channel, msg.chat_id)
        
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
            
            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
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
            content=content
        )
        
        response = await self._process_message(msg)
        return response.content if response else ""
