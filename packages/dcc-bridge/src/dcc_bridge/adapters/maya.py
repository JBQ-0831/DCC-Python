"""
Maya Adapter
实现 Maya 特定的日志、Python 路径和初始化逻辑
"""

from __future__ import annotations

import sys
import os

from .base import DCCAdapter, Logger


class MayaLogger(Logger):
    """Maya 专用日志类"""

    # channel = "Maya"

    @classmethod
    def info(cls, message: str):
        super().info(message)

    @classmethod
    def warn(cls, message: str):
        super().warn(message)

    @classmethod
    def error(cls, message: str):
        super().error(message)


class MayaAdapter(DCCAdapter):
    """
    Maya Adapter

    实现 Maya 特定的逻辑，包括：
    - 日志输出到 Maya 脚本编辑器
    - Python 路径获取（mayapy.exe，而非 maya.exe）
    - 初始化逻辑
    """

    name: str = "maya"

    def get_logger(self) -> Logger:
        return MayaLogger

    def get_python_path(self) -> str:
        """
        返回 Maya 的 Python 解释器路径（mayapy.exe）

        Maya 中 sys.executable 是 maya.exe（主程序），
        但 pip 和 debugpy 需要用 mayapy.exe（独立 Python 解释器）。
        mayapy.exe 与 maya.exe 同在 bin 目录下。
        """
        exe_dir = os.path.dirname(super().get_python_path())
        exe_name = "mayapy.exe" if sys.platform == "win32" else "mayapy"
        return os.path.join(exe_dir, exe_name)

    def on_connected(self) -> None:
        try:
            # 兼容Pyside2/Pyside6 + 对应shiboken
            try:
                from PySide2.QtWidgets import QWidget
                from shiboken2 import wrapInstance
            except ImportError:
                from PySide6.QtWidgets import QWidget
                from shiboken6 import wrapInstance
            import maya.OpenMayaUI as omui
            parent_window = wrapInstance(int(omui.MQtUtil.mainWindow()), QWidget)
        except:
            logger = self.get_logger()
            logger.error("无法获取主窗口。maya.OpenMayaUI 不可用。")
            return
        super()._on_connected(parent_window)

    def add_sys_path(self, path: str) -> None:
        super().add_sys_path(path)
        logger = self.get_logger()
        logger.info(f"Added to {self.name} sys.path: {path}")
    def get_version(self) -> str:
        try:
            from maya import cmds

            version = cmds.about(version=True)
            print(version)
            return version
        except:
            return super().get_version()