import * as vscode from 'vscode';

import { DCCManager } from '../module/dcc/dcc-manager';
import Logger from '../module/logging';


let isCommandRegistered = false;


export async function reloadWorkspaceModules() {
    const disposableStatusMessage = vscode.window.setStatusBarMessage("$(sync~spin) Reloading modules...", 5000);

    const workspaceFolders = vscode.workspace.workspaceFolders?.map(folder => folder.uri.fsPath) || [];

    const dccManager = DCCManager.getInstance();
    const driver = dccManager.getCurrentDriver();

    if (!driver) {
        disposableStatusMessage.dispose();
        Logger.error("No DCC driver selected. Please select a DCC from the status bar.");
        vscode.window.showErrorMessage("No DCC driver selected. Please select a DCC from the status bar.");
        return;
    }

    const response = await driver.reloadModules(workspaceFolders);

    disposableStatusMessage.dispose();

    if (!response) {
        return;
    }

    const failedOutput = response.output.filter((line: string) => line.startsWith("Failed"));
    const successOutput = response.output.filter((line: string) => line.startsWith("Reloaded"));

    if (failedOutput.length <= 0 && successOutput.length > 0) {
        const successMessage = successOutput[0];
        vscode.window.setStatusBarMessage(`$(check) ${successMessage}`, 3500);
        Logger.info(successMessage);
    }
    else if (!isCommandRegistered) {
        for (const line of failedOutput) {
            Logger.error(line);
        }

        const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 5);
        statusBarItem.text = `$(error) Failed to reload ${failedOutput.length} module${failedOutput.length === 1 ? '' : 's'}`;
        statusBarItem.command = "dcc-python-toolkit.showReloadErrorMessage";
        statusBarItem.color = new vscode.ThemeColor('errorForeground');

        const timeout = setTimeout(() => {
            dispose();
        }, 5000);

        const commandDisposable = vscode.commands.registerCommand(statusBarItem.command, () => {
            Logger.channel.show();
            clearTimeout(timeout);
            dispose();
        });

        const dispose = () => {
            statusBarItem.dispose();
            commandDisposable.dispose();
            isCommandRegistered = false;
        };

        statusBarItem.show();

        isCommandRegistered = true;
    }
}
