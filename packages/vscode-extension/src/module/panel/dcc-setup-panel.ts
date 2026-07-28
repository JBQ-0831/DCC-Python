import * as vscode from 'vscode';
import { runDCCBridgeCommand } from '../utils';


interface DCCEntry {
    /** dcc-bridge CLI 的 dccType */
    cliId: string;
    /** 显示名称 */
    displayName: string;
    /** 图标相对路径 */
    iconPath: string;
    /** 现有命令 ID 的后缀，如 setupMaya → 后缀 Maya */
    commandSuffix: string;
}

const DCC_LIST: DCCEntry[] = [
    { cliId: 'maya',              displayName: 'Maya',                iconPath: 'icons/maya.svg',               commandSuffix: 'Maya' },
    { cliId: '3dsmax',            displayName: '3ds Max',             iconPath: 'icons/3ds-max.svg',            commandSuffix: 'Max' },
    { cliId: 'substance_painter', displayName: 'Substance Painter',   iconPath: 'icons/substance-painter.svg',  commandSuffix: 'SP' },
    { cliId: 'substance_designer',displayName: 'Substance Designer',  iconPath: 'icons/substance-designer.svg', commandSuffix: 'SD' },
    { cliId: 'houdini',           displayName: 'Houdini',             iconPath: 'icons/houdini.svg',            commandSuffix: 'Houdini' },
    { cliId: 'blender',           displayName: 'Blender',             iconPath: 'icons/blender.svg',            commandSuffix: 'Blender' },
];


export function registerDCCSetupPanel(context: vscode.ExtensionContext) {
    context.subscriptions.push(
        vscode.commands.registerCommand('dcc-python-toolkit.openDCCSetup', () => {
            DCCSetupPanel.createOrShow(context.extensionUri);
        })
    );
}


class DCCSetupPanel {
    private static currentPanel: DCCSetupPanel | undefined;
    private readonly panel: vscode.WebviewPanel;
    private readonly extensionUri: vscode.Uri;
    private disposables: vscode.Disposable[] = [];

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this.panel = panel;
        this.extensionUri = extensionUri;

        this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
        this.panel.webview.onDidReceiveMessage(
            (msg) => this.handleMessage(msg),
            null,
            this.disposables
        );

        this.render();
        this.refreshStatus();
    }

    public static createOrShow(extensionUri: vscode.Uri) {
        if (DCCSetupPanel.currentPanel) {
            DCCSetupPanel.currentPanel.panel.reveal();
            DCCSetupPanel.currentPanel.refreshStatus();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'dccSetupPanel',
            'DCC Setup',
            vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            }
        );

        DCCSetupPanel.currentPanel = new DCCSetupPanel(panel, extensionUri);
    }

    private dispose() {
        DCCSetupPanel.currentPanel = undefined;
        this.panel.dispose();
        for (const d of this.disposables) {
            d.dispose();
        }
    }

    // ─── 消息处理 ────────────────────────────

    private async handleMessage(msg: { command: string; dcc?: string }) {
        switch (msg.command) {
            case 'setup':
                await this.runCommand(msg.dcc!, 'setup');
                break;
            case 'unsetup':
                await this.runCommand(msg.dcc!, 'unsetup');
                break;
            case 'setupAll':
                await this.runAll('setup');
                break;
            case 'unsetupAll':
                await this.runAll('unsetup');
                break;
            case 'refresh':
                await this.refreshStatus();
                break;
        }
    }

    private async runCommand(cliId: string, action: 'setup' | 'unsetup') {
        const entry = DCC_LIST.find(d => d.cliId === cliId);
        if (!entry) { return; }

        const cmdId = `dcc-python-toolkit.dashboard.${action}${entry.commandSuffix}`;
        this.postMessage({ command: 'setLoading', dcc: cliId, loading: true });
        await vscode.commands.executeCommand(cmdId);
        this.postMessage({ command: 'setLoading', dcc: cliId, loading: false });
        await this.refreshStatus();
    }

    private async runAll(action: 'setup' | 'unsetup') {
        this.postMessage({ command: 'setAllLoading', loading: true });
        for (const entry of DCC_LIST) {
            const cmdId = `dcc-python-toolkit.dashboard.${action}${entry.commandSuffix}`;
            await vscode.commands.executeCommand(cmdId);
        }
        this.postMessage({ command: 'setAllLoading', loading: false });
        await this.refreshStatus();
    }

    // ─── 状态查询 ────────────────────────────

    private async refreshStatus() {
        const statuses: Record<string, { running: boolean; dccName: string }> = {};

        // 通过 dcc status 获取运行中的 DCC 实例
        try {
            const result = await runDCCBridgeCommand(['status'], { timeout: 5000 });
            if (result.code === 0 && result.stdout.trim()) {
                const parsed = JSON.parse(result.stdout);
                const instances: { dcc_name: string }[] =
                    parsed && typeof parsed === 'object' && 'instances' in parsed
                        ? parsed.instances : Array.isArray(parsed) ? parsed : [];

                const runningSet = new Set(
                    instances.map((inst: { dcc_name: string }) =>
                        inst.dcc_name?.toLowerCase()
                    )
                );

                for (const entry of DCC_LIST) {
                    statuses[entry.cliId] = {
                        running: runningSet.has(entry.cliId.toLowerCase()),
                        dccName: entry.displayName,
                    };
                }
            }
        } catch {
            // status 查询失败时全部显示未知
        }

        // 补齐未查到的 DCC
        for (const entry of DCC_LIST) {
            if (!statuses[entry.cliId]) {
                statuses[entry.cliId] = { running: false, dccName: entry.displayName };
            }
        }

        this.postMessage({ command: 'updateStatus', statuses });
    }

    // ─── WebView 通信 ────────────────────────

    private postMessage(msg: object) {
        this.panel.webview.postMessage(msg);
    }

    // ─── 渲染 ────────────────────────────────

    private render() {
        this.panel.webview.html = this.buildHtml();
    }

    private buildHtml(): string {
        // 将图标文件路径转换为 webview URI
        const iconUris: Record<string, string> = {};
        for (const entry of DCC_LIST) {
            const svgPath = vscode.Uri.joinPath(this.extensionUri, entry.iconPath);
            iconUris[entry.cliId] = this.panel.webview.asWebviewUri(svgPath).toString();
        }

        const rows = DCC_LIST.map(entry => {
            const iconSrc = iconUris[entry.cliId];
            return /* html */ `
            <div class="dcc-row" id="row-${entry.cliId}">
                <img class="dcc-icon" src="${iconSrc}" alt="${entry.displayName}" />
                <span class="dcc-name">${entry.displayName}</span>
                <span class="dcc-status" id="status-${entry.cliId}">
                    <span class="spinner"></span> 检测中...
                </span>
                <div class="dcc-actions">
                    <button class="btn btn-setup" id="btn-setup-${entry.cliId}"
                            onclick="send('setup','${entry.cliId}')">Setup</button>
                    <button class="btn btn-unsetup" id="btn-unsetup-${entry.cliId}"
                            onclick="send('unsetup','${entry.cliId}')">Unsetup</button>
                </div>
            </div>`;
        }).join('\n');

        return /* html */ `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        padding: 16px;
        font-family: var(--vscode-font-family, -apple-system, sans-serif);
        font-size: var(--vscode-font-size, 13px);
        color: var(--vscode-foreground);
        background: var(--vscode-editor-background);
    }
    .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
    }
    h1 { font-size: 15px; font-weight: 600; }
    .dcc-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-bottom: 16px;
    }
    .dcc-row {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 12px;
        border: 1px solid var(--vscode-panel-border, #3c3c3c);
        border-radius: 6px;
        background: var(--vscode-sideBar-background, #252526);
        transition: background 0.15s;
    }
    .dcc-row:hover {
        background: var(--vscode-list-hoverBackground, #2a2d2e);
    }
    .dcc-icon {
        width: 22px;
        height: 22px;
        flex-shrink: 0;
        opacity: 0.85;
    }
    .dcc-name {
        font-weight: 500;
        width: 140px;
        flex-shrink: 0;
        font-size: 13px;
    }
    .dcc-status {
        width: 120px;
        flex-shrink: 0;
        font-size: 12px;
        display: flex;
        align-items: center;
        gap: 5px;
        white-space: nowrap;
    }
    .status-running { color: var(--vscode-testing-iconPassed, #73c991); }
    .status-stopped { color: var(--vscode-descriptionForeground, #999); }
    .dcc-actions {
        display: flex;
        gap: 6px;
        flex-shrink: 0;
    }
    .btn {
        padding: 3px 12px;
        border: 1px solid transparent;
        border-radius: 3px;
        cursor: pointer;
        font-family: inherit;
        font-size: 12px;
        line-height: 20px;
        transition: background 0.15s, opacity 0.15s;
    }
    .btn:disabled { opacity: 0.4; cursor: default; }
    .btn-setup {
        color: var(--vscode-button-foreground, #fff);
        background: var(--vscode-button-background, #0078d4);
        border-color: var(--vscode-button-border, transparent);
    }
    .btn-setup:hover:not(:disabled) {
        background: var(--vscode-button-hoverBackground, #026ec1);
    }
    .btn-unsetup {
        color: var(--vscode-button-secondaryForeground, #ccc);
        background: var(--vscode-button-secondaryBackground, #3a3d41);
        border-color: var(--vscode-button-secondaryBorder, #555);
    }
    .btn-unsetup:hover:not(:disabled) {
        background: var(--vscode-button-secondaryHoverBackground, #45494e);
    }
    .toolbar {
        display: flex;
        gap: 8px;
        padding-top: 12px;
        border-top: 1px solid var(--vscode-panel-border, #3c3c3c);
    }
    .btn-tool {
        padding: 5px 14px;
    }
    .spinner {
        display: inline-block;
        width: 12px;
        height: 12px;
        border: 2px solid var(--vscode-descriptionForeground, #999);
        border-top-color: transparent;
        border-radius: 50%;
        animation: spin 0.7s linear infinite;
        vertical-align: middle;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
    <div class="header">
        <h1>DCC Bridge 工具管理</h1>
    </div>
    <div class="dcc-list">${rows}</div>
    <div class="toolbar">
        <button class="btn btn-setup btn-tool" id="btn-all-setup"
                onclick="send('setupAll')">全部 Setup</button>
        <button class="btn btn-unsetup btn-tool" id="btn-all-unsetup"
                onclick="send('unsetupAll')">全部 Unsetup</button>
        <button class="btn btn-unsetup btn-tool" id="btn-refresh"
                onclick="send('refresh')">刷新状态</button>
    </div>
<script>
    const vscode = acquireVsCodeApi();

    function send(cmd, dcc) {
        vscode.postMessage({ command: cmd, dcc: dcc || undefined });
    }

    window.addEventListener('message', function(e) {
        const m = e.data;
        switch (m.command) {
            case 'updateStatus':
                for (const [id, s] of Object.entries(m.statuses)) {
                    const el = document.getElementById('status-' + id);
                    if (!el) continue;
                    if (s.running) {
                        el.className = 'dcc-status status-running';
                        el.textContent = '● 运行中';
                    } else {
                        el.className = 'dcc-status status-stopped';
                        el.textContent = '○ 未检测到运行';
                    }
                }
                break;
            case 'setLoading':
                setBtnLoading('btn-setup-' + m.dcc, m.loading);
                setBtnLoading('btn-unsetup-' + m.dcc, m.loading);
                break;
            case 'setAllLoading':
                document.querySelectorAll('.btn').forEach(function(b) {
                    b.disabled = m.loading;
                });
                break;
        }
    });

    function setBtnLoading(id, loading) {
        var b = document.getElementById(id);
        if (b) b.disabled = loading;
    }
</script>
</body>
</html>`;
    }
}
