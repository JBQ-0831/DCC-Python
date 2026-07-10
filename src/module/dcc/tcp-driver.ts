/**
 * TCP 驱动实现
 * 
 * 使用通用 TCP + JSON 协议连接 vscode_dcc 服务端
 * 适用于 3ds Max、Substance Painter 等没有内置命令端口的 DCC
 */

import * as net from 'net';
import * as crypto from 'crypto';

import Logger from '../logging';

import type { IDCCDriver, IExecutionResult, IDCCConfig } from './types';

interface Request {
    id: string;
    method: string;
    params: Record<string, any>;
}

interface Response {
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

export class TCPDriver implements IDCCDriver {
    readonly dccName: string;
    readonly dccType: string;
    readonly pythonPath?: string;
    
    private config: IDCCConfig;
    private socket: net.Socket | null = null;
    private isConnectedFlag: boolean = false;
    private pendingRequests: Map<string, (response: Response) => void> = new Map();
    private buffer: Buffer = Buffer.alloc(0);
    
    constructor(config: IDCCConfig, dccName: string, dccType: string) {
        this.config = config;
        this.dccName = dccName;
        this.dccType = dccType;
    }
    
    connect(): Promise<boolean> {
        return new Promise((resolve) => {
            if (this.socket && this.isConnectedFlag) {
                resolve(true);
                return;
            }
            
            // 清理残留的已断开 socket
            if (this.socket) {
                this.socket.destroy();
                this.socket = null;
            }
            
            this.socket = new net.Socket();
            this.buffer = Buffer.alloc(0);
            
            this.socket.on('connect', () => {
                this.isConnectedFlag = true;
                Logger.info(`Connected to ${this.dccType} at ${this.config.host}:${this.config.port}`);
                resolve(true);
            });
            
            this.socket.on('data', (data) => {
                this.buffer = Buffer.concat([this.buffer, data]);
                this.processBuffer();
            });
            
            this.socket.on('error', (err) => {
                Logger.error(`TCP connection error: ${err.message}`);
                this.isConnectedFlag = false;
                this.socket = null;
                resolve(false);
            });
            
            this.socket.on('close', (hadError) => {
                this.isConnectedFlag = false;
                this.socket = null;
                Logger.info(`TCP connection closed: hadError=${hadError}`);
            });
            
            this.socket.connect(this.config.port, this.config.host);
        });
    }
    
    disconnect(): void {
        if (this.socket) {
            this.socket.destroy();
            this.socket = null;
        }
        this.isConnectedFlag = false;
        this.pendingRequests.clear();
    }
    
    isConnected(): boolean {
        return this.isConnectedFlag && this.socket !== null;
    }
    
    async evaluateFunction(
        module: string, 
        functionName: string, 
        kwargs: Record<string, any> = {}, 
        discardOutput: boolean = false
    ): Promise<IExecutionResult | null> {
        return this.sendRequest('eval_function', {
            module,
            function: functionName,
            kwargs
        });
    }

    async executeFile(
        execFile: string,
        execOrigin: string,
        nameVar: string,
        isDebugging: boolean
    ): Promise<IExecutionResult | null> {
        console.log(`[TCPDriver] executeFile called: execFile=${execFile}, isDebugging=${isDebugging}`);
        // 通用 TCP 驱动直接发送 execute 请求
        return this.sendRequest('execute', {
            exec_file: execFile,
            exec_origin: execOrigin,
            name_var: nameVar,
            is_debugging: isDebugging
        });
    }

    async reloadModules(workspaceFolders: string[]): Promise<IExecutionResult | null> {
        return this.sendRequest('reload', {
            workspace_folders: workspaceFolders
        });
    }
    
    async sendCommand(
        command: string, 
        options: { discardOutput?: boolean } = {}
    ): Promise<IExecutionResult | null> {
        return this.sendRequest('eval_function', {
            module: 'builtins',
            function: 'exec',
            kwargs: {
                source: command
            }
        });
    }
    
    async importDebugpy(): Promise<boolean | undefined> {
        const result = await this.sendRequest('eval_function', {
            module: 'builtins',
            function: '__import__',
            kwargs: {
                name: 'debugpy'
            }
        });
        
        if (!result) {
            return false;
        }
        
        if (!result.success) {
            if (result.error && result.error.includes("No module named")) {
                Logger.error(`import of debugpy failed: ${result.error}`);
                return false;
            } else {
                Logger.showErrorMessage(`'import debugpy' returned unexpected result: ${result.error}`, "Failed to import debugpy");
                return undefined;
            }
        }
        
        return true;
    }
    
    async installDebugpy(pipIndexUrl?: string): Promise<boolean | undefined> {
        const params: Record<string, any> = {};
        if (pipIndexUrl) {
            params.pip_index_url = pipIndexUrl;
        }
        const result = await this.sendRequest('install_debugpy', params);
        
        // 显示 pip 安装日志到输出频道
        if (result && result.output.length > 0) {
            Logger.info('=== debugpy 安装日志 ===');
            for (const line of result.output) {
                if (line.trim()) {
                    Logger.info(line);
                }
            }
        }
        
        if (!result || !result.success) {
            return false;
        }
        
        return this.importDebugpy();
    }
    
    async startDebugServer(port: number): Promise<boolean> {
        const result = await this.sendRequest('start_debugpy', { port });
        
        if (result && result.output.length > 0) {
            Logger.info('=== debugpy 调试日志 ===');
            for (const line of result.output) {
                if (line.trim()) {
                    Logger.info(line);
                }
            }
        }
        
        return result?.success ?? false;
    }
    
    getHost(): string {
        return this.config.host;
    }
    
    getPort(): number {
        return this.config.port;
    }
    
    updateConfig(config: IDCCConfig): void {
        if (this.socket) {
            this.socket.destroy();
            this.socket = null;
        }
        this.isConnectedFlag = false;
        this.config = config;
    }
    
    private async sendRequest(method: string, params: Record<string, any>): Promise<IExecutionResult | null> {
        console.log(`[TCPDriver] sendRequest: method=${method}, hasSocket=${!!this.socket}, isConnected=${this.isConnectedFlag}`);
        Logger.info(`[DEBUG] sendRequest: method=${method}, hasSocket=${!!this.socket}, isConnected=${this.isConnectedFlag}`);
        
        // 如果连接断开，尝试自动重连
        if (!this.socket || !this.isConnectedFlag) {
            Logger.info(`[DEBUG] sendRequest: attempting reconnect...`);
            const reconnected = await this.connect();
            if (!reconnected) {
                Logger.error("Not connected to DCC server and reconnection failed");
                return null;
            }
            Logger.info(`[DEBUG] sendRequest: reconnected successfully`);
        }
        
        const id = crypto.randomUUID().replace(/-/g, '_');
        const request: Request = { id, method, params };
        
        return new Promise((resolve) => {
            this.pendingRequests.set(id, (response) => {
                this.pendingRequests.delete(id);
                
                if (response.error) {
                    resolve({
                        output: [],
                        success: false,
                        error: response.error.message,
                        traceback: response.error.traceback
                    });
                } else if (response.result) {
                    resolve({
                        output: response.result.output || [],
                        success: response.result.success
                    });
                } else {
                    resolve(null);
                }
            });
            
            const jsonStr = JSON.stringify(request);
            const jsonBytes = Buffer.from(jsonStr, 'utf-8');
            const lengthBytes = Buffer.alloc(4);
            lengthBytes.writeUInt32BE(jsonBytes.length, 0);
            
            const message = Buffer.concat([lengthBytes, jsonBytes]);
            this.socket!.write(message);
        });
    }
    
    private processBuffer(): void {
        while (this.buffer.length >= 4) {
            const length = this.buffer.readUInt32BE(0);
            
            if (this.buffer.length < 4 + length) {
                break;
            }
            
            const jsonBytes = this.buffer.slice(4, 4 + length);
            this.buffer = this.buffer.slice(4 + length);
            
            try {
                const jsonStr = jsonBytes.toString('utf-8');
                const response: Response = JSON.parse(jsonStr);
                
                const callback = this.pendingRequests.get(response.id);
                if (callback) {
                    callback(response);
                }
            } catch (err) {
                Logger.error(`Failed to parse TCP response: ${err}`);
            }
        }
    }
}
