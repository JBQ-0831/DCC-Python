"""
dcc status / ping 子命令实现
"""
from __future__ import annotations

import json

import click

from .. import discovery
from ..client import DCCClientError, resolve_client
from ..dcc_types import normalize_dcc_type


def _target_options(func):
    """为 status/ping 添加目标解析选项（端口/类型/版本/输出格式）"""
    func = click.option("--version", "dcc_version", type=str, default=None, help="Filter by DCC version.\nDCC 版本过滤。")(func)
    func = click.option("--plain", is_flag=True, default=False, help="Output in plain text.\n纯文本输出。")(func)
    func = click.option("--dcc-type", type=str, default=None, help="Filter by DCC type.\nDCC 类型过滤。")(func)
    func = click.option("--port", type=int, default=None, help="Target DCC port.\n目标 DCC 端口。")(func)
    return func


@click.command(name="status")
@_target_options
@click.pass_context
def status(ctx, port, dcc_type, plain, dcc_version) -> None:
    """Show current DCC bridge status.

    显示当前 DCC 桥接状态。
    """
    dcc_type = normalize_dcc_type(dcc_type)
    instances = discovery.list_instances()
    status_data = {
        "instances": instances,
        "count": len(instances),
    }

    # 指定 port / dcc_type / dcc_version 时附加 ping 结果
    if port or dcc_type or dcc_version:
        try:
            client = resolve_client(dcc_type=dcc_type, port=port, version=dcc_version)
            with client:
                status_data["ping"] = client.ping()
        except DCCClientError as e:
            status_data["ping_error"] = str(e)

    if plain:
        click.echo(f"Running DCC instances: {status_data['count']}")
        for info in instances:
            click.echo(
                f"  {info.get('dcc_type', 'unknown')}:{info.get('port', '?')} "
                f"v{info.get('dcc_version', '?')}"
            )
        if "ping" in status_data:
            click.echo(f"Ping: OK - {status_data['ping']}")
        if "ping_error" in status_data:
            click.echo(f"Ping error: {status_data['ping_error']}", err=True)
    else:
        click.echo(json.dumps(status_data, ensure_ascii=False, indent=2))


@click.command(name="ping")
@_target_options
@click.pass_context
def ping(ctx, port, dcc_type, plain, dcc_version) -> None:
    """Ping the DCC bridge server.

    Ping DCC 服务。
    """
    dcc_type = normalize_dcc_type(dcc_type)
    try:
        client = resolve_client(dcc_type=dcc_type, port=port, version=dcc_version)
    except DCCClientError as e:
        if plain:
            click.echo(f"Failed to reach DCC bridge server: {e}", err=True)
        else:
            click.echo(
                json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2),
                err=True,
            )
        ctx.exit(1)

    with client:
        try:
            result = client.ping()
            result["success"] = True
            if plain:
                click.echo("DCC bridge server is reachable.")
                click.echo(f"DCC type: {result.get('dcc_type', 'unknown')}")
                click.echo(f"Python path: {result.get('python_path', 'unknown')}")
            else:
                click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        except DCCClientError as e:
            if plain:
                click.echo(f"Failed to reach DCC bridge server: {e}", err=True)
            else:
                click.echo(
                    json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2),
                    err=True,
                )
            ctx.exit(1)