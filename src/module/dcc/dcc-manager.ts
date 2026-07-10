/**
 * DCC 连接管理器
 * 
 * 负责管理与 DCC 服务端的 TCP 连接，集成状态栏 UI
 */

import * as vscode from 'vscode';

import * as utils from '../utils';
import Logger from '../logging';

import type { IDCCDriver, IDCCConfig } from './types';
import { TCPDriver } from './tcp-driver';

export class DCCManager {
    private driver: IDCCDriver | null = null;
    private statusBarItem: vscode.StatusBarItem | null = null;
    private startScriptPath: string | null = null;
    
    private static instance: DCCManager | null = null;
    
    private constructor() {
    }
    
    public async initialize(context: vscode.ExtensionContext): Promise<void> {
        this.initDriver();
        this.initStatusBar(context);
        
        context.subscriptions.push(
            vscode.workspace.onDidChangeConfiguration((event) => {
                if (event.affectsConfiguration('dcc-python.server')) {
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
    
    private initDriver(): void {
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
    
    private initStatusBar(context: vscode.ExtensionContext): void {
        // 获取 start.py 的路径
        this.startScriptPath = this._resolveStartScriptPath(context);
        
        this.statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 5);
        this.updateStatusBar();
        this.statusBarItem.show();
    }
    
    private _resolveStartScriptPath(context: vscode.ExtensionContext): string {
        // 扩展安装路径下的 site-packages/vscode_dcc/start.py
        const extensionPath = context.extensionPath;
        const startScript = vscode.Uri.joinPath(
            vscode.Uri.file(extensionPath),
            'site-packages',
            'vscode_dcc',
            'start.py'
        );
        return startScript.fsPath;
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
            if (this.startScriptPath) {
                this.statusBarItem.tooltip = `请在你的 DCC 软件中运行 Python 代码启动服务端`;
            } else {
                this.statusBarItem.tooltip = 'start.py 文件未找到，生成启动代码失败!';
            }
        }
    }
    
    getCurrentDriver(): IDCCDriver | null {
        return this.driver;
    }
    
    getStartScriptPath(): string | null {
        return this.startScriptPath;
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
        this.initDriver();
        this.updateStatusBar();
    }
    
    dispose(): void {
        this.disconnect();
        if (this.statusBarItem) {
            this.statusBarItem.dispose();
        }
    }
}