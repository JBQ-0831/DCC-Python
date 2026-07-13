/**
 * VS Code 内部 socket 服务端的协议层
 *
 * 复用项目已有的长度前缀 + JSON 协议，保持与 DCC 服务端协议一致。
 */

export interface Request {
    id: string;
    method: string;
    params: Record<string, any>;
}

export interface Response {
    id: string;
    result?: {
        success: boolean;
        output?: string[];
        [key: string]: any;
    };
    error?: {
        message: string;
        traceback?: string;
    };
}

export function encodeResponse(response: Response): Buffer {
    const jsonStr = JSON.stringify(response);
    const jsonBytes = Buffer.from(jsonStr, 'utf-8');
    const lengthBytes = Buffer.alloc(4);
    lengthBytes.writeUInt32BE(jsonBytes.length, 0);
    return Buffer.concat([lengthBytes, jsonBytes]);
}

export function decodeRequest(buffer: Buffer): { request: Request; consumed: number } | null {
    if (buffer.length < 4) {
        return null;
    }

    const length = buffer.readUInt32BE(0);
    if (buffer.length < 4 + length) {
        return null;
    }

    const jsonBytes = buffer.subarray(4, 4 + length);
    const jsonStr = jsonBytes.toString('utf-8');
    const request: Request = JSON.parse(jsonStr);

    return { request, consumed: 4 + length };
}
