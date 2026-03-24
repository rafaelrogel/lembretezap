/**
 * WhatsApp client wrapper using Baileys.
 * Based on OpenClaw's working implementation.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
import * as fs from 'fs';
import * as path from 'path';
import makeWASocket, { DisconnectReason, useMultiFileAuthState, fetchLatestBaileysVersion, makeCacheableSignalKeyStore, downloadMediaMessage, } from '@whiskeysockets/baileys';
import qrcode from 'qrcode-terminal';
import pino from 'pino';
const VERSION = '0.1.0';
export class WhatsAppClient {
    sock = null;
    options;
    reconnecting = false;
    constructor(options) {
        this.options = options;
    }
    async connect() {
        const logger = pino({ level: 'silent' });
        const self = this;
        const { state, saveCreds } = await useMultiFileAuthState(this.options.authDir);
        const { version } = await fetchLatestBaileysVersion();
        console.log(`Using Baileys version: ${version.join('.')}`);
        // Create socket following OpenClaw's pattern
        this.sock = makeWASocket({
            auth: {
                creds: state.creds,
                keys: makeCacheableSignalKeyStore(state.keys, logger),
            },
            version,
            logger,
            printQRInTerminal: false,
            browser: ['zapista', 'cli', VERSION],
            syncFullHistory: false,
            markOnlineOnConnect: false,
        });
        // Handle WebSocket errors
        if (this.sock.ws && typeof this.sock.ws.on === 'function') {
            this.sock.ws.on('error', (err) => {
                console.error('WebSocket error:', err.message);
            });
        }
        // Handle connection updates
        this.sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr } = update;
            if (qr) {
                // Display QR code in terminal
                console.log('\n📱 Scan this QR code with WhatsApp (Linked Devices):\n');
                qrcode.generate(qr, { small: true });
                this.options.onQR(qr);
            }
            if (connection === 'close') {
                const statusCode = lastDisconnect?.error?.output?.statusCode;
                const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
                console.log(`Connection closed. Status: ${statusCode}, Will reconnect: ${shouldReconnect}`);
                this.options.onStatus('disconnected');
                if (shouldReconnect && !this.reconnecting) {
                    this.reconnecting = true;
                    console.log('Reconnecting in 5 seconds...');
                    setTimeout(() => {
                        this.reconnecting = false;
                        this.connect();
                    }, 5000);
                }
            }
            else if (connection === 'open') {
                console.log('✅ Connected to WhatsApp');
                this.options.onStatus('connected');
            }
        });
        // Save credentials on update
        this.sock.ev.on('creds.update', saveCreds);
        // Reações: emoji na mensagem (feito 👍 / não feito 👎)
        if (this.options.onReaction) {
            this.sock.ev.on('messages.reaction', (reactions) => {
                const arr = Array.isArray(reactions) ? reactions : (reactions ? [reactions] : []);
                for (const r of arr) {
                    const key = r?.key;
                    const text = (r?.text || '').trim();
                    if (!key?.id || !key?.remoteJid)
                        continue;
                    const chatId = key.remoteJid;
                    const messageId = key.id;
                    const fromMe = !!key.fromMe;
                    const participant = key.participant;
                    const sender = participant || chatId;
                    this.options.onReaction({
                        chatId,
                        messageId,
                        emoji: text || '',
                        fromMe,
                        sender,
                        pn: key.remoteJidAlt || '',
                    });
                }
            });
        }
        // Allow self-messages (message to yourself / saved messages) for testing with a single number
        const allowSelfMessages = process.env.ALLOW_SELF_MESSAGES === '1' || process.env.ALLOW_SELF_MESSAGES === 'true';
        // Handle incoming messages
        const MAX_ICS_BYTES = 500 * 1024; // 500 KB
        const MAX_AUDIO_BYTES = 2 * 1024 * 1024; // 2 MB (~5–6 min Opus; pedidos sucintos até ~1 min)
        this.sock.ev.on('messages.upsert', async ({ messages, type }) => {
            if (type !== 'notify')
                return;
            for (const msg of messages) {
                if (msg.key.fromMe && !allowSelfMessages)
                    continue;
                if (msg.key.remoteJid === 'status@broadcast')
                    continue;
                const isGroup = msg.key.remoteJid?.endsWith('@g.us') || false;
                // Document .ics: download and send to gateway with attachmentIcs
                const doc = msg.message?.documentMessage;
                if (doc) {
                    const fileName = (doc.fileName || doc.title || '').toString().toLowerCase();
                    const mime = (doc.mimeType || '').toString().toLowerCase();
                    const isIcs = fileName.endsWith('.ics') || mime.includes('calendar');
                    if (isIcs) {
                        try {
                            const buffer = await downloadMediaMessage(msg, 'buffer', {}, { logger, reuploadRequest: this.sock.updateMediaMessage });
                            if (buffer && buffer.length > 0 && buffer.length <= MAX_ICS_BYTES) {
                                let icsContent = buffer.toString('utf-8');
                                // Se UTF-8 não parecer um .ics válido (ex.: ficheiro em Latin-1), tentar Latin-1
                                if (icsContent.trim() && !/BEGIN:VCALENDAR/i.test(icsContent)) {
                                    const asLatin1 = (Buffer.isBuffer(buffer) ? buffer : Buffer.from(buffer)).toString('latin1');
                                    if (/BEGIN:VCALENDAR/i.test(asLatin1)) {
                                        icsContent = asLatin1;
                                    }
                                }
                                if (icsContent.trim()) {
                                    const caption = doc.caption ? (typeof doc.caption === 'string' ? doc.caption : '') : '';
                                    this.options.onMessage({
                                        ...this.basePayload(msg),
                                        content: caption || '[Calendar]',
                                        attachmentIcs: icsContent,
                                    });
                                    continue;
                                }
                            }
                        }
                        catch (err) {
                            console.error('ICS download failed:', err.message);
                        }
                    }
                }
                // Voice/Audio: download and send as base64 (option A). Only accept original recordings, not forwarded.
                const audioMsg = msg.message?.audioMessage;
                if (audioMsg) {
                    const ctx = audioMsg.contextInfo;
                    const isForwarded = ctx?.isForwarded === true || ((ctx?.forwardingScore ?? 0) > 0);
                    if (isForwarded) {
                        this.options.onMessage({
                            ...this.basePayload(msg),
                            content: '[Voice Message]',
                            audioForwarded: true,
                        });
                        continue;
                    }
                    try {
                        const buffer = await downloadMediaMessage(msg, 'buffer', {}, { logger, reuploadRequest: this.sock.updateMediaMessage });
                        if (buffer && buffer.length > 0 && buffer.length <= MAX_AUDIO_BYTES) {
                            const mediaBase64 = Buffer.isBuffer(buffer) ? buffer.toString('base64') : Buffer.from(buffer).toString('base64');
                            this.options.onMessage({
                                ...this.basePayload(msg),
                                content: '[Voice Message]',
                                mediaBase64,
                                mimetype: audioMsg.mimetype || 'audio/ogg',
                            });
                            continue;
                        }
                        if (buffer && buffer.length > MAX_AUDIO_BYTES) {
                            this.options.onMessage({
                                ...this.basePayload(msg),
                                content: '[Voice Message]',
                                audioTooLarge: true,
                            });
                            continue;
                        }
                    }
                    catch (err) {
                        console.error('Audio download failed:', err.message);
                    }
                    this.options.onMessage({
                        ...this.basePayload(msg),
                        content: '[Voice Message]',
                    });
                    continue;
                }
                const content = this.extractMessageContent(msg);
                if (!content)
                    continue;
                this.options.onMessage({
                    ...this.basePayload(msg),
                    content,
                });
            }
        });
    }
    basePayload(msg) {
        const pushName = typeof msg.pushName === 'string' ? msg.pushName.trim() || undefined : undefined;
        return {
            id: msg.key.id || '',
            sender: msg.key.remoteJid || '',
            pn: msg.key.remoteJidAlt || '',
            timestamp: msg.messageTimestamp,
            isGroup: msg.key.remoteJid?.endsWith('@g.us') || false,
            ...(pushName ? { pushName } : {}),
        };
    }
    extractMessageContent(msg) {
        const message = msg.message;
        if (!message)
            return null;
        // Text message
        if (message.conversation) {
            return message.conversation;
        }
        // Extended text (reply, link preview)
        if (message.extendedTextMessage?.text) {
            return message.extendedTextMessage.text;
        }
        // Image with caption
        if (message.imageMessage?.caption) {
            return `[Image] ${message.imageMessage.caption}`;
        }
        // Video with caption
        if (message.videoMessage?.caption) {
            return `[Video] ${message.videoMessage.caption}`;
        }
        // Document with caption
        if (message.documentMessage?.caption) {
            return `[Document] ${message.documentMessage.caption}`;
        }
        // Voice/Audio message
        if (message.audioMessage) {
            return `[Voice Message]`;
        }
        return null;
    }
    // TODO: Após WhatsApp Business API, use buttons: sendButtons(['Confirmar','Cancelar']) em vez de texto "1=sim 2=não".
    async sendMessage(to, text) {
        if (!this.sock) {
            throw new Error('Not connected');
        }
        const result = await this.sock.sendMessage(to, { text });
        const id = result?.key?.id || null;
        return id ? { id } : null;
    }
    /**
     * Envia voice note (PTT) a partir de ficheiro OGG/Opus.
     * O path deve ser acessível ao container do bridge (ex.: /root/.zapista/tmp/tts/xxx.ogg).
     */
    async sendVoiceNote(to, audioPath) {
        if (!this.sock) {
            throw new Error('Not connected');
        }
        const resolved = path.resolve(audioPath);
        if (!fs.existsSync(resolved)) {
            throw new Error(`Audio file not found: ${audioPath}`);
        }
        const buffer = fs.readFileSync(resolved);
        const result = await this.sock.sendMessage(to, {
            audio: buffer,
            mimetype: 'audio/ogg; codecs=opus',
            ptt: true,
        });
        const id = result?.key?.id || null;
        return id ? { id } : null;
    }
    async disconnect() {
        if (this.sock) {
            this.sock.end(undefined);
            this.sock = null;
        }
    }
}
