"""
dcc setup / unsetup 子命令实现

注意：底层注入逻辑在 dcc_bridge.setup 子包中实现，
本文件仅做命令行封装。
"""
from __future__ import annotations

import click

from ..dcc_names import normalize_dcc_name
from ..setup.base import get_setup


def _run_setup_action(ctx, dcc_name, dcc_version, action, pip_index_url=""):
    """统一处理 setup / unsetup 的执行与错误输出

    action: "setup" 或 "unsetup"
    """
    # 将别名规范化为标准名称（max -> 3dsmax, sp -> substance_painter）
    dcc_name = normalize_dcc_name(dcc_name)
    setup_instance = get_setup(dcc_name)

    if setup_instance is None:
        click.echo(f"Unsupported DCC type for {action}: {dcc_name}", err=True)
        click.echo(
            "Currently supported: maya, 3dsmax, substance_painter, substance_designer, houdini",
            err=True,
        )
        ctx.exit(2)

    try:
        if action == "setup":
            success = setup_instance.setup(version=dcc_version, pip_index_url=pip_index_url)
        else:
            success = setup_instance.unsetup(version=dcc_version)
        if success:
            click.echo(f"{action.capitalize()} succeeded for {dcc_name}")
            return
        click.echo(f"{action.capitalize()} failed for {dcc_name}", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(f"{action.capitalize()} error: {e}", err=True)
        ctx.exit(1)


@click.command(name="setup")
@click.argument("dcc_name", required=False, default=None)
@click.option("--version", "dcc_version", default=None, help="Specify DCC version (processes all supported versions if omitted).\n指定 DCC 版本（不指定则处理所有支持的版本）。")
@click.option("--pip-index-url", default="", help="pip 镜像源 URL，用于加速 debugpy 安装（如 https://pypi.tuna.tsinghua.edu.cn/simple）。")
@click.pass_context
def setup(ctx, dcc_name, dcc_version, pip_index_url) -> None:
    """Inject DCC auto-startup scripts and install debugpy.

    注入 DCC 自启动脚本并安装 debugpy 调试模块。
    不指定 dcc_name 时，自动为所有已支持的 DCC 执行注入。
    """
    if dcc_name is None:
        # 不指定 DCC 类型时，遍历所有已支持的 DCC
        all_types = ["maya", "3dsmax", "substance_painter", "substance_designer", "houdini", "blender"]
        for dt in all_types:
            click.echo(f"\n--- Setting up {dt} ---")
            try:
                _run_setup_action(ctx, dt, dcc_version, "setup", pip_index_url)
            except SystemExit:
                # _run_setup_action 失败时调用 ctx.exit()，继续处理下一个 DCC
                pass
        return
    _run_setup_action(ctx, dcc_name, dcc_version, "setup", pip_index_url)


@click.command(name="unsetup")
@click.argument("dcc_name")
@click.option("--version", "dcc_version", default=None, help="Specify DCC version.\n指定 DCC 版本。")
@click.pass_context
def unsetup(ctx, dcc_name, dcc_version) -> None:
    """Remove DCC auto-startup scripts.

    移除 DCC 自启动脚本。
    """
    _run_setup_action(ctx, dcc_name, dcc_version, "unsetup")
