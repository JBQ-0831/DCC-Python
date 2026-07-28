"""
SubstanceDesigner Adapter
实现 SubstanceDesigner 特定的日志、Python 路径和初始化逻辑
"""

from __future__ import annotations

import sys
import os

from .base import DCCAdapter, Logger


class SubstanceDesignerLogger(Logger):
    """SubstanceDesigner 专用日志类"""

    # channel = "SubstanceDesigner"

    @classmethod
    def info(cls, message: str):
        super().info(message)

    @classmethod
    def warn(cls, message: str):
        super().warn(message)

    @classmethod
    def error(cls, message: str):
        super().error(message)


class SubstanceDesignerAdapter(DCCAdapter):
    """
    SubstanceDesigner Adapter

    实现 SubstanceDesigner 特定的逻辑，包括：
    - 日志输出到 SubstanceDesigner 脚本编辑器
    - Python 路径获取（python.exe）
    - 初始化逻辑
    """

    name: str = "substance_designer"

    def get_logger(self) -> Logger:
        return SubstanceDesignerLogger

    def get_python_path(self) -> str:
        """
        返回 SubstanceDesigner 的 Python 解释器路径（python.exe）

        所有版本的SP的python解析器路径都位于根目录下的: "./plugins/pythonsdk/python.exe"
        """
        exe_dir = os.path.dirname(super().get_python_path())
        exe_name = "python.exe" if sys.platform == "win32" else "python"
        return os.path.join(exe_dir, "plugins", "pythonsdk", exe_name)

    def on_connected(self) -> None:
        try:
            import sd

            ctx = sd.getContext()
            app = ctx.getSDApplication()
            uimgr = app.getUIMgr()

            # 兼容Pyside2/Pyside6 + 对应shiboken
            try:
                from PySide2.QtWidgets import QWidget
                from shiboken2 import wrapInstance
            except ImportError:
                from PySide6.QtWidgets import QWidget
                from shiboken6 import wrapInstance

            ptr = uimgr.getMainWindowPtr()
            parent_window = wrapInstance(int(ptr), QWidget)
        except:
            logger = self.get_logger()
            logger.error("无法获取主窗口。substance_designer.ui 不可用。")
            return
        super()._on_connected(parent_window)

    def add_sys_path(self, path: str) -> None:
        super().add_sys_path(path)
        logger = self.get_logger()
        logger.info(f"Added to {self.name} sys.path: {path}")

    def get_version(self) -> str:
        try:
            import sd

            ctx = sd.getContext()
            app = ctx.getSDApplication()
            version = app.getVersion()
            return version
        except:
            return super().get_version()

    def configure_debugpy(self, python_path: str) -> None:
        """
            SD 内置 Python 是打包冻结版（frozen modules），
            debugpy 默认校验源码文件一致性，冻结内置库会触发断点失效警告，
            两种解决思路：关闭冻结模块 / 跳过文件校验。

            这里选择在脚本最顶部添加环境变量，提前关闭校验，从而屏蔽警告
        Args:
            python_path: 用于启动子进程的 Python 解释器路径
        """
        # 放在所有import最前面
        import os

        os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"
        import debugpy

        debugpy.configure(python=python_path)
