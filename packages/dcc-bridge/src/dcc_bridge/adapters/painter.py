"""
SubstancePainter Adapter
实现 SubstancePainter 特定的日志、Python 路径和初始化逻辑
"""

from __future__ import annotations

import sys
import os

from .base import DCCAdapter, Logger


class SubstancePainterLogger(Logger):
    """SubstancePainter 专用日志类"""

    # channel = "SubstancePainter"

    @classmethod
    def info(cls, message: str):
        try:
            import substance_painter as sp

            sp.logging.log(sp.logging.INFO, cls.channel, message)
        except:
            super().info(message)

    @classmethod
    def warn(cls, message: str):
        try:
            import substance_painter as sp

            sp.logging.log(sp.logging.WARNING, cls.channel, message)
        except:
            super().warn(message)

    @classmethod
    def error(cls, message: str):
        try:
            import substance_painter as sp

            sp.logging.log(sp.logging.ERROR, cls.channel, message)
        except:
            super().error(message)


class SubstancePainterAdapter(DCCAdapter):
    """
    SubstancePainter Adapter

    实现 SubstancePainter 特定的逻辑，包括：
    - 日志输出到 SubstancePainter 脚本编辑器
    - Python 路径获取（python.exe）
    - 初始化逻辑
    """

    name: str = "substance_painter"

    def get_logger(self) -> Logger:
        return SubstancePainterLogger

    def get_python_path(self) -> str:
        """
        返回 SubstancePainter 的 Python 解释器路径（python.exe）

        所有版本的SP的python解析器路径都位于根目录下的: "./resources/pythonsdk/python.exe"
        """
        exe_dir = os.path.dirname(super().get_python_path())
        exe_name = "python.exe" if sys.platform == "win32" else "python"
        return os.path.join(exe_dir, "resources", "pythonsdk", exe_name)

    def on_connected(self) -> None:
        try:
            import substance_painter.ui as sp_ui

            parent_window = sp_ui.get_main_window()
        except:
            logger = self.get_logger()
            logger.error("无法获取主窗口。substance_painter.ui 不可用。")
            return
        super()._on_connected(parent_window)

    def add_sys_path(self, path: str) -> None:
        super().add_sys_path(path)
        logger = self.get_logger()
        logger.info(f"Added to {self.name} sys.path: {path}")

    def get_version(self) -> str:
        try:
            import substance_painter.application as sp_app

            version = sp_app.version()
            return version
        except:
            return super().get_version()