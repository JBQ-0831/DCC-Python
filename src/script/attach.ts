import * as vscode from 'vscode';

import * as utils from '../module/utils';
import { DCCManager } from '../module/dcc/dcc-manager';
import { promptStartServer, getOutputChannel } from './execute';

import Logger from '../module/logging';


interface IUserDebugConfiguration {
    port: number;
    justMyCode: boolean;
};


export async function attach() {
    const dccManager = DCCManager.getInstance();
    const driver = dccManager.getCurrentDriver();

    if (!driver) {
        Logger.error("No DCC driver selected.");
        vscode.window.showErrorMessage("No DCC driver selected.");
        return;
    }

    // 先确保 DCC 服务端已连接，未连接则提示用户先启动服务端
    if (!driver.isConnected()) {
        const connected = await dccManager.connect();
        if (!connected) {
            await promptStartServer();
            return;
        }
    }

    let isDebugpyInstalled: boolean = true;
    const importResult = await driver.importDebugpy();
    if (importResult === undefined) {
        return;
    }
    isDebugpyInstalled = importResult;

    if (!isDebugpyInstalled) {
        const selection = await vscode.window.showErrorMessage(
            "Python package debugpy is required to attach the debugger.",
            "Install debugpy"
        );

        if (selection !== "Install debugpy") {
            return;
        }

        const config = utils.getExtensionConfig();
        const pipIndexUrl = config.get<string>('debug.pipIndexUrl', '');
        
        const installationSuccess = await driver.installDebugpy(pipIndexUrl);
        if (!installationSuccess) {
            return;
        }
    }

    const config = utils.getExtensionConfig();

    const userDebugConfig = config.get<IUserDebugConfiguration>('debug');
    if (!userDebugConfig) {
        Logger.showErrorMessage("Failed to get 'dcc-python.debug' configuration.");
        return;
    }

    const { port, ...debugConfig } = userDebugConfig;

    if (await driver.startDebugServer(port)) {
        const host = driver.getHost();

        const configuration: vscode.DebugConfiguration = {
            "name": utils.DEBUG_SESSION_NAME,
            "request": "attach",
            "type": "debugpy",
            "connect": {
                "host": host,
                "port": port
            },
            ...debugConfig
        };

        await vscode.debug.startDebugging(undefined, configuration);
    }
}