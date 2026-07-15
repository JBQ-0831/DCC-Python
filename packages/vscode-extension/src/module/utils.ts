import * as vscode from 'vscode';

export const EXTENSION_ID = "dcc-python";
export const DEBUG_SESSION_NAME = "DCC Python"; // The name of the DCC debug session


let _extensionUri: vscode.Uri | undefined; // Stores the absolute path to this extension's directory, set on activation


/**
 * This function should only be called once, on activation
 * @param uri Should be: `ExtensionContext.extensionPath`
 */
export function setExtensionUri(uri: vscode.Uri) {
    _extensionUri = uri;
}

/**
 * This function cannot be called in top-level. It must be called after the extension has been activated
 * @returns The absolute path to this extension's directory
 */
export function getExtensionUri(): vscode.Uri {
    if (!_extensionUri) {
        throw Error("Extension Dir hasn't been set yet! This should be set on activation. This function cannot be called in top-level.");
    }
    return _extensionUri;
}

/**
 * Get the workspace folder for the currently active file/text editor
 */
export function getActiveWorkspaceFolder(): vscode.WorkspaceFolder | undefined {
    if (vscode.window.activeTextEditor) {
        return vscode.workspace.getWorkspaceFolder(vscode.window.activeTextEditor.document.uri);
    }
}


/**
 * @returns The workspace configuration for this extension
 */
export function getExtensionConfig() {
    const activeWorkspaceFolder = getActiveWorkspaceFolder()?.uri;
    return vscode.workspace.getConfiguration(EXTENSION_ID, activeWorkspaceFolder);
}


/** Check if we're currently attached to an DCC instance */
export function isDebuggingDCC() {
    return vscode.debug.activeDebugSession?.name === DEBUG_SESSION_NAME;
}


/** Check if a filesystem file/directory exists at the given uri */
export async function uriExists(uri: vscode.Uri): Promise<boolean> {
    try {
        await vscode.workspace.fs.stat(uri);
        return true;
    } catch {
        return false;
    }
}


export async function createDirectoryIfNotExists(directory: vscode.Uri) {
    if (!await uriExists(directory)) {
        try {
            await vscode.workspace.fs.createDirectory(directory);
        } catch {
            return false;
        }
    }

    return true;
}
