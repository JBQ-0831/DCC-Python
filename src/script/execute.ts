import * as vscode from 'vscode';

import * as crypto from 'crypto';
import * as path from 'path';

import * as vsCodeExec from '../module/code-exec';
import * as utils from '../module/utils';
import * as reload from './reload';
import { DCCManager } from '../module/dcc/dcc-manager';

import Logger from '../module/logging';


let gOutputChannel: vscode.OutputChannel | undefined;
let cachedEntryPointPath: vscode.Uri | undefined;


export function getOutputChannel(bEnsureChannelExists = true) {
    if (!gOutputChannel && bEnsureChannelExists) {
        gOutputChannel = vscode.window.createOutputChannel("DCC Python");
    }

    return gOutputChannel;
}


async function executeFile(fileUri: vscode.Uri, execOrigin: string) {
    const config = utils.getExtensionConfig();

    if (config.get<boolean>("execute.clearOutput")) {
        const outputChannel = getOutputChannel(false);
        if (outputChannel) {
            outputChannel.clear();
        }
    }

    const isDebugging = utils.isDebuggingDCC();
    const dccManager = DCCManager.getInstance();
    const driver = dccManager.getCurrentDriver();

    Logger.info(`[DEBUG] executeFile: isDebugging=${isDebugging}, hasDriver=${!!driver}, file=${fileUri.fsPath}`);

    if (!driver) {
        await promptStartServer();
        return;
    }

    // 不提前检查 isConnected()，让 sendRequest 内部自动连接
    const response = await driver.executeFile(
        fileUri.fsPath,
        execOrigin,
        config.get<string>("execute.name", "__main__"),
        isDebugging
    );

    if (response === null) {
        await promptStartServer();
        return;
    }

    if (!isDebugging) {
        const outputChannel = getOutputChannel(true);
        if (response !== null && outputChannel) {
            if (response.output.length > 0) {
                for (const line of response.output) {
                    if (line !== "\n") {
                        outputChannel.appendLine(line);
                    }
                }
            }

            outputChannel.appendLine(">>>");

            if (config.get<boolean>("execute.showOutput")) {
                outputChannel.show(true);
            }
        }
    }
}


/**
 * 提示用户在 DCC 中运行 start.py 启动服务端
 * 提供"复制启动代码"按钮，点击后把多行格式化代码写入剪贴板
 */
export async function promptStartServer(): Promise<void> {
    const dccManager = DCCManager.getInstance();
    const startScriptPath = dccManager.getStartScriptPath();
    const config = utils.getExtensionConfig();
    const port = config.get<number>('server.port', 7002);
    
    if (!startScriptPath) {
        const msg = 'start.py 文件未找到，生成启动代码失败!';
        Logger.error(msg);
        vscode.window.showErrorMessage(msg);
        return;
    }
    
    const startCode = [
        'exec(r"""',
        'import sys',
        'import os',
        `script_path = r"${startScriptPath}"`,
        'site_packages_dir = os.path.dirname(os.path.dirname(script_path))',
        'if site_packages_dir not in sys.path:',
        '    sys.path.insert(0, site_packages_dir)',
        'from vscode_dcc.start import start_server',
        `start_server(port=${port})`,
        '""")'
    ].join('\n');
    
    const shortMsg = '请在你的 DCC 软件中运行 Python 代码启动服务端（点击"复制启动代码"按钮）';
    
    const result = await vscode.window.showErrorMessage(
        shortMsg,
        '复制启动代码'
    );
    
    if (result === '复制启动代码') {
        await vscode.env.clipboard.writeText(startCode);
        vscode.window.showInformationMessage('启动代码已复制到剪贴板，请粘贴到 DCC 中运行');
    }
    
    Logger.error(`${shortMsg}\n\n${startCode}`);
}


/**
 * Execute a predefined entry point script
 */
export async function executeEntryPoint() {
    const extConfig = utils.getExtensionConfig();
    const entryPointPath = extConfig.get<string>("execute.entryPointPath");

    let fileUri: vscode.Uri | undefined = undefined;
    if (entryPointPath) {
        if (path.isAbsolute(entryPointPath)) {
            fileUri = vscode.Uri.file(entryPointPath);
        }
        else {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            for (const folder of workspaceFolders || []) {
                const possiblePath = path.join(folder.uri.fsPath, entryPointPath);
                if (await utils.uriExists(vscode.Uri.file(possiblePath))) {
                    fileUri = vscode.Uri.file(possiblePath);
                    break;
                }
            }
        }

        if (!fileUri || !await utils.uriExists(fileUri)) {
            Logger.error(`Entry point path does not exist: ${entryPointPath}`);
            vscode.window.showErrorMessage(`Entry point path does not exist: ${entryPointPath}`);
            return;
        }

    }
    else if (cachedEntryPointPath && await utils.uriExists(cachedEntryPointPath)) {
        fileUri = cachedEntryPointPath;
    }
    else {
        const files = await vscode.workspace.findFiles('**/*.py', '**/env/**');

        const items: vscode.QuickPickItem[] = files.map(file => {
            return {
                label: '',
                resourceUri: file,
                iconPath: vscode.ThemeIcon.File
            };
        });

        const selected = await vscode.window.showQuickPick(items, {
            prompt: "Select a Python file to execute as the entry point",
            canPickMany: false,
            title: "Execute Entry Point",
        });

        if (!selected?.resourceUri) {
            return;
        }

        cachedEntryPointPath = selected.resourceUri;
        fileUri = cachedEntryPointPath;
    }

    if (extConfig.get<boolean>("execute.entryPointReload")) {
        await reload.reloadWorkspaceModules();
    }

    await executeFile(fileUri, fileUri.fsPath);
}


export async function executeCurrentContext(tempDir: vscode.Uri) {
    if (vscode.window.activeTextEditor === undefined) {
        return;
    }

    const id = crypto.randomUUID().replace(/-/g, "_");
    const tempUri = vscode.Uri.joinPath(tempDir, `exec_${id}.py`);

    const executeUri = await vsCodeExec.getFileToExecute(tempUri);
    if (!executeUri) {
        return;
    }

    // 使用实际文件路径作为 exec_origin，让 debugpy 能正确匹配断点
    // 而非硬编码的 "current_context"
    const activeDocument = vscode.window.activeTextEditor.document;
    const execOrigin = activeDocument.uri.fsPath;

    await executeFile(executeUri, execOrigin);

    if (await utils.uriExists(tempUri)) {
        await vscode.workspace.fs.delete(tempUri, { useTrash: false });
    }
}
