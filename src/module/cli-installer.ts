/**
 * Windows 下自动安装 dcc-run CLI 到用户 PATH
 *
 * 插件激活时调用，若检测到 dcc-run 不在 PATH 中，则运行 cli/install_windows_cli.py
 * 进行安装。同时提供手动安装命令供用户触发。
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { spawn, exec } from 'child_process';
import { promisify } from 'util';

import Logger from './logging';


const execAsync = promisify(exec);
const CLI_DIR_NAME = '.dcc-python-cli';


function getCliDir(): string {
	return path.join(process.env.USERPROFILE || '', CLI_DIR_NAME);
}


export async function isCliInstalled(): Promise<boolean> {
	try {
		await execAsync('where dcc-run');
		return true;
	} catch {
		return false;
	}
}


export async function installCli(extensionPath: string): Promise<void> {
	const installScript = path.join(extensionPath, 'cli', 'install_windows_cli.py');
	const dccRunPy = path.join(extensionPath, 'cli', 'dcc_run.py');

	if (!await fileExists(installScript)) {
		throw new Error(`CLI install script not found: ${installScript}`);
	}
	if (!await fileExists(dccRunPy)) {
		throw new Error(`CLI dcc_run.py not found: ${dccRunPy}`);
	}

	Logger.info(`[CLI Installer] Installing dcc-run CLI...`);

	return new Promise((resolve, reject) => {
		const proc = spawn('python', [
			installScript,
			'--dcc-run-py',
			dccRunPy
		], {
			shell: false
		});

		let stdout = '';
		let stderr = '';

		proc.stdout.on('data', (data) => {
			stdout += data.toString();
			Logger.info(data.toString().trimEnd());
		});

		proc.stderr.on('data', (data) => {
			stderr += data.toString();
			Logger.error(data.toString().trimEnd());
		});

		proc.on('close', (code) => {
			if (code === 0) {
				Logger.info('[CLI Installer] dcc-run CLI installed successfully');
				resolve();
			} else {
				reject(new Error(`CLI install failed with code ${code}.\n${stderr}`));
			}
		});

		proc.on('error', (err) => {
			reject(err);
		});
	});
}


export async function ensureCliInstalled(extensionPath: string, showRestartHint: boolean = true): Promise<void> {
	if (await isCliInstalled()) {
		Logger.info('[CLI Installer] dcc-run is already available in PATH');
		return;
	}

	Logger.info('[CLI Installer] dcc-run not found in PATH, installing...');

	try {
		await installCli(extensionPath);
		if (showRestartHint) {
			vscode.window.showInformationMessage(
				'dcc-run CLI installed. Please restart your terminal to use it globally.',
				'OK'
			);
		}
	} catch (err) {
		const message = err instanceof Error ? err.message : String(err);
		Logger.error(`[CLI Installer] Failed to install dcc-run: ${message}`);
		vscode.window.showErrorMessage(
			`Failed to install dcc-run CLI: ${message}`
		);
		throw err;
	}
}


async function fileExists(filePath: string): Promise<boolean> {
	try {
		await vscode.workspace.fs.stat(vscode.Uri.file(filePath));
		return true;
	} catch {
		return false;
	}
}
