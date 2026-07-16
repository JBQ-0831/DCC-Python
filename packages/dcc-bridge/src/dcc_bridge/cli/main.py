"""
dcc 命令主入口
"""
from __future__ import annotations

import click

from .. import __version__
from .cleanup import cleanup
from .run import run_group
from .setup import setup, unsetup
from .status import ping, status


@click.group()
@click.version_option(version=__version__, prog_name="dcc")
def dcc() -> None:
    """DCC Bridge CLI: 在 DCC 中执行 Python 代码或管理 DCC 启动注入。"""


# 注册全部子命令
dcc.add_command(run_group, name="run")
dcc.add_command(setup)
dcc.add_command(unsetup)
dcc.add_command(status)
dcc.add_command(ping)
dcc.add_command(cleanup)


def main() -> None:
    dcc()


if __name__ == "__main__":
    main()