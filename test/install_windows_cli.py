#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Windows 下安装 dcc-run 命令到用户 PATH

用法：
    uv run python test/install_windows_cli.py

安装后会：
1. 在 %USERPROFILE%\\.dcc-python-cli 创建 dcc-run.cmd
2. 将该目录追加到用户 PATH（如果不在的话）
3. 之后即可在任意目录运行 dcc-run
"""
import os
import subprocess
import sys


CLI_DIR_NAME = ".dcc-python-cli"
CMD_NAME = "dcc-run.cmd"


def get_cli_dir():
    """返回放置 wrapper 脚本的目录"""
    return os.path.join(os.environ["USERPROFILE"], CLI_DIR_NAME)


def get_dcc_run_py_path():
    """返回 dcc_run.py 的绝对路径，假设 install 脚本位于 test/ 目录"""
    install_dir = os.path.dirname(os.path.abspath(__file__))
    dcc_run_path = os.path.abspath(os.path.join(install_dir, "dcc_run.py"))
    if not os.path.exists(dcc_run_path):
        print("ERROR: dcc_run.py not found at: {}".format(dcc_run_path))
        sys.exit(1)
    return dcc_run_path


def ensure_cli_dir(cli_dir):
    """确保 CLI 目录存在"""
    if not os.path.exists(cli_dir):
        os.makedirs(cli_dir)
        print("Created directory: {}".format(cli_dir))


def write_cmd_wrapper(cli_dir, dcc_run_path):
    """创建 dcc-run.cmd 包装器"""
    cmd_path = os.path.join(cli_dir, CMD_NAME)

    # 使用 python 启动 dcc_run.py，支持任意目录调用
    content = '''@echo off
python "{dcc_run_py}" %*
'''.format(dcc_run_py=dcc_run_path)

    with open(cmd_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Created wrapper: {}".format(cmd_path))


def get_user_path():
    """读取当前用户环境变量 PATH"""
    result = subprocess.run(
        ["reg", "query", "HKCU\\Environment", "/v", "Path"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return ""

    # reg query 输出类似：
    # HKEY_CURRENT_USER\Environment
    #     Path    REG_EXPAND_SZ    C:\Users\xxx\bin;...
    lines = result.stdout.strip().splitlines()
    for line in lines:
        if line.strip().startswith("Path"):
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                return parts[2]
    return ""


def add_to_path(cli_dir):
    """把 cli_dir 追加到用户 PATH，如果不在的话"""
    current_path = get_user_path()
    paths = [p.strip() for p in current_path.split(";") if p.strip()]

    if cli_dir in paths:
        print("Already in PATH: {}".format(cli_dir))
        return

    new_path = current_path
    if new_path and not new_path.endswith(";"):
        new_path += ";"
    new_path += cli_dir

    result = subprocess.run(
        ["setx", "Path", new_path],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("Added to PATH: {}".format(cli_dir))
        print("Please restart your terminal for PATH changes to take effect.")
    else:
        print("ERROR: Failed to update PATH")
        print(result.stderr)
        sys.exit(1)


def main():
    cli_dir = get_cli_dir()
    dcc_run_path = get_dcc_run_py_path()

    ensure_cli_dir(cli_dir)
    write_cmd_wrapper(cli_dir, dcc_run_path)
    add_to_path(cli_dir)

    print("\nInstallation complete.")
    print("After restarting your terminal, run: dcc-run --help")


if __name__ == "__main__":
    main()
