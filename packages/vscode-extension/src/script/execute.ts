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
        gOutputChannel = vscode.window.createOutputChannel("DCC Python ToolKit");
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
            const failed = !response.success || !!response.error;

            if (response.output.length > 0) {
                for (const line of response.output) {
                    if (line !== "\n") {
                        outputChannel.appendLine(line);
                    }
                }
            }

            if (failed) {
                // 执行失败时把错误与回溯呈现给用户，避免只看到 ">>>" 而无感知
                if (response.error) {
                    outputChannel.appendLine("Error: " + response.error);
                }
                if (response.traceback) {
                    outputChannel.appendLine(response.traceback);
                }
                outputChannel.appendLine(">>> [执行失败]");
                vscode.window.showErrorMessage(
                    "DCC 执行失败：" + (response.error || "未知错误")
                );
            } else {
                outputChannel.appendLine(">>>");
            }

            if (config.get<boolean>("execute.showOutput")) {
                outputChannel.show(true);
            }
        }
    }
}


/**
 * 提示用户没有可用的 DCC 服务端连接
 * 引导用户使用 Dashboard 或 dcc setup 命令完成一次性配置
 */
export async function promptStartServer(): Promise<void> {
    const result = await vscode.window.showErrorMessage(
        '未连接到 DCC 服务端。请先打开 DCC，或配置 DCC 自启动桥接服务。',
        '打开 Dashboard',
    );

    if (result === '打开 Dashboard') {
        await vscode.commands.executeCommand('dcc-python-toolkit.openDashboard');
    }

    Logger.error('No DCC server reachable. Use "dcc setup <dcc>" or the Dashboard to configure auto-start.');
}


/**
 * Execute a predefined entry point script
 */
export async function executeEntryPoint() {
    const extConfig = utils.getExtensionConfig();
    const entryPointPath = extConfig.get<string>("execute.entryPoint");

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
