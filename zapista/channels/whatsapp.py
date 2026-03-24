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

from backend.logger import get_logger
logger = get_logger(__name__)

from zapista.bus.events import OutboundMessage
from zapista.bus.queue import MessageBus
from zapista.channels.base import BaseChannel
from zapista.config.schema import WhatsAppConfig

from backend.locale import (
    LangCode,
    AUDIO_TOO_LARGE,
    AUDIO_TOO_LONG,
    AUDIO_NOT_ALLOWED,
    AUDIO_FORWARDED,
    AUDIO_TRANSCRIBE_FAILED,
    AUDIO_NOT_RECEIVED,
    GOD_MODE_ACTIVE,
    GOD_MODE_INACTIVE,
    MUTE_USAGE,
    ADMIN_ERROR,
    RESTART_MSG_FIRST,
    RESTART_MSG_SECOND,
    RESTART_MSG_CANCELLED,
    RESTART_MSG_DONE,
    RESTART_ERROR,
    CONFIRM_DONE,
    SCHEDULE_CHANGE_PROMPT,
    SNOOZE_MAX,
    format_snooze,
)

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
    try:
        from zapista.clock_drift import get_effective_time
        now = get_effective_time()
    except Exception:
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
    try:
        from zapista.clock_drift import get_effective_time
        now = get_effective_time()
    except Exception:
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
        """Send a message through WhatsApp (text or voice note)."""
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

        # audio_mode: TTS → PTT; se texto longo, vários áudios (split_text_for_tts) + texto
        # Allowlist: mesma lógica do STT (allow_from_tts vazio = todos). Grupos NUNCA.
        audio_mode = (msg.metadata or {}).get("audio_mode") is True
        locale_override = (msg.metadata or {}).get("audio_locale_override")
        phone_for_locale = (msg.metadata or {}).get("phone_for_locale")
        ogg_paths: list = []
        chat_id_str = str(msg.chat_id)
        tts_allowed = (
            not chat_id_str.strip().endswith(WHATSAPP_GROUP_SUFFIX)
            and self.is_allowed_tts(chat_id_str)
        )
        if audio_mode:
            logger.info(f"TTS: audio_mode=True chat_id={str(msg.chat_id)[:24]}... tts_allowed={tts_allowed} content_len={len(msg.content or '')}")
        if audio_mode and msg.content and tts_allowed:
            try:
                from zapista.tts.service import synthesize_voice_note, split_text_for_tts
                from zapista.tts.config import tts_max_words, tts_enabled
                if not tts_enabled():
                    logger.info("TTS requested but TTS disabled or Piper not configured; sending text only. Set TTS_ENABLED=1 and PIPER_BIN/TTS_MODELS_BASE for voice replies.")
                else:
                    chunks = split_text_for_tts(msg.content, tts_max_words())
                    for chunk in chunks:
                        if not chunk.strip():
                            continue
                        ogg = synthesize_voice_note(
                            chunk,
                            chat_id_str,
                            locale_override=locale_override,
                            phone_for_locale=phone_for_locale,
                        )
                        if ogg and ogg.exists():
                            ogg_paths.append(ogg)
                    logger.info(f"TTS: tts_enabled=1 chunks={len(chunks)} ogg_paths={len(ogg_paths)} (Piper em PIPER_BIN/TTS_MODELS_BASE)")
                    if not ogg_paths and msg.content:
                        logger.info("TTS requested but no audio generated (check TTS_MODELS_BASE/Piper voices and logs). Sending text only.")
            except Exception as e:
                logger.warning(f"TTS synthesize failed: {e}")

        if audio_mode and not tts_allowed:
            logger.info("TTS: audio_mode=True but tts_allowed=False (check allow_from_tts in config or group chat)")
        if audio_mode and not (msg.content or "").strip():
            logger.info("TTS: audio_mode=True but content empty; sending nothing or text only")
        try:
            if ogg_paths:
                for i, ogg_path in enumerate(ogg_paths):
                    payload = {
                        "type": "send_voice",
                        "to": msg.chat_id,
                        "audio_path": str(ogg_path.resolve()),
                    }
                    if job_id:
                        payload["job_id"] = job_id
                    if request_id:
                        payload["request_id"] = request_id
                    logger.info(f"WhatsApp send_voice: to={str(msg.chat_id)[:30]}...")
                    # Só esperar confirmação no primeiro áudio (para store_sent_mapping)
                    rid = request_id if i == 0 else None
                    await self._send_payload(payload, rid, msg.chat_id, job_id)
                if msg.content:
                    payload = {
                        "type": "send",
                        "to": msg.chat_id,
                        "text": msg.content,
                    }
                    if job_id:
                        payload["job_id"] = job_id
                    if request_id:
                        payload["request_id"] = request_id
                    logger.info(f"WhatsApp send (texto após áudios): to={str(msg.chat_id)[:30]}...")
                    await self._send_payload(payload, None, None, None)
                return
            payload = {
                "type": "send",
                "to": msg.chat_id,
                "text": msg.content,
            }
            if job_id:
                payload["job_id"] = job_id
            if request_id:
                payload["request_id"] = request_id
            logger.info(f"WhatsApp send: to={str(msg.chat_id)[:30]}... len={len(msg.content)}")
            await self._send_payload(payload, request_id, msg.chat_id, job_id)
        except Exception as e:
            self._pending_sends.pop(request_id, None) if request_id else None
            logger.error(f"Error sending WhatsApp message: {e}")

    async def _send_payload(
        self,
        payload: dict,
        request_id: str | None = None,
        chat_id: Any = None,
        job_id: str | None = None,
    ) -> None:
        """Envia um payload ao bridge e opcionalmente espera confirmação (para store_sent_mapping)."""
        future = None
        if request_id:
            future = asyncio.get_running_loop().create_future()
            self._pending_sends[request_id] = future
        await self._ws.send(json.dumps(payload))
        if future and job_id and chat_id is not None:
            try:
                result = await asyncio.wait_for(future, timeout=10.0)
                msg_id = result.get("id") if isinstance(result, dict) else None
                if msg_id:
                    try:
                        from backend.database import SessionLocal
                        from backend.reminder_reaction import store_sent_mapping
                        db = SessionLocal()
                        try:
                            store_sent_mapping(db, chat_id, msg_id, job_id)
                        finally:
                            db.close()
                    except Exception as e:
                        logger.debug(f"Store sent mapping failed: {e}")
            except asyncio.TimeoutError:
                logger.debug("WhatsApp send: no sent confirmation within 10s")
            finally:
                self._pending_sends.pop(request_id, None)

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
            if data.get("fromMe") or data.get("from_me"):
                logger.debug(f"Ignoring own message id={data.get('id')!r}")
                return
            
            sender = (data.get("sender") or "").strip()
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
            is_group = data.get("isGroup", False) or sender.endswith(WHATSAPP_GROUP_SUFFIX)
            if is_group:
                logger.debug("Ignoring message from group (we only respond in private chats)")
                return

            # Deprecated by whatsapp: old phone number style typically: <phone>@s.whatsapp.net
            pn = data.get("pn", "")
            # New LID style typically:
            content = data.get("content", "")
            transcribed_text = None

            # Extract just the phone number or lid as chat_id
            user_id = pn if pn else sender
            sender_id = user_id.split("@")[0] if "@" in user_id else user_id

            # Fallback dedup (APÓS estabilização): mesmo chat + mesmo texto em 30s = ignorar
            # Isto evita que a mesma msg (ex: "oi") enviada via LID e depois JID passe 2x.
            if not msg_id and _is_duplicate_by_content(user_id, content or ""):
                logger.debug(f"Ignoring duplicate by content from {user_id[:20]}...")
                return

            # Se um tester não receber resposta, ver nos logs este valor e adiciona-o a allow_from no config
            logger.info(f"WhatsApp from sender={sender!r} pn={pn!r} → chat_id={user_id!r} (sender_id={sender_id!r})")

            # Migração de identidade (LID -> JID) se detetarmos ambos no mesmo evento
            if pn and sender and pn != sender and "@s.whatsapp.net" in pn and "@lid" in sender:
                try:
                    from backend.database import SessionLocal
                    from backend.user_store import migrate_user_identity
                    db = SessionLocal()
                    try:
                        migrate_user_identity(db, sender, pn)
                    finally:
                        db.close()
                except Exception as e:
                    logger.debug(f"Identity migration failed: {e}")

            # Handle voice transcription if it's a voice message (option A: base64 no payload)
            from backend.database import SessionLocal
            from zapista.bus.events import OutboundMessage
            from backend.locale import (
                phone_to_default_language,
            )
            from backend.user_store import get_user_language

            media_base64 = data.get("mediaBase64") or data.get("media_base_64")
            mimetype = data.get("mimetype") or data.get("mime_type")
            audio_too_large = data.get("audioTooLarge") or data.get("audio_too_large")
            if content == "[Voice Message]":
                # Resolve idioma do utilizador (pt-PT, pt-BR, es, en). Preferir pn para LID.
                phone_for_locale = pn or sender
                db = SessionLocal()
                try:
                    user_lang: LangCode = (
                        get_user_language(db, user_id, phone_for_locale) or phone_to_default_language(phone_for_locale)
                    )
                finally:
                    db.close()

                if audio_too_large:
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=AUDIO_TOO_LARGE.get(user_lang, AUDIO_TOO_LARGE["en"]),
                    ))
                    return
                audio_forwarded = data.get("audioForwarded") or data.get("audio_forwarded")
                if audio_forwarded:
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=AUDIO_FORWARDED.get(user_lang, AUDIO_FORWARDED["en"]),
                    ))
                    return
                if not self.is_allowed_audio(sender_id):
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=AUDIO_NOT_ALLOWED.get(user_lang, AUDIO_NOT_ALLOWED["en"]),
                    ))
                    return
                if media_base64 and isinstance(media_base64, str):
                    from zapista.stt import transcribe
                    from zapista.stt.audio_utils import check_audio_duration

                    duration_error_key = check_audio_duration(media_base64.strip(), mimetype=mimetype)
                    if duration_error_key == "AUDIO_TOO_LONG":
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=user_id,
                            content=AUDIO_TOO_LONG.get(user_lang, AUDIO_TOO_LONG["en"]),
                        ))
                        return

                    transcribed = await transcribe(media_base64.strip(), mimetype=mimetype)
                    if transcribed and transcribed.strip():
                        content = transcribed.strip()
                        transcribed_text = content
                    else:
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=user_id,
                            content=AUDIO_TRANSCRIBE_FAILED.get(
                                user_lang, AUDIO_TRANSCRIBE_FAILED["en"]
                            ),
                        ))
                        return
                else:
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=AUDIO_NOT_RECEIVED.get(user_lang, AUDIO_NOT_RECEIVED["en"]),
                    ))
                    return

            # Anexo .ics: parse e registar eventos (sem passar ao agente)
            attachment_ics = data.get("attachmentIcs") or data.get("attachment_ics")
            if attachment_ics and isinstance(attachment_ics, str) and attachment_ics.strip():
                from zapista.bus.events import OutboundMessage
                try:
                    from backend.ics_handler import handle_ics_payload
                    from backend.database import SessionLocal
                    response = await handle_ics_payload(
                        chat_id=user_id,
                        sender_id=sender_id,
                        ics_content=attachment_ics.strip(),
                        db_session_factory=SessionLocal,
                        cron_tool=getattr(self, "_cron_tool", None),
                        cron_channel=self.name,
                    )
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=response or "—",
                    ))
                except Exception as e:
                    logger.exception(f"ICS handler failed: {e}")
                    error_str = str(e).lower()
                    error_type = type(e).__name__
                    
                    # Mensagem de erro específica baseada no tipo de erro
                    if "icalendar" in error_str or "import" in error_str or "module" in error_str:
                        ics_err = "Suporte a calendários temporariamente indisponível. Tenta novamente mais tarde."
                    elif "encoding" in error_str or "decode" in error_str or "codec" in error_str or "utf" in error_str:
                        ics_err = (
                            "Erro de encoding no ficheiro .ics. "
                            "O Gmail às vezes exporta com formato incorreto. "
                            "Tenta abrir no Google Calendar (calendar.google.com) e exportar de lá."
                        )
                    elif "parse" in error_str or "invalid" in error_str or "calendar" in error_str:
                        ics_err = (
                            "Calendário inválido ou mal formado. "
                            "Verifica se o ficheiro .ics está completo e tenta novamente."
                        )
                    elif "database" in error_str or "db" in error_str or "sql" in error_str:
                        ics_err = "Erro ao guardar eventos. Tenta novamente em alguns segundos."
                    else:
                        ics_err = (
                            f"Erro ao processar calendário ({error_type}). "
                            "Tenta exportar o .ics de outra forma ou de outro serviço."
                        )
                    
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=ics_err,
                    ))
                return

            # God Mode: #<senha> ativa; #cmd só se já ativou. Senha errada ou #inválido = silêncio.
            if (content or "").strip().startswith("#"):
                from backend.admin_commands import (
                    is_god_mode_password,
                    is_god_mode_activated,
                    activate_god_mode,
                    deactivate_god_mode,
                    bump_god_mode_activity,
                    log_god_mode_audit,
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
                if is_locked_out(user_id):
                    log_god_mode_audit(user_id, "login_blocked")
                    return  # bloqueado por tentativas erradas; silêncio
                if is_god_mode_password(rest):
                    clear_failed_attempts(user_id)
                    activate_god_mode(user_id)
                    log_god_mode_audit(user_id, "login_ok")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=GOD_MODE_ACTIVE.get(user_lang, GOD_MODE_ACTIVE["en"]) if 'user_lang' in locals() else GOD_MODE_ACTIVE["pt-PT"],
                    ))
                    return
                cmd, arg = parse_admin_command_arg(raw)
                if not cmd or not is_god_mode_activated(user_id):
                    if not cmd and rest:
                        record_failed_attempt(user_id)
                        log_god_mode_audit(user_id, "login_fail")
                    return  # silêncio
                # Sessão válida: resetar inatividade
                bump_god_mode_activity(user_id)
                # #quit: desativar god-mode
                if cmd == "quit":
                    deactivate_god_mode(user_id)
                    log_god_mode_audit(user_id, "logout")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=GOD_MODE_INACTIVE.get(user_lang, GOD_MODE_INACTIVE["en"]) if 'user_lang' in locals() else GOD_MODE_INACTIVE["pt-PT"],
                    ))
                    return
                # #mute <número>: aplicar punição e enviar mensagem ao utilizador
                if cmd == "mute":
                    if not arg.strip():
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=user_id,
                            content=MUTE_USAGE.get(user_lang, MUTE_USAGE["en"]) if 'user_lang' in locals() else MUTE_USAGE["pt-PT"],
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
                        chat_id=user_id,
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
                        chat_id=user_id,
                    )
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=response or "—",
                    ))
                except Exception as e:
                    logger.exception(f"Admin command failed: {e}")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=ADMIN_ERROR.get(user_lang, ADMIN_ERROR["en"]) if 'user_lang' in locals() else ADMIN_ERROR["pt-PT"],
                    ))
                return

            # /restart: confirmação dupla (sim/não) e depois execução do reset
            from zapista.utils.restart_flow import (
                get_restart_stage,
                set_restart_stage,
                clear_restart_stage,
                is_confirm_reply,
                is_confirm_no,
                run_restart,
            )
            raw_content = (content or "").strip()
            is_restart_cmd = raw_content.lower() in ("/restart", "restart")
            stage = get_restart_stage(self.name, user_id)
            if is_restart_cmd and not stage:
                set_restart_stage(self.name, user_id, "1")
                await self.bus.publish_outbound(OutboundMessage(
                    channel=self.name,
                    chat_id=user_id,
                    content=RESTART_MSG_FIRST.get(user_lang, RESTART_MSG_FIRST["en"]) if 'user_lang' in locals() else RESTART_MSG_FIRST["pt-PT"],
                ))
                return
            if stage and is_confirm_reply(raw_content):
                if is_confirm_no(raw_content):
                    clear_restart_stage(self.name, user_id)
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=RESTART_MSG_CANCELLED.get(user_lang, RESTART_MSG_CANCELLED["en"]) if 'user_lang' in locals() else RESTART_MSG_CANCELLED["pt-PT"],
                    ))
                    return
                if stage == "1":
                    set_restart_stage(self.name, user_id, "2")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=RESTART_MSG_SECOND.get(user_lang, RESTART_MSG_SECOND["en"]) if 'user_lang' in locals() else RESTART_MSG_SECOND["pt-PT"],
                    ))
                    return
                if stage == "2":
                    clear_restart_stage(self.name, user_id)
                    if self._restart_executor:
                        try:
                            await self._restart_executor(self.name, user_id)
                        except Exception as e:
                            logger.exception(f"Restart executor failed: {e}")
                            await self.bus.publish_outbound(OutboundMessage(
                                channel=self.name,
                                chat_id=user_id,
                                content=RESTART_ERROR.get(user_lang, RESTART_ERROR["en"]) if 'user_lang' in locals() else RESTART_ERROR["pt-PT"],
                            ))
                            return
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=user_id,
                        content=RESTART_MSG_DONE.get(user_lang, RESTART_MSG_DONE["en"]) if 'user_lang' in locals() else RESTART_MSG_DONE["pt-PT"],
                    ))
                    return
            if stage:
                # Continua à espera de sim/não; ignorar outras mensagens ou repetir o aviso
                return

            # Horário silencioso: só processar mensagem se for para desativar (comando /quiet off ou NL "parar horário silencioso")
            try:
                from backend.user_store import is_user_in_quiet_window
                from backend.settings_handlers import _is_nl_quiet_off
                if is_user_in_quiet_window(user_id):
                    raw = (content or "").strip()
                    if not raw.lower().startswith("/quiet") and not _is_nl_quiet_off(raw):
                        return  # não responder durante horário silencioso
            except Exception:
                pass

            # Resposta em áudio: pedido em texto ("responde em áudio", "manda áudio", "fala comigo") ou áudio
            raw_content = (content or "").strip()
            audio_mode = False
            audio_locale_override = None
            try:
                from backend.audio_request import detects_audio_request
                if detects_audio_request(raw_content):
                    audio_mode = True
            except Exception:
                pass

            # Forward to agent only for private chats (groups already filtered above)
            # phone_for_locale: número para inferir idioma (pn tem o número quando sender é LID)
            trace_id = uuid.uuid4().hex[:12]
            meta = {
                "message_id": data.get("id"),
                "timestamp": data.get("timestamp"),
                "is_group": False,
                "trace_id": trace_id,
                "phone_for_locale": pn or sender,
                "raw_sender": sender,
            }
            # Nome do perfil WhatsApp (Baileys pushName) — usado no onboarding como fallback
            push_name = (data.get("pushName") or data.get("push_name") or "").strip()
            if push_name:
                meta["sender_display_name"] = push_name[:128]
            if audio_mode:
                meta["audio_mode"] = True
                if audio_locale_override:
                    meta["audio_locale_override"] = audio_locale_override
            if transcribed_text:
                meta["transcribed_text"] = transcribed_text
            await self._handle_message(
                sender_id=sender_id,
                chat_id=user_id,  # Use stable chat_id (prioritizes JID over LID)
                content=content,
                metadata=meta,
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
        pn = (data.get("pn") or "").strip()
        # Estabilizar chat_id: priorizar número (pn) sobre LID
        user_id = pn if pn else chat_id

        message_id = (data.get("messageId") or "").strip()
        emoji = (data.get("emoji") or "").strip()
        if not user_id or not message_id:
            return
        if user_id.endswith(WHATSAPP_GROUP_SUFFIX):
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
                job_id = lookup_job_by_message(db, user_id, message_id)
                # Fallback para transição: se enviamos o lembrete para o LID, mas o user reagiu como JID
                if not job_id and pn and chat_id and user_id != chat_id:
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
                    set_pending(self.name, user_id, "completion_confirmation", {
                        "job_id": job_id,
                        "completed_job_id": completed_job_id,
                    })
                    logger.info(f"Reação positiva: pedindo confirmação para job {job_id}")
                
                # We need user language here if available, fallback to pt-BR
                user_lang = "pt-BR"
                db = SessionLocal()
                try:
                    from backend.user_store import get_user_language
                    from backend.locale import phone_to_default_language
                    user_lang = get_user_language(db, user_id, user_id) or phone_to_default_language(user_id)
                except Exception:
                    pass
                finally:
                    db.close()

                await self.bus.publish_outbound(OutboundMessage(
                    channel=self.name,
                    chat_id=user_id,
                    content=CONFIRM_DONE.get(user_lang, CONFIRM_DONE["en"]),
                ))
            elif is_snooze_emoji(emoji):
                user_lang = "pt-BR"
                db = SessionLocal()
                try:
                    from backend.user_store import get_user_language
                    from backend.locale import phone_to_default_language
                    user_lang = get_user_language(db, user_id, user_id) or phone_to_default_language(user_id)
                except Exception:
                    pass
                finally:
                    db.close()

                if self._cron_service:
                    ok, count = self._cron_service.snooze_job(job_id)
                    if ok:
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=user_id,
                            content=format_snooze(user_lang, count),
                        ))
                    elif count >= self._cron_service.SNOOZE_MAX_COUNT:
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=user_id,
                            content=SNOOZE_MAX.get(user_lang, SNOOZE_MAX["en"]),
                        ))
                    # count==0 e ok==False: job já não existe (ex.: follow-up já executou), ignora
            elif is_negative_emoji(emoji):
                user_lang = "pt-BR"
                db = SessionLocal()
                try:
                    from backend.user_store import get_user_language
                    from backend.locale import phone_to_default_language
                    user_lang = get_user_language(db, user_id, user_id) or phone_to_default_language(user_id)
                except Exception:
                    pass
                finally:
                    db.close()

                if self._cron_service:
                    self._cron_service.remove_job(job_id)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=self.name,
                    chat_id=user_id,
                    content=SCHEDULE_CHANGE_PROMPT.get(user_lang, SCHEDULE_CHANGE_PROMPT["en"]),
                ))
        except Exception as e:
            logger.debug(f"Reaction handler failed: {e}")
