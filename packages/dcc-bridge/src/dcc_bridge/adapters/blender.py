"""
Blender Adapter
实现 Blender 特定的日志、Python 路径和初始化逻辑。

注意：Blender 的 UI 不是 Qt 框架（无 PySide/PySide2 嵌入的主窗口），
因此 on_connected 只做日志输出，不尝试弹出 PySide 消息框。
"""

from __future__ import annotations

import sys
import os

from .base import DCCAdapter, Logger


class BlenderLogger(Logger):
    """Blender 专用日志类"""

    channel = "Blender"

    @classmethod
    def info(cls, message: str):
        super().info(message)

    @classmethod
    def warn(cls, message: str):
        super().warn(message)

    @classmethod
    def error(cls, message: str):
        super().error(message)


class BlenderAdapter(DCCAdapter):
    """
    Blender Adapter

    实现 Blender 特定的逻辑，包括：
    - 日志输出（Blender 内置 Python 控制台）
    - Python 路径获取（Blender 内置 Python，而非 blender 可执行文件）
    - 连接初始化（Blender 无 Qt 主窗口，仅日志）
    """

    name: str = "blender"

    def get_logger(self) -> Logger:
        return BlenderLogger

    def get_python_path(self) -> str:
        """
        返回 Blender 内置的 Python 解释器路径

        Blender 运行脚本时 sys.executable 指向 blender 可执行文件，
        但 pip 和 debugpy 需要 Blender 自带的 Python 解释器：
            <安装目录>/<version>/python/bin/python.exe

        安装目录由 bpy.app.binary_path（blender 可执行文件）的所在目录得到，
        <version> 取 bpy.app.version 的 major.minor（如 "4.5"）。
        """
        try:
            import bpy

            blender_exe = bpy.app.binary_path
            if blender_exe:
                install_dir = os.path.dirname(blender_exe)
                version = ".".join(str(v) for v in bpy.app.version[:2])
                python_exe = "python.exe" if sys.platform == "win32" else "python"
                return os.path.join(
                    install_dir, version, "python", "bin", python_exe
                )
        except Exception:
            pass
        return super().get_python_path()

    def on_connected(self) -> None:
        """
        连接建立后的回调

        Blender 的 UI 不是 Qt 框架，无法像 Maya 那样获取主窗口 QWidget，
        因此这里只做日志输出，不弹出消息框。
        """
        logger = self.get_logger()
        logger.info("DCC Bridge Server connected")

    def run_on_main_thread(self, callback, *args, **kwargs):
        """
        在 Blender 主线程执行回调

        Blender 的 bpy 操作必须在主线程执行，而服务端运行在后台线程。
        通过 bpy.app.timers.register 把回调排到主线程的事件循环下一拍执行，
        并用 threading.Event 阻塞等待完成，确保异常能被正确传播到调用方。
        """
        import bpy
        import threading

        result = []
        error = []
        event = threading.Event()

        def _wrapper():
            try:
                result.append(callback(*args, **kwargs))
            except Exception as e:
                error.append(e)
            finally:
                event.set()

        bpy.app.timers.register(_wrapper, first_interval=0)
        event.wait(timeout=60.0)

        if error:
            raise error[0]
        return result[0] if result else None

    def add_sys_path(self, path: str) -> None:
        super().add_sys_path(path)
        logger = self.get_logger()
        logger.info(f"Added to {self.name} sys.path: {path}")

    def get_version(self) -> str:
        try:
            import bpy

            return bpy.app.version_string
        except Exception:
            return super().get_version()
