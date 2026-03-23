/**
 * WebSocket server for Python-Node.js bridge communication.
 * Serves GET /health on the same port for Docker healthchecks.
 */
export declare class BridgeServer {
    private port;
    private authDir;
    private httpServer;
    private wss;
    private wa;
    private clients;
    constructor(port: number, authDir: string);
    start(): Promise<void>;
    private handleCommand;
    private broadcast;
    stop(): Promise<void>;
}
