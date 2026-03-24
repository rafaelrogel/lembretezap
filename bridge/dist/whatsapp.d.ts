/**
 * WhatsApp client wrapper using Baileys.
 * Based on OpenClaw's working implementation.
 */
export interface InboundMessage {
    id: string;
    sender: string;
    pn?: string;
    content: string;
    timestamp: number;
    isGroup: boolean;
    /** Display name from WhatsApp profile (Baileys pushName). Used e.g. for onboarding fallback. */
    pushName?: string;
    /** Raw .ics file content when the user sends a document with .ics / text/calendar */
    attachmentIcs?: string;
    /** Base64-encoded audio when user sends voice message (PTT). Option A: inline no payload. */
    mediaBase64?: string;
    /** True when audio was rejected for being too large (file size). */
    audioTooLarge?: boolean;
    /** True when audio was rejected for being forwarded (we only accept original voice recordings). */
    audioForwarded?: boolean;
    /** Mimetype of the audio (e.g. audio/ogg; codecs=opus or audio/mp4). Used for better format detection. */
    mimetype?: string;
}
export interface ReactionEvent {
    chatId: string;
    messageId: string;
    emoji: string;
    fromMe: boolean;
    sender?: string;
    pn?: string;
}
export interface WhatsAppClientOptions {
    authDir: string;
    onMessage: (msg: InboundMessage) => void;
    onReaction?: (ev: ReactionEvent) => void;
    onQR: (qr: string) => void;
    onStatus: (status: string) => void;
}
export declare class WhatsAppClient {
    private sock;
    private options;
    private reconnecting;
    constructor(options: WhatsAppClientOptions);
    connect(): Promise<void>;
    private basePayload;
    private extractMessageContent;
    sendMessage(to: string, text: string): Promise<{
        id: string;
    } | null>;
    /**
     * Envia voice note (PTT) a partir de ficheiro OGG/Opus.
     * O path deve ser acessível ao container do bridge (ex.: /root/.zapista/tmp/tts/xxx.ogg).
     */
    sendVoiceNote(to: string, audioPath: string): Promise<{
        id: string;
    } | null>;
    disconnect(): Promise<void>;
}
