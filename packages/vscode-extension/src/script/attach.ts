import * as vscode from 'vscode';

import * as utils from '../module/utils';
import { DCCManager } from '../module/dcc/dcc-manager';
import { promptStartServer } from './execute';

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

    // 确保 DCC 服务端已连接，未连接则提示用户先启动服务端
    if (!driver.isConnected()) {
        const connected = await dccManager.connect();
        if (!connected) {
            await promptStartServer();
            return;
        }
    }

    const config = utils.getExtensionConfig();

    const userDebugConfig = config.get<IUserDebugConfiguration>('debug');
    if (!userDebugConfig) {
        Logger.showErrorMessage("Failed to get 'dcc-python-toolkit.debug' configuration.");
        return;
    }

    const { port, ...debugConfig } = userDebugConfig;

    // 检测目标 DCC 的 Python 版本：低于 3.0 不支持 debugpy（如 Python 2.7）
    const pingResult = await driver.ping();
    if (pingResult && pingResult.pythonVersion) {
        const majorVersion = parseInt(pingResult.pythonVersion.split('.')[0], 10);
        if (!isNaN(majorVersion) && majorVersion < 3) {
            vscode.window.showErrorMessage(
                `目标 DCC（${driver.dccName}）运行在 Python ${pingResult.pythonVersion}，版本低于 3.0，暂不支持使用 debugpy 进行调试。`
            );
            return;
        }
    }

    const started = await driver.startDebugServer(port);
    if (!started) {
        // debugpy 未安装时会提示用户运行 dcc setup
        return;
    }

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