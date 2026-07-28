import * as vscode from 'vscode';

import Logger from '../logging';
import { DCCManager } from '../dcc/dcc-manager';
import { runDCCBridgeCommand } from '../utils';


interface DCCInstance {
    pid: number;
    dcc_name: string;
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
            const result = await runDCCBridgeCommand(['status'], { timeout: 5000 });
            if (result.code !== 0) {
                throw new Error(result.stderr || `exit code ${result.code}`);
            }
            const { stdout } = result;
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
            const label = `${instance.dcc_name}${instance.dcc_version ? ` ${instance.dcc_version}` : ''} @ ${instance.host}:${instance.port}`;
            const item = new DashboardItem(
                label,
                vscode.TreeItemCollapsibleState.None,
                'instance',
                instance
            );
            item.tooltip = `PID: ${instance.pid}\n版本: ${instance.dcc_version || 'unknown'}\n启动时间: ${instance.started_at}\nPython: ${instance.python_path}`;
            item.command = {
                command: 'dcc-python-toolkit.dashboard.selectInstance',
                title: '选择此实例',
                arguments: [instance]
            };
            items.push(item);
        }

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
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.selectInstance', async (arg: DCCInstance | DashboardItem) => {
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
                Logger.info(`[Dashboard] selecting instance: ${instance.host}:${port} (${instance.dcc_name})`);
                const dccManager = DCCManager.getInstance();
                dccManager.setDriverByInstance(instance.host, port, instance.dcc_name);
                const connected = await dccManager.connect();
                if (connected) {
                    vscode.window.showInformationMessage(`已连接到 DCC 实例: ${instance.dcc_name} @ ${instance.host}:${instance.port}`);
                } else {
                    vscode.window.showErrorMessage(`无法连接到 DCC 实例: ${instance.dcc_name} @ ${instance.host}:${instance.port}`);
                }
            } catch (err) {
                const message = `选择实例失败: ${err}`;
                Logger.error(message);
                vscode.window.showErrorMessage(message);
            }
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.setupMaya', async () => {
            await runSetupCommand('maya');
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.setupMax', async () => {
            await runSetupCommand('3dsmax');
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.setupSP', async () => {
            await runSetupCommand('substance_painter');
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.setupSD', async () => {
            await runSetupCommand('substance_designer');
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.unsetupMaya', async () => {
            await runSetupCommand('maya', true);
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.unsetupMax', async () => {
            await runSetupCommand('3dsmax', true);
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.unsetupSP', async () => {
            await runSetupCommand('substance_painter', true);
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.unsetupSD', async () => {
            await runSetupCommand('substance_designer', true);
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.setupHoudini', async () => {
            await runSetupCommand('houdini');
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.unsetupHoudini', async () => {
            await runSetupCommand('houdini', true);
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.setupBlender', async () => {
            await runSetupCommand('blender');
        }),
        vscode.commands.registerCommand('dcc-python-toolkit.dashboard.unsetupBlender', async () => {
            await runSetupCommand('blender', true);
        })
    );
}


async function runSetupCommand(dccType: string, unsetup: boolean = false) {
    const args = unsetup ? ['unsetup', dccType] : ['setup', dccType];

    // Setup 时读取用户配置的 pip 镜像源
    if (!unsetup) {
        const config = vscode.workspace.getConfiguration('dcc-python-toolkit');
        const mirrorUrl: string = config.get('pip.indexUrl', '');
        if (mirrorUrl.trim()) {
            args.push('--pip-index-url', mirrorUrl.trim());
        }
    }

    const cmdText = `dcc ${args.join(' ')}`;
    // 显示 log 输出频道，让用户看到实时进度
    Logger.channel.show(true);
    Logger.info(`=== ${cmdText} 开始执行 ===`);
    try {
        // 不设超时：网络速度不可预判，避免误报超时
        const result = await runDCCBridgeCommand(args);
        // 逐行输出 stdout 到 log 频道
        if (result.stdout) {
            const lines = result.stdout.split('\n');
            for (const line of lines) {
                if (line.trim()) {
                    Logger.info(line);
                }
            }
        }
        if (result.stderr) {
            const lines = result.stderr.split('\n');
            for (const line of lines) {
                if (line.trim()) {
                    Logger.warning(line);
                }
            }
        }
        if (result.code !== 0) {
            Logger.error(`${cmdText} 执行失败 (exit code ${result.code})`);
            vscode.window.showErrorMessage(`${cmdText} 执行失败，详情请查看 DCC Python ToolKit Log 输出频道。`);
            return;
        }
        Logger.info(`=== ${cmdText} 执行完成 ===`);
        vscode.window.showInformationMessage(`${cmdText} 执行完成`);
    } catch (error) {
        const message = `${cmdText} 执行失败: ${error}`;
        Logger.error(message);
        vscode.window.showErrorMessage(message);
    }
}
