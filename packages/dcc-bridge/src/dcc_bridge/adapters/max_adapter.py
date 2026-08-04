# -*- coding: utf-8 -*-
"""
3ds Max Adapter
实现 3ds Max 特定的日志、Python 路径和初始化逻辑

兼容 Python 2.7 / 3.x：不使用 from __future__ import annotations、
变量注解、f-string、无参 super() 等 py3-only 语法。
"""

import sys
import os

from .base_adapter import DCCAdapter, Logger


class MaxLogger(Logger):
    """3ds Max 专用日志类"""

    # channel = "3ds Max"

    @classmethod
    def info(cls, message):
        super(MaxLogger, cls).info(message)

    @classmethod
    def warn(cls, message):
        super(MaxLogger, cls).warn(message)

    @classmethod
    def error(cls, message):
        super(MaxLogger, cls).error(message)


class MaxAdapter(DCCAdapter):
    """
    3ds Max Adapter

    实现 3ds Max 特定的逻辑，包括：
    - 日志输出到 3ds Max 脚本监听器
    - Python 路径获取（3ds Max 自带的 Python）
    - 初始化逻辑
    """

    name = "3dsmax"

    def get_logger(self):
        return MaxLogger

    def get_python_path(self):
        """
        返回 3ds Max 的 Python 解释器路径

        2021 及以上版本: <Max目录>\\Python\\python.exe
        2020 及以下版本: <Max目录>\\3dsmaxpy.exe
        """
        exe_dir = os.path.dirname(
            super(MaxAdapter, self).get_python_path()
        )
        try:
            import pymxs

            version = pymxs.runtime.maxVersion()
            # 3ds Max 版本号: 2024=26000, 2023=25000, 2020=22000
            if version[0] >= 22000:
                return os.path.join(exe_dir, "Python", "python.exe")
        except Exception:
            pass
        # 旧版本使用 3dsmaxpy.exe
        exe_name = "3dsmaxpy.exe" if sys.platform == "win32" else "3dsmaxpy"
        return os.path.join(exe_dir, exe_name)

    def on_connected(self):
        try:
            import MaxPlus

            parent_window = MaxPlus.GetQMaxMainWindow()
        except:
            try:
                import qtmax

                parent_window = qtmax.GetQMaxMainWindow()
            except:
                logger = self.get_logger()
                logger.error("无法获取主窗口。MaxPlus 和 qtmax 都不可用。")
                return
        super(MaxAdapter, self)._on_connected(parent_window)

    def add_sys_path(self, path):
        super(MaxAdapter, self).add_sys_path(path)
        logger = self.get_logger()
        logger.info("Added to {0} sys.path: {1}".format(self.name, path))

    def get_version(self):
        try:
            import pymxs

            version_array = pymxs.runtime.maxVersion()
            version = str(version_array[0] // 1000 + 1998)  # 26000 -> 2024
            print(version)
            return version
        except Exception:
            return super(MaxAdapter, self).get_version()
