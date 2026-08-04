# -*- coding: utf-8 -*-
"""
SubstancePainter Adapter
实现 SubstancePainter 特定的日志、Python 路径和初始化逻辑

兼容 Python 2.7 / 3.x：不使用 from __future__ import annotations、
变量注解、f-string、无参 super() 等 py3-only 语法。
"""

import sys
import os

from .base_adapter import DCCAdapter, Logger


class SubstancePainterLogger(Logger):
    """SubstancePainter 专用日志类"""

    # channel = "SubstancePainter"

    @classmethod
    def info(cls, message):
        try:
            import substance_painter as sp

            sp.logging.log(sp.logging.INFO, cls.channel, message)
        except:
            super(SubstancePainterLogger, cls).info(message)

    @classmethod
    def warn(cls, message):
        try:
            import substance_painter as sp

            sp.logging.log(sp.logging.WARNING, cls.channel, message)
        except:
            super(SubstancePainterLogger, cls).warn(message)

    @classmethod
    def error(cls, message):
        try:
            import substance_painter as sp

            sp.logging.log(sp.logging.ERROR, cls.channel, message)
        except:
            super(SubstancePainterLogger, cls).error(message)


class SubstancePainterAdapter(DCCAdapter):
    """
    SubstancePainter Adapter

    实现 SubstancePainter 特定的逻辑，包括：
    - 日志输出到 SubstancePainter 脚本编辑器
    - Python 路径获取（python.exe）
    - 初始化逻辑
    """

    name = "substance_painter"

    def get_logger(self):
        return SubstancePainterLogger

    def get_python_path(self):
        """
        返回 SubstancePainter 的 Python 解释器路径（python.exe）

        所有版本的SP的python解析器路径都位于根目录下的: "./resources/pythonsdk/python.exe"
        """
        exe_dir = os.path.dirname(
            super(SubstancePainterAdapter, self).get_python_path()
        )
        exe_name = "python.exe" if sys.platform == "win32" else "python"
        return os.path.join(exe_dir, "resources", "pythonsdk", exe_name)

    def on_connected(self):
        try:
            import substance_painter.ui as sp_ui

            parent_window = sp_ui.get_main_window()
        except:
            logger = self.get_logger()
            logger.error("无法获取主窗口。substance_painter.ui 不可用。")
            return
        super(SubstancePainterAdapter, self)._on_connected(parent_window)

    def add_sys_path(self, path):
        super(SubstancePainterAdapter, self).add_sys_path(path)
        logger = self.get_logger()
        logger.info("Added to {0} sys.path: {1}".format(self.name, path))

    def get_version(self):
        try:
            import substance_painter.application as sp_app

            version = sp_app.version()
            return version
        except:
            return super(SubstancePainterAdapter, self).get_version()
