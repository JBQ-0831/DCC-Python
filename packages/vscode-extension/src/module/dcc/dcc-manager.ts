/**
 * DCC 连接管理器
 * 
 * 负责管理与 DCC 服务端的 TCP 连接，集成状态栏 UI。
 * 重构后不再依赖扩展内置的 site-packages，而是通过 dcc-bridge 包与 DCC 通信。
 */

import * as vscode from 'vscode';

import * as utils from '../utils';

import type { IDCCDriver, IDCCConfig } from './types';
import { TCPDriver } from './tcp-driver';


export class DCCManager {
    private driver: IDCCDriver | null = null;
    private statusBarItem: vscode.StatusBarItem | null = null;
    
    private static instance: DCCManager | null = null;
    
    private constructor() {
    }
    
    public registerStatusBarItem(context: vscode.ExtensionContext): void {
        this.initDriver();
        this.initStatusBar(context);
        
        context.subscriptions.push(
            vscode.workspace.onDidChangeConfiguration((event) => {
                if (event.affectsConfiguration('dcc-python-toolkit.server')) {
                    this._onServerConfigChanged();
                }
            })
        );
    }
    
    public static getInstance(): DCCManager {
        if (!DCCManager.instance) {
            DCCManager.instance = new DCCManager();
        }
        return DCCManager.instance;
    }
    
    private initDriver(force: boolean = false): void {
        if (this.driver && !force) {
            return;
        }

        const config = utils.getExtensionConfig();
        const host = config.get<string>('server.host', '127.0.0.1');
        const port = config.get<number>('server.port', 7002);
        
        const driverConfig: IDCCConfig = {
            host,
            port,
            driverType: 'tcp-json-rpc'
        };
        
        this.driver = new TCPDriver(driverConfig, 'dcc', 'DCC');
    }
    
    private initStatusBar(_context: vscode.ExtensionContext): void {
        this.statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 5);
        this.updateStatusBar();
        this.statusBarItem.show();
    }
    
    private updateStatusBar(): void {
        if (!this.statusBarItem) {
            return;
        }
        
        const isConnected = this.driver?.isConnected() ?? false;
        
        if (isConnected) {
            this.statusBarItem.text = '$(check) DCC Connected';
            this.statusBarItem.tooltip = 'Connected to DCC server';
        } else {
            this.statusBarItem.text = '$(circle-outline) DCC';
            this.statusBarItem.tooltip = '点击连接 DCC 服务，或使用 DCC Python ToolKit: Open Dashboard 查看运行中的实例';
        }
    }
    
    getCurrentDriver(): IDCCDriver | null {
        return this.driver;
    }
    
    /**
     * 根据 host/port 切换当前驱动
     */
    setDriverByInstance(host: string, port: number, dccType: string, pythonPath?: string): void {
        if (this.driver) {
            this.driver.disconnect();
        }

        const normalizedType = dccType || 'unknown';

        const driverConfig: IDCCConfig = {
            host,
            port,
            driverType: 'tcp-json-rpc'
        };

        this.driver = new TCPDriver(driverConfig, normalizedType, normalizedType.toUpperCase(), pythonPath);
        this.updateStatusBar();
    }
    
    async connect(): Promise<boolean> {
        if (!this.driver) {
            return false;
        }
        
        const connected = await this.driver.connect();
        this.updateStatusBar();
        return connected;
    }
    
    disconnect(): void {
        if (this.driver) {
            this.driver.disconnect();
        }
        this.updateStatusBar();
    }
    
    private _onServerConfigChanged(): void {
        const driver = this.getCurrentDriver();
        if (driver) {
            driver.disconnect();
        }
        this.initDriver(true);
        this.updateStatusBar();
    }
    
    dispose(): void {
        this.disconnect();
        if (this.statusBarItem) {
            this.statusBarItem.dispose();
        }
    }
}
