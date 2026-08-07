# -*- coding: utf-8 -*-
"""
Maya Adapter
实现 Maya 特定的日志、Python 路径和初始化逻辑

兼容 Python 2.7 / 3.x：不使用 from __future__ import annotations、
变量注解、f-string、无参 super() 等 py3-only 语法。
"""

import sys
import os
import traceback

from .base_adapter import DCCAdapter, Logger


class MayaLogger(Logger):
    """Maya 专用日志类"""

    # channel = "Maya"

    @classmethod
    def info(cls, message):
        super(MayaLogger, cls).info(message)

    @classmethod
    def warn(cls, message):
        super(MayaLogger, cls).warn(message)

    @classmethod
    def error(cls, message):
        super(MayaLogger, cls).error(message)


class MayaAdapter(DCCAdapter):
    """
    Maya Adapter

    实现 Maya 特定的逻辑，包括：
    - 日志输出到 Maya 脚本编辑器
    - Python 路径获取（mayapy.exe，而非 maya.exe）
    - 初始化逻辑
    """

    name = "maya"

    def get_logger(self):
        return MayaLogger

    def get_python_path(self):
        """
        返回 Maya 的 Python 解释器路径（mayapy.exe）

        Maya 中 sys.executable 是 maya.exe（主程序），
        但 pip 和 debugpy 需要用 mayapy.exe（独立 Python 解释器）。
        mayapy.exe 与 maya.exe 同在 bin 目录下。
        """
        exe_dir = os.path.dirname(
            super(MayaAdapter, self).get_python_path()
        )
        exe_name = "mayapy.exe" if sys.platform == "win32" else "mayapy"
        return os.path.join(exe_dir, exe_name)

    def on_connected(self):
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
        super(MayaAdapter, self)._on_connected(parent_window)

    def add_sys_path(self, path):
        super(MayaAdapter, self).add_sys_path(path)
        logger = self.get_logger()
        logger.info("Added to {0} sys.path: {1}".format(self.name, path))

    def get_version(self):
        try:
            from maya import cmds as cm

            version = cm.about(version=True)
            return version
        except Exception:
            # 暴露真实异常，便于排查（如早期调用 about 抛错、cmds 导入失败等）
            logger = self.get_logger()
            logger.error(traceback.format_exc())
            return super(MayaAdapter, self).get_version()
