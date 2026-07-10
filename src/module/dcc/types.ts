/**
 * DCC 驱动相关类型定义
 */

export interface IDCCConfig {
    host: string;
    port: number;
    driverType: string;
}

export interface IExecutionResult {
    output: string[];
    success: boolean;
    error?: string;
    traceback?: string;
}

export interface IDCCDriver {
    readonly dccName: string;
    readonly dccType: string;
    
    connect(): Promise<boolean>;
    disconnect(): void;
    isConnected(): boolean;
    
    executeFile(execFile: string, execOrigin: string, nameVar: string, isDebugging: boolean): Promise<IExecutionResult | null>;
    evaluateFunction(module: string, functionName: string, kwargs?: Record<string, any>, discardOutput?: boolean): Promise<IExecutionResult | null>;
    sendCommand(command: string, options?: { discardOutput?: boolean }): Promise<IExecutionResult | null>;
    reloadModules(workspaceFolders: string[]): Promise<IExecutionResult | null>;
    
    importDebugpy(): Promise<boolean | undefined>;
    installDebugpy(): Promise<boolean | undefined>;
    startDebugServer(port: number): Promise<boolean>;
    
    getHost(): string;
    getPort(): number;
    
    updateConfig(config: IDCCConfig): void;
}