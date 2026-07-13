/**
 * VS Code 内部 socket 服务端
 *
 * 监听本地端口，接收外部传入的 execute_file / execute_code 请求并调用 DCC driver 执行。
 */

import * as net from 'net';

import Logger from '../logging';
import * as utils from '../utils';

import { encodeResponse, decodeRequest } from './protocol';
import { handleRequest } from './handler';
import type { Request } from './protocol';


let server: net.Server | null = null;


export function startVSCodeServer(): void {
    if (server) {
        Logger.info('[VSCodeServer] Server is already running');
        return;
    }

    const config = utils.getExtensionConfig();
    const enabled = config.get<boolean>('vscodeServer.enabled', false);
    if (!enabled) {
        Logger.info('[VSCodeServer] Server is disabled by configuration');
        return;
    }

    const port = config.get<number>('vscodeServer.port', 7005);

    server = net.createServer((socket) => {
        handleSocket(socket);
    });

    server.on('error', (err) => {
        if ((err as any).code === 'EADDRINUSE') {
            Logger.error(`[VSCodeServer] Port ${port} is already in use. Server could not start.`);
        } else {
            Logger.error(`[VSCodeServer] Server error: ${err.message}`);
        }
        server = null;
    });

    // 只监听本机地址，避免外部网络访问
    server.listen(port, '127.0.0.1', () => {
        Logger.info(`[VSCodeServer] Server listening on 127.0.0.1:${port}`);
    });
}


export function stopVSCodeServer(): void {
    if (!server) {
        return;
    }

    server.close(() => {
        Logger.info('[VSCodeServer] Server stopped');
    });
    server = null;
}


function handleSocket(socket: net.Socket): void {
    let buffer = Buffer.alloc(0);

    socket.on('data', async (data) => {
        buffer = Buffer.concat([buffer, data]);

        while (true) {
            const decoded = decodeRequest(buffer);
            if (!decoded) {
                break;
            }

            buffer = buffer.subarray(decoded.consumed);
            const request: Request = decoded.request;

            try {
                const response = await handleRequest(request);
                socket.write(encodeResponse(response));
            } catch (err) {
                const message = err instanceof Error ? err.message : String(err);
                Logger.error(`[VSCodeServer] Failed to handle request: ${message}`);
                socket.write(encodeResponse({
                    id: request.id || 'unknown',
                    error: { message }
                }));
            }
        }
    });

    socket.on('error', (err) => {
        Logger.error(`[VSCodeServer] Socket error: ${err.message}`);
    });

    socket.on('close', () => {
        Logger.info('[VSCodeServer] Client disconnected');
    });
}
