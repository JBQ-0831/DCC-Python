import * as vscode from 'vscode';

import * as utils from './module/utils';
import { DCCManager } from './module/dcc/dcc-manager';

import * as execute from './script/execute';
import * as reload from './script/reload';
import * as attach from './script/attach';
import { startVSCodeServer, stopVSCodeServer } from './module/vscode-server';
import * as cliInstaller from './module/cli-installer';

export async function activate(context: vscode.ExtensionContext) {
	utils.setExtensionUri(context.extensionUri);

	const tempDir = vscode.Uri.joinPath(context.globalStorageUri, 'temp');
	if (await utils.uriExists(tempDir)) {
		await vscode.workspace.fs.delete(tempDir, { recursive: true, useTrash: false });
	}

	const dccManager = DCCManager.getInstance();
	await dccManager.initialize(context);

	context.subscriptions.push(
		vscode.commands.registerCommand('dcc-python.execute', () => {
			execute.executeCurrentContext(tempDir);
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('dcc-python.executeEntryPoint', () => {
			execute.executeEntryPoint();
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('dcc-python.reloadModules', () => {
			reload.reloadWorkspaceModules();
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('dcc-python.attach', () => {
			attach.attach();
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('dcc-python.installCli', async () => {
			try {
				await cliInstaller.ensureCliInstalled(context.extensionPath, true);
			} catch {
				// 错误已在 ensureCliInstalled 内部提示
			}
		})
	);

	// 启动 VS Code 内部 socket 服务端，接收外部 execute_file 请求
	startVSCodeServer();

	// 自动安装 dcc-run CLI（若尚未安装）
	cliInstaller.ensureCliInstalled(context.extensionPath, true).catch(() => {
		// 安装失败不阻塞扩展激活，错误已在内部提示
	});

	context.subscriptions.push({
		dispose: () => {
			dccManager.dispose();
			stopVSCodeServer();
		}
	});
}


export function deactivate() {
	const dccManager = DCCManager.getInstance();
	dccManager.dispose();
	stopVSCodeServer();
}