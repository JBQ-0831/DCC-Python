import * as vscode from 'vscode';
import * as childProcess from 'child_process';
import { promisify } from 'util';

import Logger from '../logging';
import { DCCManager } from '../dcc/dcc-manager';


const execAsync = promisify(childProcess.exec);


interface DCCInstance {
    pid: number;
    dcc_type: string;
    dcc_version: string;
    host: string;
    port: number;
    started_at: string;
    python_path: string;
}


export class DCCPythonDashboard implements vscode.TreeDataProvider<DashboardItem>, vscode.Disposable {
    private static instance: DCCPythonDashboard | undefined;
    private _onDidChangeTreeData: vscode.EventEmitter<DashboardItem | undefined | void> = new vscode.EventEmitter<DashboardItem | undefined | void>();
    public readonly onDidChangeTreeData: vscode.Event<DashboardItem | undefined | void> = this._onDidChangeTreeData.event;

    private _instances: DCCInstance[] = [];
    private _error: string | undefined;

    private constructor() { }

    public static getInstance(): DCCPythonDashboard {
        if (!DCCPythonDashboard.instance) {
            DCCPythonDashboard.instance = new DCCPythonDashboard();
        }
        return DCCPythonDashboard.instance;
    }

    public static createOrShow(_extensionUri: vscode.Uri) {
        // Explorer 视图会自动显示，此方法用于刷新
        const dashboard = DCCPythonDashboard.getInstance();
        dashboard.refresh();
        vscode.commands.executeCommand('workbench.view.explorer');
    }

    public refresh(): void {
        this._loadInstances().then(() => {
            this._onDidChangeTreeData.fire();
        });
    }

    private async _loadInstances(): Promise<void> {
        try {
            const { stdout } = await execAsync('dcc status', { timeout: 5000 });
            const parsed = JSON.parse(stdout);
            // dcc status 返回 { instances: [...], count: N }
            if (parsed && typeof parsed === 'object' && 'instances' in parsed) {
                this._instances = Array.isArray(parsed.instances) ? parsed.instances : [];
            } else if (Array.isArray(parsed)) {
                this._instances = parsed;
            } else {
                this._instances = [];
            }
            this._error = undefined;
        } catch (error) {
            this._instances = [];
            this._error = `无法获取 DCC 实例: ${error}`;
            Logger.warning(this._error);
        }
    }

    getTreeItem(element: DashboardItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: DashboardItem): Thenable<DashboardItem[]> {
        if (element) {
            return Promise.resolve([]);
        }

        const items: DashboardItem[] = [];

        if (this._error) {
            items.push(new DashboardItem(this._error, vscode.TreeItemCollapsibleState.None, 'error'));
        }

        if (this._instances.length === 0 && !this._error) {
            items.push(new DashboardItem(
                "未找到运行中的 DCC 实例",
                vscode.TreeItemCollapsibleState.None,
                'info'
            ));
        }

        for (const instance of this._instances) {
            const label = `${instance.dcc_type}${instance.dcc_version ? ` ${instance.dcc_version}` : ''} @ ${instance.host}:${instance.port}`;
            const item = new DashboardItem(
                label,
                vscode.TreeItemCollapsibleState.None,
                'instance',
                instance
            );
            item.tooltip = `PID: ${instance.pid}\n版本: ${instance.dcc_version || 'unknown'}\n启动时间: ${instance.started_at}\nPython: ${instance.python_path}`;
            item.command = {
                command: 'dcc-python.dashboard.selectInstance',
                title: '选择此实例',
                arguments: [instance]
            };
            items.push(item);
        }

        // 快捷操作
        items.push(new DashboardItem(
            "刷新",
            vscode.TreeItemCollapsibleState.None,
            'action',
            undefined,
            { command: 'dcc-python.openDashboard', title: '刷新' }
        ));

        return Promise.resolve(items);
    }

    dispose() {
        DCCPythonDashboard.instance = undefined;
    }
}


class DashboardItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly itemType: 'instance' | 'action' | 'error' | 'info',
        public readonly instance?: DCCInstance,
        command?: vscode.Command
    ) {
        super(label, collapsibleState);
        this.contextValue = itemType;

        if (itemType === 'instance') {
            this.iconPath = new vscode.ThemeIcon('server-environment');
        } else if (itemType === 'action') {
            this.iconPath = new vscode.ThemeIcon('refresh');
        } else if (itemType === 'error') {
            this.iconPath = new vscode.ThemeIcon('error');
        } else {
            this.iconPath = new vscode.ThemeIcon('info');
        }

        if (command) {
            this.command = command;
        }
    }
}


/**
 * 注册 Dashboard 相关的命令
 */
export function registerDashboardCommands(context: vscode.ExtensionContext) {
    context.subscriptions.push(
        vscode.commands.registerCommand('dcc-python.dashboard.selectInstance', async (arg: DCCInstance | DashboardItem) => {
            try {
                // VS Code TreeView 点击时可能传入 DashboardItem 本身，而非 command.arguments[0]
                const instance = arg && 'instance' in arg && arg.instance ? arg.instance : arg as DCCInstance;
                Logger.info(`[Dashboard] selectInstance received arg type=${typeof arg}, resolved instance=${JSON.stringify(instance)}`);
                if (!instance) {
                    vscode.window.showErrorMessage('未收到实例数据，请点击列表项标题而非图标。');
                    return;
                }
                const rawPort = instance.port;
                const port = typeof rawPort === 'string' ? parseInt(rawPort, 10) : rawPort;
                Logger.info(`[Dashboard] rawPort=${rawPort} (type=${typeof rawPort}), parsed port=${port}`);
                if (typeof port !== 'number' || isNaN(port)) {
                    vscode.window.showErrorMessage(`实例数据无效（端口缺失或无效: ${rawPort}），请刷新 Dashboard 后重试。`);
                    return;
                }
                Logger.info(`[Dashboard] selecting instance: ${instance.host}:${port} (${instance.dcc_type})`);
                const dccManager = DCCManager.getInstance();
                dccManager.setDriverByInstance(instance.host, port, instance.dcc_type);
                const connected = await dccManager.connect();
                if (connected) {
                    vscode.window.showInformationMessage(`已连接到 DCC 实例: ${instance.dcc_type} @ ${instance.host}:${instance.port}`);
                } else {
                    vscode.window.showErrorMessage(`无法连接到 DCC 实例: ${instance.dcc_type} @ ${instance.host}:${instance.port}`);
                }
            } catch (err) {
                const message = `选择实例失败: ${err}`;
                Logger.error(message);
                vscode.window.showErrorMessage(message);
            }
        }),
        vscode.commands.registerCommand('dcc-python.dashboard.setupMaya', async () => {
            await runSetupCommand('maya');
        }),
        vscode.commands.registerCommand('dcc-python.dashboard.setupMax', async () => {
            await runSetupCommand('3dsmax');
        }),
        vscode.commands.registerCommand('dcc-python.dashboard.setupSP', async () => {
            await runSetupCommand('substance_painter');
        }),
        vscode.commands.registerCommand('dcc-python.dashboard.setupSD', async () => {
            await runSetupCommand('substance_designer');
        }),
        vscode.commands.registerCommand('dcc-python.dashboard.unsetupMaya', async () => {
            await runSetupCommand('maya', true);
        }),
        vscode.commands.registerCommand('dcc-python.dashboard.unsetupMax', async () => {
            await runSetupCommand('3dsmax', true);
        }),
        vscode.commands.registerCommand('dcc-python.dashboard.unsetupSP', async () => {
            await runSetupCommand('substance_painter', true);
        }),
        vscode.commands.registerCommand('dcc-python.dashboard.unsetupSD', async () => {
            await runSetupCommand('substance_designer', true);
        })
    );
}


async function runSetupCommand(dccType: string, unsetup: boolean = false) {
    const cmd = unsetup ? `dcc unsetup ${dccType}` : `dcc setup ${dccType}`;
    try {
        const { stdout, stderr } = await execAsync(cmd, { timeout: 30000 });
        if (stderr) {
            Logger.warning(stderr);
        }
        Logger.info(stdout);
        vscode.window.showInformationMessage(`${cmd} 执行完成`);
    } catch (error) {
        const message = `${cmd} 执行失败: ${error}`;
        Logger.error(message);
        vscode.window.showErrorMessage(message);
    }
}
