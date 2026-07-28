"""
Houdini Adapter
实现 Houdini 特定的日志、Python 路径和初始化逻辑
"""

from __future__ import annotations

import os
import sys

from dcc_bridge.adapters.base import DCCAdapter, Logger


class HoudiniLogger(Logger):
    """Houdini 专用日志类

    Houdini 的 Python 输出会进入其内置的脚本输出窗口，
    这里在无法访问 hou 模块时回退到标准打印。
    """

    # channel = "Houdini"

    @classmethod
    def info(cls, message: str):
        super().info(message)

    @classmethod
    def warn(cls, message: str):
        super().warn(message)

    @classmethod
    def error(cls, message: str):
        super().error(message)


class HoudiniAdapter(DCCAdapter):
    """
    Houdini Adapter

    实现 Houdini 特定的逻辑，包括：
    - 日志输出到 Houdini 脚本输出窗口
    - Python 路径获取（Houdini 内置的 python3X/python.exe）
    - 初始化逻辑（定位 Qt 主窗口）
    """

    name: str = "houdini"

    def get_logger(self) -> Logger:
        return HoudiniLogger

    def get_python_path(self) -> str:
        """
        返回 Houdini 内置的 Python 解释器路径

        Houdini 内嵌 Python 的 sys.prefix 即指向其内置的 python3X 目录，
        该目录下存在独立的 python.exe，可用于 pip / debugpy。
        """
        exe_name = "python.exe" if sys.platform == "win32" else "python"
        return os.path.join(sys.prefix, exe_name)

    def on_connected(self) -> None:
        try:
            import hou

            parent_window = hou.qt.mainWindow()
        except Exception:
            logger = self.get_logger()
            logger.error("无法获取主窗口。hou.qt.mainWindow() 不可用。")
            return
        super()._on_connected(parent_window)

    def add_sys_path(self, path: str) -> None:
        super().add_sys_path(path)
        logger = self.get_logger()
        logger.info(f"Added to {self.name} sys.path: {path}")

    def get_version(self) -> str:
        try:
            import hou

            return hou.applicationVersionString()
        except Exception:
            return super().get_version()
