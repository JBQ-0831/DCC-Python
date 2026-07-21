import * as vscode from 'vscode';

class Logger {
    private static _channel: vscode.LogOutputChannel | null = null;

    private constructor() { }

    public static get channel(): vscode.LogOutputChannel {
        if (!this._channel) {
            this._channel = vscode.window.createOutputChannel("DCC Python ToolKit Log", { log: true });
        }
        return this._channel;
    }

    static python(message: string): void {
        Logger.channel.info(`[Python] ${message.trimEnd()}`);
    }

    static info(message: string): void {
        Logger.channel.info(message);
    }

    static warning(message: string): void {
        Logger.channel.warn(message);
    }

    static error(message: string): void {
        Logger.channel.error(message);
    }

    static showErrorMessage(error: Error | string, userMessage?: string): void {
        const msgStr = typeof error === "string" ? error : error.message;

        Logger.error(msgStr);

        vscode.window.showErrorMessage(userMessage || msgStr, "Show Log").then(selection => {
            if (selection === "Show Log") {
                Logger.channel.show();
            }
        });
    }
}

export default Logger;
