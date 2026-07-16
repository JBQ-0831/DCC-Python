"""
dcc setup / unsetup 子命令实现

注意：底层注入逻辑在 dcc_bridge.setup 子包中实现，
本文件仅做命令行封装。
"""
from __future__ import annotations

import click

from ..dcc_types import normalize_dcc_type
from ..setup.base import get_setup


def _run_setup_action(ctx, dcc_type, dcc_version, action):
    """统一处理 setup / unsetup 的执行与错误输出

    action: "setup" 或 "unsetup"
    """
    # 将别名规范化为标准名称（max -> 3dsmax, sp -> substance_painter）
    dcc_type = normalize_dcc_type(dcc_type)
    setup_instance = get_setup(dcc_type)

    if setup_instance is None:
        click.echo(f"Unsupported DCC type for {action}: {dcc_type}", err=True)
        click.echo("Currently supported: maya, 3dsmax", err=True)
        ctx.exit(2)

    method = setup_instance.setup if action == "setup" else setup_instance.unsetup
    try:
        success = method(version=dcc_version)
        if success:
            click.echo(f"{action.capitalize()} succeeded for {dcc_type}")
            return
        click.echo(f"{action.capitalize()} failed for {dcc_type}", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(f"{action.capitalize()} error: {e}", err=True)
        ctx.exit(1)


@click.command(name="setup")
@click.argument("dcc_type")
@click.option("--version", "dcc_version", default=None, help="Specify DCC version (processes all supported versions if omitted).\n指定 DCC 版本（不指定则处理所有支持的版本）。")
@click.pass_context
def setup(ctx, dcc_type, dcc_version) -> None:
    """Inject DCC auto-startup scripts.

    注入 DCC 自启动脚本。
    """
    _run_setup_action(ctx, dcc_type, dcc_version, "setup")


@click.command(name="unsetup")
@click.argument("dcc_type")
@click.option("--version", "dcc_version", default=None, help="Specify DCC version.\n指定 DCC 版本。")
@click.pass_context
def unsetup(ctx, dcc_type, dcc_version) -> None:
    """Remove DCC auto-startup scripts.

    移除 DCC 自启动脚本。
    """
    _run_setup_action(ctx, dcc_type, dcc_version, "unsetup")
