"""
dcc cleanup 子命令实现

卸载前清理：
1. 删除 ~/.dcc-bridge 用户数据目录（包含所有发现文件）
2. 对所有已实现的 DCCSetup 子类执行 unsetup，移除自启动脚本
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import shutil
from typing import List, Type

import click

from ..discovery import get_user_data_dir
from ..setup.base import DCCSetup


def _discover_setup_classes() -> List[Type[DCCSetup]]:
    """动态发现 dcc_bridge.setup 包下所有非抽象的 DCCSetup 子类"""
    from .. import setup as setup_pkg

    setup_classes: List[Type[DCCSetup]] = []
    package_name = setup_pkg.__name__
    package_path = setup_pkg.__path__  # type: ignore[attr-defined]

    # 遍历 setup 包下的所有模块
    for finder, module_name, is_pkg in pkgutil.iter_modules(
        package_path, prefix=f"{package_name}."
    ):
        if module_name.endswith(".base") or is_pkg:
            continue
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, DCCSetup)
                and obj is not DCCSetup
                and getattr(obj, "dcc_type", "")
            ):
                setup_classes.append(obj)

    return setup_classes


@click.command(name="cleanup")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.\n跳过确认提示。")
@click.pass_context
def cleanup(ctx, yes: bool) -> None:
    """Clean up dcc-bridge data and auto-startup scripts (use before uninstall).

    清理 dcc-bridge 数据与自启动脚本（卸载前使用）。
    """
    user_data_dir = get_user_data_dir()

    # 先发现所有 setup 子类，用于确认提示
    setup_classes = _discover_setup_classes()
    dcc_names = [cls.dcc_type for cls in setup_classes]

    if not yes:
        click.echo("即将执行以下清理操作：")
        click.echo(f"  1. 删除用户数据目录: {user_data_dir}")
        if dcc_names:
            click.echo(f"  2. 移除以下 DCC 的自启动脚本: {', '.join(dcc_names)}")
        else:
            click.echo("  2. 未发现可清理的 DCC 自启动脚本")
        click.echo("")
        if not click.confirm("确认继续？"):
            click.echo("已取消")
            ctx.exit(0)

    # 1. 删除用户数据目录
    if os.path.exists(user_data_dir):
        try:
            shutil.rmtree(user_data_dir)
            click.echo(f"Removed user data directory: {user_data_dir}")
        except OSError as e:
            click.echo(f"Failed to remove user data directory: {e}", err=True)
            ctx.exit(1)
    else:
        click.echo(f"User data directory not found: {user_data_dir}")

    # 2. 对所有发现的 DCC 执行 unsetup
    any_failed = False
    for setup_cls in setup_classes:
        dcc_type = setup_cls.dcc_type
        try:
            setup_instance = setup_cls()
        except Exception as e:
            click.echo(f"Failed to instantiate setup for {dcc_type}: {e}", err=True)
            any_failed = True
            continue

        try:
            success = setup_instance.unsetup()
            if success:
                click.echo(f"Unsetup succeeded for {dcc_type}")
            else:
                click.echo(f"Unsetup returned failure for {dcc_type} (may not be installed)", err=True)
                any_failed = True
        except Exception as e:
            click.echo(f"Unsetup error for {dcc_type}: {e}", err=True)
            any_failed = True

    if any_failed:
        ctx.exit(1)
