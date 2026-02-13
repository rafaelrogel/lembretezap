"""WhatsApp channel implementation using Node.js bridge.

We only handle private chats. We never respond in groups: messages from groups
are ignored and not forwarded to the agent.
Deduplicação por message_id evita processar o mesmo evento várias vezes (bridge/Baileys pode reenviar).
"""

import asyncio
import json
import time
import uuid
from typing import Any

from loguru import logger

from zapista.bus.events import OutboundMessage
from zapista.bus.queue import MessageBus
from zapista.channels.base import BaseChannel
from zapista.config.schema import WhatsAppConfig

# JID suffix for WhatsApp groups; we only process chats (e.g. @s.whatsapp.net or LID), never groups
WHATSAPP_GROUP_SUFFIX = "@g.us"

# Dedup: ignorar mensagens com o mesmo message_id já processado nos últimos N segundos
_DEDUP_SECONDS = 120
_processed_ids: dict[str, float] = {}
# Fallback quando o bridge não envia id: dedup por (chat_id, conteúdo, janela 30s)
_processed_fallback: dict[tuple[str, str, int], float] = {}
_FALLBACK_BUCKET_SECONDS = 30


def _is_duplicate_message(msg_id: str) -> bool:
    """True se esta mensagem já foi processada recentemente (evita chamadas LLM duplicadas)."""
    if not msg_id:
        return False
    now = time.time()
    to_del = [k for k, t in _processed_ids.items() if now - t > _DEDUP_SECONDS]
    for k in to_del:
        del _processed_ids[k]
    if msg_id in _processed_ids:
        return True
    _processed_ids[msg_id] = now
    return False


def _is_duplicate_by_content(chat_id: str, content: str) -> bool:
    """Fallback quando não há message_id: mesmo chat + mesmo texto na mesma janela = duplicado."""
    if not content and not chat_id:
        return False
    now = time.time()
    bucket = int(now / _FALLBACK_BUCKET_SECONDS)
    key = (chat_id, content.strip()[:200], bucket)
    to_del = [k for k, t in _processed_fallback.items() if now - t > _DEDUP_SECONDS]
    for k in to_del:
        del _processed_fallback[k]
    if key in _processed_fallback:
        return True
    _processed_fallback[key] = now
    return False


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp channel that connects to a Node.js bridge.
    Chats only: we respond in private chats and never in groups.
    The bridge uses @whiskeysockets/baileys; communication is via WebSocket.
    """
    
    name = "whatsapp"
    
    def __init__(self, config: WhatsAppConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: WhatsAppConfig = config
        self._ws = None
        self._connected = False
        self._cron_tool = None  # opcional: para lembretes 15 min antes de eventos .ics
        self._cron_service = None  # para remover job ao reagir com emoji positivo
        self._restart_executor = None  # (channel, chat_id) -> awaitable; injetado pelo gateway
        self._pending_sends: dict[str, asyncio.Future] = {}

    def set_restart_executor(self, executor) -> None:
        """Injetar função async execute_restart(channel, chat_id) para o comando /restart."""
        self._restart_executor = executor

    def set_ics_cron_tool(self, cron_tool) -> None:
        """Injetar CronTool para criar lembretes 15 min antes de cada evento ao importar .ics."""
        self._cron_tool = cron_tool

    def set_cron_service(self, cron_service: Any) -> None:
        """Injetar CronService para remover job ao reagir com emoji positivo."""
        self._cron_service = cron_service

    async def start(self) -> None:
        """Start the WhatsApp channel by connecting to the bridge."""
        import websockets
        
        bridge_url = self.config.bridge_url
        
        logger.info(f"Connecting to WhatsApp bridge at {bridge_url}...")
        
        self._running = True
        
        while self._running:
            try:
                async with websockets.connect(bridge_url) as ws:
                    self._ws = ws
                    is_reconnect = getattr(self, "_has_ever_connected", False)
                    self._connected = True
                    self._has_ever_connected = True
                    if is_reconnect:
                        try:
                            from backend.server_metrics import record_event
                            record_event("bridge_reconnect")
                        except Exception:
                            pass
                    logger.info("Connected to WhatsApp bridge")
                    
                    # Listen for messages
                    async for message in ws:
                        try:
                            await self._handle_bridge_message(message)
                        except Exception as e:
                            logger.error(f"Error handling bridge message: {e}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._ws = None
                logger.warning(f"WhatsApp bridge connection error: {e}")
                
                if self._running:
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)
    
    async def stop(self) -> None:
        """Stop the WhatsApp channel."""
        self._running = False
        self._connected = False
        
        if self._ws:
            await self._ws.close()
            self._ws = None
    
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through WhatsApp."""
        if not self._ws or not self._connected:
            logger.warning("WhatsApp send skipped: bridge not connected")
            try:
                from backend.server_metrics import record_event
                record_event("whatsapp_skipped")
            except Exception:
                pass
            return

        job_id = (msg.metadata or {}).get("job_id") if msg.metadata else None
        request_id = str(uuid.uuid4()) if job_id else None
        try:
            payload: dict[str, Any] = {
                "type": "send",
                "to": msg.chat_id,
                "text": msg.content,
            }
            if job_id:
                payload["job_id"] = job_id
            if request_id:
                payload["request_id"] = request_id

            future = None
            if request_id:
                future = asyncio.get_running_loop().create_future()
                self._pending_sends[request_id] = future

            logger.info(f"WhatsApp send: to={str(msg.chat_id)[:30]}... len={len(msg.content)}")
            await self._ws.send(json.dumps(payload))

            if future and job_id:
                try:
                    result = await asyncio.wait_for(future, timeout=10.0)
                    msg_id = result.get("id") if isinstance(result, dict) else None
                    if msg_id:
                        try:
                            from backend.database import SessionLocal
                            from backend.reminder_reaction import store_sent_mapping
                            db = SessionLocal()
                            try:
                                store_sent_mapping(db, msg.chat_id, msg_id, job_id)
                            finally:
                                db.close()
                        except Exception as e:
                            logger.debug(f"Store sent mapping failed: {e}")
                except asyncio.TimeoutError:
                    logger.debug("WhatsApp send: no sent confirmation within 10s")
                finally:
                    self._pending_sends.pop(request_id, None)
        except Exception as e:
            self._pending_sends.pop(request_id, None) if request_id else None
            logger.error(f"Error sending WhatsApp message: {e}")
    
    async def _handle_bridge_message(self, raw: str) -> None:
        """Handle a message from the bridge."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from bridge: {raw[:100]}")
            return
        
        msg_type = data.get("type")

        if msg_type == "sent":
            req_id = data.get("request_id")
            if req_id and req_id in self._pending_sends:
                fut = self._pending_sends.pop(req_id, None)
                if fut and not fut.done():
                    fut.set_result({"id": data.get("id"), "job_id": data.get("job_id")})
            return

        if msg_type == "reaction":
            await self._handle_reaction(data)
            return

        if msg_type == "message":
            # Evitar processar o mesmo evento várias vezes (reduz chamadas LLM duplicadas)
            msg_id = (data.get("id") or "").strip()
            redis_url = getattr(self.bus, "redis_url", None) if self.bus else None
            if msg_id and redis_url:
                try:
                    from zapista.bus.redis_queue import is_inbound_duplicate_or_record
                    if await is_inbound_duplicate_or_record(redis_url, msg_id):
                        logger.debug(f"Ignoring duplicate message id={msg_id!r}")
                        return
                except Exception as e:
                    logger.debug(f"Redis dedup failed, fallback to memory: {e}")
                    if _is_duplicate_message(msg_id):
                        return
            elif _is_duplicate_message(msg_id):
                logger.debug(f"Ignoring duplicate message id={msg_id!r}")
                return

            # Incoming message from WhatsApp — we only process chats, never groups
            is_group = data.get("isGroup", False) or (data.get("sender") or "").strip().endswith(WHATSAPP_GROUP_SUFFIX)
            if is_group:
                logger.debug("Ignoring message from group (we only respond in private chats)")
                return

            # Deprecated by whatsapp: old phone number style typically: <phone>@s.whatsapp.net
            pn = data.get("pn", "")
            # New LID style typically:
            sender = data.get("sender", "")
            content = data.get("content", "")

            # Fallback dedup quando o bridge não envia id: mesmo chat + mesmo texto em 30s = ignorar
            if not msg_id and _is_duplicate_by_content(sender, content or ""):
                logger.debug(f"Ignoring duplicate by content from {sender[:20]}...")
                return

            # Extract just the phone number or lid as chat_id
            user_id = pn if pn else sender
            sender_id = user_id.split("@")[0] if "@" in user_id else user_id
            # Se um tester não receber resposta, ver nos logs este valor e adiciona-o a allow_from no config
            logger.info(f"WhatsApp from sender={sender!r} → sender_id={sender_id!r} (use na allow_from se bloqueado)")

            # Handle voice transcription if it's a voice message
            if content == "[Voice Message]":
                logger.info(f"Voice message received from {sender_id}, but direct download from bridge is not yet supported.")
                content = "[Voice Message: Transcription not available for WhatsApp yet]"

            # Anexo .ics: parse e registar eventos (sem passar ao agente)
            attachment_ics = data.get("attachmentIcs") or data.get("attachment_ics")
            if attachment_ics and isinstance(attachment_ics, str) and attachment_ics.strip():
                from zapista.bus.events import OutboundMessage
                try:
                    from backend.ics_handler import handle_ics_payload
                    from backend.database import SessionLocal
                    response = await handle_ics_payload(
                        chat_id=sender,
                        sender_id=sender_id,
                        ics_content=attachment_ics.strip(),
                        db_session_factory=SessionLocal,
                        cron_tool=getattr(self, "_cron_tool", None),
                        cron_channel=self.name,
                    )
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content=response or "—",
                    ))
                except Exception as e:
                    logger.exception(f"ICS handler failed: {e}")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content="Erro ao processar o calendário. Tenta outro ficheiro .ics.",
                    ))
                return

            # God Mode: #<senha> ativa; #cmd só se já ativou. Senha errada ou #inválido = silêncio.
            if (content or "").strip().startswith("#"):
                from backend.admin_commands import (
                    is_god_mode_password,
                    is_god_mode_activated,
                    activate_god_mode,
                    deactivate_god_mode,
                    parse_admin_command_arg,
                    handle_admin_command,
                )
                from backend.god_mode_lockout import (
                    is_locked_out,
                    record_failed_attempt,
                    clear_failed_attempts,
                )
                from zapista.bus.events import OutboundMessage
                from zapista.utils.muted_store import apply_mute
                raw = (content or "").strip()
                rest = raw[1:].strip()  # texto após #
                if is_locked_out(sender):
                    return  # bloqueado por tentativas erradas; silêncio
                if is_god_mode_password(rest):
                    clear_failed_attempts(sender)
                    activate_god_mode(sender)
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content="God-mode ativo. Comandos: #status #users #cron #add #remove #mute #quit ...",
                    ))
                    return
                cmd, arg = parse_admin_command_arg(raw)
                if not cmd or not is_god_mode_activated(sender):
                    if not cmd and rest:
                        record_failed_attempt(sender)
                    return  # silêncio
                # #quit: desativar god-mode
                if cmd == "quit":
                    deactivate_god_mode(sender)
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content="God-mode desativado.",
                    ))
                    return
                # #mute <número>: aplicar punição e enviar mensagem ao utilizador
                if cmd == "mute":
                    if not arg.strip():
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=sender,
                            content="#mute\nUso: #mute <número de telefone>",
                        ))
                        return
                    user_msg, count, admin_msg = apply_mute(arg)
                    # Enviar ao utilizador muted (JID = número@s.whatsapp.net para o bridge)
                    phone_digits = "".join(c for c in str(arg) if c.isdigit())
                    if phone_digits and user_msg:
                        chat_id_user = f"{phone_digits}@s.whatsapp.net" if "@" not in str(arg) else str(arg).strip()
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=chat_id_user,
                            content=user_msg,
                        ))
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content=admin_msg,
                    ))
                    return
                # Resto (#add, #remove, #status, ...): handle_admin_command
                try:
                    from backend.database import SessionLocal
                    from zapista.config.loader import get_data_dir
                    cron_store_path = get_data_dir() / "cron" / "jobs.json"
                    response = await handle_admin_command(
                        raw,
                        db_session_factory=SessionLocal,
                        cron_store_path=cron_store_path,
                        wa_channel=self,
                    )
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content=response or "—",
                    ))
                except Exception as e:
                    logger.exception(f"Admin command failed: {e}")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content="Erro ao executar comando admin.",
                    ))
                return

            # /restart: confirmação dupla (sim/não) e depois execução do reset
            from zapista.utils.restart_flow import (
                get_restart_stage,
                set_restart_stage,
                clear_restart_stage,
                MSG_FIRST,
                MSG_SECOND,
                MSG_CANCELLED,
                MSG_DONE,
                is_confirm_reply,
                is_confirm_no,
                run_restart,
            )
            raw_content = (content or "").strip()
            is_restart_cmd = raw_content.lower() in ("/restart", "restart")
            stage = get_restart_stage(self.name, sender)
            if is_restart_cmd and not stage:
                set_restart_stage(self.name, sender, "1")
                await self.bus.publish_outbound(OutboundMessage(
                    channel=self.name,
                    chat_id=sender,
                    content=MSG_FIRST,
                ))
                return
            if stage and is_confirm_reply(raw_content):
                if is_confirm_no(raw_content):
                    clear_restart_stage(self.name, sender)
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content=MSG_CANCELLED,
                    ))
                    return
                if stage == "1":
                    set_restart_stage(self.name, sender, "2")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content=MSG_SECOND,
                    ))
                    return
                if stage == "2":
                    clear_restart_stage(self.name, sender)
                    if self._restart_executor:
                        try:
                            await self._restart_executor(self.name, sender)
                        except Exception as e:
                            logger.exception(f"Restart executor failed: {e}")
                            await self.bus.publish_outbound(OutboundMessage(
                                channel=self.name,
                                chat_id=sender,
                                content="Erro ao reiniciar. Tenta de novo ou contacta o suporte.",
                            ))
                            return
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content=MSG_DONE,
                    ))
                    return
            if stage:
                # Continua à espera de sim/não; ignorar outras mensagens ou repetir o aviso
                return

            # Forward to agent only for private chats (groups already filtered above)
            trace_id = uuid.uuid4().hex[:12]
            await self._handle_message(
                sender_id=sender_id,
                chat_id=sender,  # Use full JID/LID for replies
                content=content,
                metadata={
                    "message_id": data.get("id"),
                    "timestamp": data.get("timestamp"),
                    "is_group": False,
                    "trace_id": trace_id,
                },
            )
        
        elif msg_type == "status":
            # Connection status update
            status = data.get("status")
            logger.info(f"WhatsApp status: {status}")
            
            if status == "connected":
                self._connected = True
            elif status == "disconnected":
                self._connected = False
        
        elif msg_type == "qr":
            # QR code for authentication
            logger.info("Scan QR code in the bridge terminal to connect WhatsApp")
        
        elif msg_type == "error":
            logger.error(f"WhatsApp bridge error: {data.get('error')}")

    async def _handle_reaction(self, data: dict) -> None:
        """Trata reação em mensagem: emoji positivo = feito (remove job); negativo = perguntar reagendar."""
        if data.get("fromMe"):
            return
        chat_id = (data.get("chatId") or "").strip()
        message_id = (data.get("messageId") or "").strip()
        emoji = (data.get("emoji") or "").strip()
        if not chat_id or not message_id:
            return
        if chat_id.endswith(WHATSAPP_GROUP_SUFFIX):
            return
        try:
            from backend.database import SessionLocal
            from backend.reminder_reaction import (
                lookup_job_by_message,
                is_positive_emoji,
                is_negative_emoji,
                is_snooze_emoji,
            )
            db = SessionLocal()
            try:
                job_id = lookup_job_by_message(db, chat_id, message_id)
            finally:
                db.close()
            if not job_id:
                return
            if is_positive_emoji(emoji):
                completed_job_id = job_id
                if self._cron_service:
                    j = self._cron_service.get_job(job_id)
                    if j:
                        parent_id = getattr(j.payload, "parent_job_id", None) or None
                        if parent_id:
                            completed_job_id = parent_id
                    # Confirmar conclusão: pedir sim/não antes de marcar como feito
                    from backend.confirmations import set_pending
                    set_pending(self.name, chat_id, "completion_confirmation", {
                        "job_id": job_id,
                        "completed_job_id": completed_job_id,
                    })
                    logger.info(f"Reação positiva: pedindo confirmação para job {job_id}")
                await self.bus.publish_outbound(OutboundMessage(
                    channel=self.name,
                    chat_id=chat_id,
                    content="Confirmas que concluíste? Responde *sim* ou *não*.",
                ))
            elif is_snooze_emoji(emoji):
                if self._cron_service:
                    ok, count = self._cron_service.snooze_job(job_id)
                    if ok:
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=chat_id,
                            content=f"⏰ Adiado 5 min! (soneca {count}/3)",
                        ))
                    elif count >= self._cron_service.SNOOZE_MAX_COUNT:
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=chat_id,
                            content="Máximo 3 sonecas. Queres alterar o horário? Diz o novo horário ou *não* para cancelar.",
                        ))
                    # count==0 e ok==False: job já não existe (ex.: follow-up já executou), ignora
            elif is_negative_emoji(emoji):
                if self._cron_service:
                    self._cron_service.remove_job(job_id)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=self.name,
                    chat_id=chat_id,
                    content="Queres alterar o horário? Diz o novo horário (ex: em 1 hora, amanhã às 10h) ou *não* para cancelar.",
                ))
        except Exception as e:
            logger.debug(f"Reaction handler failed: {e}")
