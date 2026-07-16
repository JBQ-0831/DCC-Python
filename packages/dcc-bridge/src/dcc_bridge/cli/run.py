"""
dcc run 子命令实现
"""
from __future__ import annotations

import os
import sys

import click

from ..client import DCCClient, DCCClientError, resolve_client
from ..dcc_types import normalize_dcc_type
from .utils import get_exit_code, parse_response, print_client_error, print_result


def _do_reload(client: DCCClient, workspace_folders: list) -> dict:
    """发送重载模块请求"""
    response = client.reload_modules(workspace_folders)
    return parse_response(response)


def _run_common_options(func):
    """为 run 子命令添加公共选项（端口/类型/版本/重载/输出等）"""
    func = click.option("--timeout", type=float, default=30.0, help="Connection timeout in seconds.\n连接超时秒数。")(func)
    func = click.option("--json", "as_json", is_flag=True, default=False, help="Output in JSON format.\nJSON 格式输出。")(func)
    func = click.option("--plain", is_flag=True, default=False, help="Output in plain text.\n纯文本输出。")(func)
    func = click.option("--origin", type=str, default=None, help="Execution origin identifier.\n执行来源标识。")(func)
    func = click.option("-r", "--reload", "reload", is_flag=True, default=False, help="Reload modules before execution.\n执行前重载模块。")(func)
    func = click.option("--dcc-type", type=str, default=None, help="DCC type (maya/3dsmax/substance_painter/substance_designer).\nDCC 类型 (maya/3dsmax/substance_painter/substance_designer)。")(func)
    func = click.option("--version", "dcc_version", type=str, default=None, help="Filter by DCC version (e.g. 2022/2024).\nDCC 版本过滤（如 2022/2024）。")(func)
    func = click.option("--port", type=int, default=None, help="Target DCC port.\n目标 DCC 端口。")(func)
    return func


def _execute_code_in_client(ctx, client, code, origin, plain, reload, reload_dir):
    """在已建立的 client 连接中执行代码，统一处理 reload 与输出"""
    with client:
        if reload:
            reload_result = _do_reload(client, [reload_dir])
            if not reload_result["success"]:
                print_result(reload_result, plain)
                ctx.exit(get_exit_code(reload_result))

        response = client.execute_code(code, exec_origin=origin)
        result = parse_response(response)
        print_result(result, plain)
        ctx.exit(get_exit_code(result))


@click.group(name="run")
def run_group() -> None:
    """Execute Python code or files in DCC.

    在 DCC 中执行 Python 代码或文件。
    """


@run_group.command(name="file")
@click.argument("target")
@_run_common_options
@click.pass_context
def run_file(ctx, target, port, dcc_type, reload, origin, plain, as_json, timeout, dcc_version) -> None:
    """Execute a local Python file.

    执行本地 Python 文件。
    """
    dcc_type = normalize_dcc_type(dcc_type)
    file_path = os.path.abspath(target)

    if not os.path.exists(file_path):
        result = {
            "success": False,
            "output": [],
            "error": f"File not found: {file_path}",
            "traceback": None,
        }
        print_result(result, plain)
        ctx.exit(3)

    try:
        client = resolve_client(dcc_type=dcc_type, port=port, version=dcc_version, timeout=timeout)
    except DCCClientError as e:
        ctx.exit(print_client_error(e, plain))

    with client:
        if reload:
            file_dir = os.path.dirname(file_path)
            reload_result = _do_reload(client, [file_dir])
            if not reload_result["success"]:
                print_result(reload_result, plain)
                ctx.exit(get_exit_code(reload_result))

        response = client.execute_file(file_path, exec_origin=file_path)
        result = parse_response(response)
        print_result(result, plain)
        ctx.exit(get_exit_code(result))


@run_group.command(name="code")
@click.argument("target")
@_run_common_options
@click.pass_context
def run_code(ctx, target, port, dcc_type, reload, origin, plain, as_json, timeout, dcc_version) -> None:
    """Execute a Python code string.

    执行代码字符串。
    """
    dcc_type = normalize_dcc_type(dcc_type)
    try:
        client = resolve_client(dcc_type=dcc_type, port=port, version=dcc_version, timeout=timeout)
    except DCCClientError as e:
        ctx.exit(print_client_error(e, plain))

    _execute_code_in_client(ctx, client, target, origin or "<dcc-run>", plain, reload, os.getcwd())


@run_group.command(name="stdin")
@_run_common_options
@click.pass_context
def run_stdin(ctx, port, dcc_type, reload, origin, plain, as_json, timeout, dcc_version) -> None:
    """Read code from stdin and execute.

    从标准输入读取代码并执行。
    """
    dcc_type = normalize_dcc_type(dcc_type)
    source = sys.stdin.read()
    try:
        client = resolve_client(dcc_type=dcc_type, port=port, version=dcc_version, timeout=timeout)
    except DCCClientError as e:
        ctx.exit(print_client_error(e, plain))

    _execute_code_in_client(ctx, client, source, origin or "<dcc-run-stdin>", plain, reload, os.getcwd())