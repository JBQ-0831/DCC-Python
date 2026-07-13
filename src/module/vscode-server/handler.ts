/**
 * VS Code 内部 socket 服务端请求处理器
 *
 * 支持：
 * - execute_file：接收外部传入的文件路径，调用 DCC driver 执行
 * - execute_code：接收外部传入的代码字符串，写入临时文件后调用 DCC driver 执行
 * - reload_modules：重载工作区模块
 */

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

import Logger from '../logging';
import * as utils from '../utils';
import { DCCManager } from '../dcc/dcc-manager';

import type { Request, Response } from './protocol';


export async function handleRequest(request: Request): Promise<Response> {
    if (request.method === 'execute_file') {
        return handleExecuteFile(request);
    }

    if (request.method === 'execute_code') {
        return handleExecuteCode(request);
    }

    if (request.method === 'reload_modules') {
        return handleReloadModules(request);
    }

    return buildErrorResponse(request.id, `Unknown method: ${request.method}`);
}


async function handleReloadModules(request: Request): Promise<Response> {
    const dccManager = DCCManager.getInstance();
    const driver = dccManager.getCurrentDriver();
    if (!driver) {
        return buildErrorResponse(request.id, 'No DCC driver available. Please start the DCC server first.');
    }

    const workspaceFolders: string[] = request.params.workspace_folders || [];

    Logger.info(`[VSCodeServer] reload_modules: ${workspaceFolders.join(', ')}`);

    const response = await driver.reloadModules(workspaceFolders);

    if (response === null) {
        return buildErrorResponse(request.id, 'Failed to reload modules: DCC server is not connected.');
    }

    if (response.output.length > 0) {
        for (const line of response.output) {
            if (line !== '\n') {
                Logger.info(line);
            }
        }
    }

    return {
        id: request.id,
        result: {
            success: response.success,
            output: response.output
        }
    };
}


async function handleExecuteFile(request: Request): Promise<Response> {
    const filePath = request.params.file_path;
    if (!filePath || typeof filePath !== 'string') {
        return buildErrorResponse(request.id, 'Missing or invalid parameter: file_path');
    }

    if (!fs.existsSync(filePath)) {
        return buildErrorResponse(request.id, `File not found: ${filePath}`);
    }

    return executeFile(filePath, filePath, request.id);
}


async function handleExecuteCode(request: Request): Promise<Response> {
    const source = request.params.source;
    if (!source || typeof source !== 'string') {
        return buildErrorResponse(request.id, 'Missing or invalid parameter: source');
    }

    const execOrigin = request.params.exec_origin || '<vscode-server>';

    // 将代码写入临时文件，复用 executeFile 流程
    const tempDir = os.tmpdir();
    const tempFile = path.join(tempDir, `vscode_dcc_exec_${Date.now()}.py`);
    fs.writeFileSync(tempFile, source);

    try {
        return await executeFile(tempFile, execOrigin, request.id);
    } finally {
        try {
            fs.unlinkSync(tempFile);
        } catch {
            // 忽略清理临时文件失败
        }
    }
}


async function executeFile(filePath: string, execOrigin: string, requestId: string): Promise<Response> {
    const dccManager = DCCManager.getInstance();
    const driver = dccManager.getCurrentDriver();
    if (!driver) {
        return buildErrorResponse(requestId, 'No DCC driver available. Please start the DCC server first.');
    }

    const config = utils.getExtensionConfig();
    const nameVar = config.get<string>('execute.name', '__main__');

    Logger.info(`[VSCodeServer] execute: ${filePath}`);

    const response = await driver.executeFile(filePath, execOrigin, nameVar, false);

    if (response === null) {
        return buildErrorResponse(requestId, 'Failed to execute: DCC server is not connected.');
    }

    // 同步输出到 DCC Python Log 频道
    if (response.output.length > 0) {
        for (const line of response.output) {
            if (line !== '\n') {
                Logger.info(line);
            }
        }
    }

    if (!response.success) {
        const errorMsg = response.error || 'Execution failed';
        Logger.error(errorMsg);
        return buildErrorResponse(requestId, errorMsg, response.traceback);
    }

    return {
        id: requestId,
        result: {
            success: true,
            output: response.output
        }
    };
}


function buildErrorResponse(id: string, message: string, traceback?: string): Response {
    return {
        id,
        error: {
            message,
            traceback
        }
    };
}
