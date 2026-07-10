import * as vscode from 'vscode';

import * as utils from './module/utils';
import { DCCManager } from './module/dcc/dcc-manager';

import * as execute from './script/execute';
import * as reload from './script/reload';
import * as attach from './script/attach';

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

	context.subscriptions.push({
		dispose: () => {
			dccManager.dispose();
		}
	});
}


export function deactivate() {
	const dccManager = DCCManager.getInstance();
	dccManager.dispose();
}