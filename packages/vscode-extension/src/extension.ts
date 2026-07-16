import * as vscode from 'vscode';

import { setExtensionUri } from './module/utils';
import { DCCManager } from './module/dcc/dcc-manager';
import Logger from './module/logging';
import * as execute from './script/execute';
import { reloadWorkspaceModules } from './script/reload';
import { attach } from './script/attach';
import { DCCPythonDashboard, registerDashboardCommands } from './module/panel/dashboard';
import { getExtensionConfig, uriExists, resolvePythonCommand, runPythonCommand, runDCCBridgeCommand } from './module/utils';


export async function activate(context: vscode.ExtensionContext) {
    setExtensionUri(context.extensionUri);

    Logger.info("DCC Python extension activated");

    // 检查 dcc-bridge Python 包是否已安装
    checkDCCBridgeInstallation();

    // 清理临时目录
    const tempDir = vscode.Uri.joinPath(context.globalStorageUri, 'temp');
    if (await uriExists(tempDir)) {
        await vscode.workspace.fs.delete(tempDir, { recursive: true, useTrash: false });
    }

    // 先注册状态栏（使用默认配置），再尝试自动连接
    const dccManager = DCCManager.getInstance();
    dccManager.registerStatusBarItem(context);

    // 启动时自动发现并连接到第一个运行中的 DCC 实例（会覆盖默认的 driver）
    autoConnectToFirstInstance();

    // 注册核心命令
    context.subscriptions.push(
        vscode.commands.registerCommand('dcc-python.execute', () => {
            execute.executeCurrentContext(tempDir);
        }),
        vscode.commands.registerCommand('dcc-python.executeEntryPoint', execute.executeEntryPoint),
        vscode.commands.registerCommand('dcc-python.reloadModules', reloadWorkspaceModules),
        vscode.commands.registerCommand('dcc-python.attach', attach),
        vscode.commands.registerCommand('dcc-python.openDashboard', () => {
            DCCPythonDashboard.createOrShow(context.extensionUri);
        })
    );

    // 注册 Dashboard 树数据提供器及相关命令
    const dashboard = DCCPythonDashboard.getInstance();
    vscode.window.registerTreeDataProvider('dccPythonDashboard', dashboard);
    context.subscriptions.push(dashboard);
    registerDashboardCommands(context);

    // 自动刷新 Dashboard
    const refreshInterval = setInterval(() => {
        dashboard.refresh();
    }, 3000);
    context.subscriptions.push({
        dispose: () => clearInterval(refreshInterval)
    });

    // 窗口获得焦点时刷新实例列表
    context.subscriptions.push(
        vscode.window.onDidChangeWindowState((state) => {
            if (state.focused) {
                dashboard.refresh();
            }
        })
    );
}


export function deactivate() {
    Logger.info("DCC Python extension deactivated");
}


/**
 * 启动时自动发现运行中的 DCC 实例，并连接到第一个找到的实例
 */
async function autoConnectToFirstInstance() {
    try {
        const result = await runDCCBridgeCommand(['status'], { timeout: 5000 });
        if (result.code !== 0 || !result.stdout.trim()) {
            return;
        }
        const parsed = JSON.parse(result.stdout);
        const instances: { dcc_type: string; host: string; port: number }[] =
            parsed && typeof parsed === 'object' && 'instances' in parsed
                ? parsed.instances
                : Array.isArray(parsed) ? parsed : [];

        if (instances.length === 0) {
            return;
        }

        const first = instances[0];
        if (!first || typeof first.port !== 'number' || isNaN(first.port)) {
            Logger.warning(`Auto-connect skipped: invalid instance port`);
            return;
        }
        Logger.info(`Auto-connecting to ${first.dcc_type} @ ${first.host}:${first.port}`);

        const dccManager = DCCManager.getInstance();
        dccManager.setDriverByInstance(first.host, first.port, first.dcc_type);
        await dccManager.connect();

        vscode.window.showInformationMessage(
            `已自动连接到 ${first.dcc_type} (${first.host}:${first.port})`
        );
    } catch {
        // 静默失败，让用户通过 Dashboard 手动选择
    }
}


/**
 * 检查 dcc-bridge Python 包是否已安装
 *
 * 检测方式（任一成功即视为已安装）：
 * 1. Python 解释器能 import dcc_bridge（适用于 pip install 安装方式）
 * 2. 通过 Python 模块执行 `python -m dcc_bridge --version`（适用于虚拟环境安装）
 *
 * 全部失败时弹出提示，引导用户安装。
 */
async function checkDCCBridgeInstallation() {
    const config = getExtensionConfig();
    const skipCheck = config.get<boolean>('skipBridgeCheck', false);
    if (skipCheck) {
        return;
    }

    // 方式一：通过 Python 解释器检查 import
    const pythonCmd = await resolvePythonCommand();
    Logger.info(`Using Python command: ${pythonCmd}`);
    try {
        const result = await runPythonCommand(pythonCmd, ['-c', 'import dcc_bridge; print(dcc_bridge.__version__)']);
        if (result.code === 0 && result.stdout.trim()) {
            Logger.info(`dcc-bridge version: ${result.stdout.trim()}`);
            return;
        }
    } catch {
        // 命令执行失败，继续下一步
    }

    // 方式二：通过 Python 模块方式检测 dcc-bridge
    // 兼容虚拟环境安装（用户配置 pythonPath 后即可使用）
    try {
        const dccResult = await runDCCBridgeCommand(['--version']);
        if (dccResult.code === 0 && dccResult.stdout.trim()) {
            Logger.info(`dcc CLI detected: ${dccResult.stdout.trim()}`);
            return;
        }
    } catch {
        // dcc-bridge 模块或 dcc 命令均不可用
    }

    const selection = await vscode.window.showErrorMessage(
        "DCC Python 需要安装 dcc-bridge Python 包才能与 DCC 通信。",
        "复制安装命令",
        "不再提示"
    );

    if (selection === "复制安装命令") {
        await vscode.env.clipboard.writeText("pip install dcc-bridge");
        vscode.window.showInformationMessage("已复制到剪贴板: pip install dcc-bridge");
    } else if (selection === "不再提示") {
        await config.update('skipBridgeCheck', true, vscode.ConfigurationTarget.Global);
    }
}



