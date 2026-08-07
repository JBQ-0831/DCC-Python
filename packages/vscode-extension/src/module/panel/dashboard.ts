import * as vscode from 'vscode';

import Logger from '../logging';
import { DCCManager } from '../dcc/dcc-manager';
import { runDCCBridgeCommand } from '../utils';


export interface DCCInstance {
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
    private _treeView?: vscode.TreeView<DashboardItem>;
    private _currentItems: DashboardItem[] = [];
    private _connectedHost?: string;
    private _connectedPort?: number;

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
            const isConnected = instance.host === this._connectedHost && instance.port === this._connectedPort;
            const label = `${instance.dcc_name}${instance.dcc_version ? ` ${instance.dcc_version}` : ''} @ ${instance.host}:${instance.port}`;
            const item = new DashboardItem(
                label,
                vscode.TreeItemCollapsibleState.None,
                'instance',
                instance
            );
            if (isConnected) {
                item.description = '(已连接)';
                item.iconPath = new vscode.ThemeIcon('check');
            }
            item.tooltip = `PID: ${instance.pid}\n版本: ${instance.dcc_version || 'unknown'}\n启动时间: ${instance.started_at}\nPython: ${instance.python_path}`;
            item.command = {
                command: 'dcc-python-toolkit.dashboard.selectInstance',
                title: '选择此实例',
                arguments: [instance]
            };
            items.push(item);
        }

        this._currentItems = items;
        return Promise.resolve(items);
    }

    /**
     * 返回指定项的父级。Dashboard 为扁平结构，所有项均为顶层，无父级。
     * 必须实现此方法，否则 VS Code 的 TreeView.reveal() 会抛
     * "Required registered TreeDataProvider to implement 'getParent' method" 错误。
     */
    getParent(_element: DashboardItem): vscode.ProviderResult<DashboardItem> {
        return null;
    }

    /**
     * 绑定 TreeView 引用（替代 registerTreeDataProvider，便于程序化 reveal 选中项）。
     */
    public bindTreeView(): void {
        this._treeView = vscode.window.createTreeView('dccPythonDashboard', { treeDataProvider: this });
    }

    /**
     * 记录当前已连接的实例，用于在 Dashboard 中持久标记「已连接」（3 秒刷新后仍可见）。
     */
    public setConnectedInstance(host?: string, port?: number): void {
        this._connectedHost = host;
        this._connectedPort = port;
        this._onDidChangeTreeData.fire();
    }

    /**
     * 选中并连接指定实例。
     * 手动点击列表项与自动连接共用此方法，确保「连接 + 高亮」体验完全一致：
     * 连接成功后持久标记「已连接」、reveal 设置选中高亮（select+focus）并激活 Explorer 视图使高亮可见。
     */
    public async selectInstance(instance: DCCInstance): Promise<void> {
        if (!instance) {
            vscode.window.showErrorMessage('未收到实例数据，请点击列表项标题而非图标。');
            return;
        }
        const rawPort = instance.port;
        const port = typeof rawPort === 'string' ? parseInt(rawPort, 10) : rawPort;
        if (typeof port !== 'number' || isNaN(port)) {
            vscode.window.showErrorMessage(`实例数据无效（端口缺失或无效: ${rawPort}），请刷新 Dashboard 后重试。`);
            return;
        }
        Logger.info(`[Dashboard] selecting instance: ${instance.host}:${port} (${instance.dcc_name})`);
        const dccManager = DCCManager.getInstance();
        dccManager.setDriverByInstance(instance.host, port, instance.dcc_name, instance.python_path);
        const connected = await dccManager.connect();
        if (!connected) {
            vscode.window.showErrorMessage(`无法连接到 DCC 实例: ${instance.dcc_name} @ ${instance.host}:${instance.port}`);
            return;
        }
        this.setConnectedInstance(instance.host, port);
        // 与手动点击左键一致：reveal 设置选中高亮，并激活 Explorer 视图使高亮条可见
        await this.revealInstance(instance.host, port);
        await vscode.commands.executeCommand('workbench.view.explorer');
        vscode.window.showInformationMessage(`已连接到 DCC 实例: ${instance.dcc_name} @ ${instance.host}:${instance.port}`);
    }

    /**
     * 在 Dashboard 树中聚焦并选中指定 host:port 的实例。
     * 注意：reveal 要求目标项已被 TreeView 渲染注册，且通过 id 匹配（不依赖对象引用相等）。
     * 因此先加载数据并 fire 触发渲染、等待渲染完成，再用 id 查找目标项 reveal，并加轻量重试兜住偶发渲染延迟。
     */
    public async revealInstance(host: string, port: number): Promise<void> {
        if (!this._treeView) {
            return;
        }
        // 1. 确保实例数据已加载（autoConnect 时 Dashboard 自身列表可能尚未加载）
        await this._loadInstances();
        // 2. 触发 TreeView 重新渲染，使目标项被 VS Code 注册（reveal 的前提）
        this._onDidChangeTreeData.fire();
        // 3. 等待 TreeView 异步渲染完成
        await new Promise<void>((resolve) => setTimeout(resolve, 80));

        // 4. 按稳定 id 查找目标项（与渲染时项 id 一致，不依赖对象引用相等）
        const targetId = `${host}:${port}`;
        const target = this._currentItems.find((i) => i.id === targetId);
        if (!target) {
            return;
        }

        // 5. 轻量重试：TreeView 渲染为异步，偶发首次 reveal 时节点尚未就绪
        const maxRetries = 3;
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                await this._treeView.reveal(target, { select: true, focus: true });
                // reveal 已设置选中+聚焦，至少完成高亮；list 命令仅是弱环境下的兜底，
                // 其失败（如树无焦点时 'list.focus' 未注册）不重试、不告警，交由 reveal 兜底
                this._applyListFocusFallback();
                return;
            } catch (err) {
                Logger.warning(`[Dashboard] revealInstance attempt ${attempt} failed: ${err}`);
                if (attempt < maxRetries) {
                    await new Promise<void>((resolve) => setTimeout(resolve, 150));
                }
            }
        }
    }

    /**
     * 兜底：程序化 reveal 的高亮渲染在部分环境弱于鼠标点击，
     * 用 list.focus 确保焦点落到树、list.select 选中焦点项，复现点击式蓝条高亮。
     * 注意：list.focus / list.select 是上下文命令，仅在树获得焦点时才被注册；
     * 部分时刻（如从通知/命令面板返回）树无焦点导致命令不存在，此时 reveal 已足够完成选中，
     * 故任何异常一律静默忽略，不重试、不告警。
     */
    private async _applyListFocusFallback(): Promise<void> {
        try {
            await vscode.commands.executeCommand('workbench.view.explorer');
            await vscode.commands.executeCommand('list.focus');
            await vscode.commands.executeCommand('list.select');
        } catch {
            // 静默忽略：list.* 命令缺失或非树焦点上下文时不可用，不影响 reveal 已完成的选中
        }
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
            // 稳定 id：让 VS Code 用 id 匹配 reveal 目标，而非依赖对象引用相等
            this.id = instance ? `${instance.host}:${instance.port}` : label;
        } else if (itemType === 'action') {
            this.iconPath = new vscode.ThemeIcon('refresh');
            this.id = label;
        } else if (itemType === 'error') {
            this.iconPath = new vscode.ThemeIcon('error');
            this.id = 'dashboard-error';
        } else {
            this.iconPath = new vscode.ThemeIcon('info');
            this.id = 'dashboard-info';
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
                const dashboard = DCCPythonDashboard.getInstance();
                await dashboard.selectInstance(instance);
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
