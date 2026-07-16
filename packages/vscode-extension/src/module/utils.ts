import * as vscode from 'vscode';
import * as cp from 'child_process';

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


/**
 * Python 命令执行结果
 */
export interface PythonCommandResult {
    code: number;
    stdout: string;
    stderr: string;
}


/**
 * Python 命令执行选项
 */
export interface PythonCommandOptions {
    /** 超时时间（毫秒），0 或 undefined 表示不超时 */
    timeout?: number;
}


/**
 * 解析要使用的 Python 命令路径
 *
 * 优先顺序：
 * 1. 用户设置 dcc-python.pythonPath
 * 2. VS Code Python 扩展的当前解释器
 * 3. 系统默认 python 命令
 */
export async function resolvePythonCommand(): Promise<string> {
    // 1. 检查用户配置
    const pythonPath = getExtensionConfig().get<string>('pythonPath', '');
    if (pythonPath) {
        return pythonPath;
    }

    // 2. 尝试通过 Python 扩展获取当前解释器路径
    try {
        const pyExt = vscode.extensions.getExtension('ms-python.python');
        if (pyExt) {
            const api = pyExt.isActive ? pyExt.exports : await pyExt.activate();
            // Python 扩展 v2023+ API
            if (api?.environments?.getActiveEnvironmentPath) {
                const envPath = api.environments.getActiveEnvironmentPath();
                if (envPath?.path) {
                    return envPath.path;
                }
            }
            // Python 扩展旧版 API
            if (api?.settings?.getExecutionDetails) {
                const execDetails = api.settings.getExecutionDetails();
                if (execDetails?.execCommand?.length > 0) {
                    return execDetails.execCommand[0];
                }
            }
        }
    } catch {
        // Python 扩展不可用或 API 变更
    }

    // 3. 回退到系统默认
    return 'python';
}


/**
 * 执行 Python 命令
 *
 * @param pythonCmd Python 解释器路径或命令
 * @param args 传递给 Python 的参数列表
 * @param options 执行选项
 */
export function runPythonCommand(
    pythonCmd: string,
    args: string[],
    options: PythonCommandOptions = {}
): Promise<PythonCommandResult> {
    return new Promise((resolve, reject) => {
        const proc = cp.spawn(pythonCmd, args, { shell: true });

        let stdout = '';
        let stderr = '';
        let timeoutId: NodeJS.Timeout | undefined;

        if (options.timeout && options.timeout > 0) {
            timeoutId = setTimeout(() => {
                proc.kill();
                reject(new Error(`Command timed out after ${options.timeout}ms`));
            }, options.timeout);
        }

        proc.stdout.on('data', (data: Buffer) => {
            stdout += data.toString();
        });

        proc.stderr.on('data', (data: Buffer) => {
            stderr += data.toString();
        });

        proc.on('error', (err) => {
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
            reject(err);
        });

        proc.on('close', (code: number | null) => {
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
            resolve({ code: code ?? -1, stdout, stderr });
        });
    });
}


/**
 * 通过 Python 模块方式执行 dcc-bridge CLI
 *
 * 优先使用用户配置的 Python 解释器执行 `python -m dcc_bridge <args>`，
 * 兼容安装在虚拟环境中的场景。若用户未配置 pythonPath 且模块执行失败，
 * 则回退到直接调用全局 `dcc` 命令（兼容 uv tool install 等全局安装）。
 */
export async function runDCCBridgeCommand(
    args: string[],
    options: PythonCommandOptions = {}
): Promise<PythonCommandResult> {
    const pythonCmd = await resolvePythonCommand();
    const moduleResult = await runPythonCommand(pythonCmd, ['-m', 'dcc_bridge', ...args], options);
    if (moduleResult.code === 0) {
        return moduleResult;
    }

    // 用户未显式配置 pythonPath 时，回退到全局 dcc 命令
    const pythonPath = getExtensionConfig().get<string>('pythonPath', '');
    if (!pythonPath) {
        const cliResult = await runPythonCommand('dcc', args, options);
        if (cliResult.code === 0) {
            return cliResult;
        }
    }

    return moduleResult;
}
