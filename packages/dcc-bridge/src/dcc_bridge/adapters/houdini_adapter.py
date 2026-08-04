# -*- coding: utf-8 -*-
"""
Houdini Adapter
实现 Houdini 特定的日志、Python 路径和初始化逻辑

兼容 Python 2.7 / 3.x：不使用 from __future__ import annotations、
变量注解、f-string、无参 super() 等 py3-only 语法；
queue 模块在 py2 名为 Queue，做兼容导入。
"""

import os
import sys
import threading

try:
    import queue
except ImportError:
    import Queue as queue  # py2 兼容

from dcc_bridge.adapters.base import DCCAdapter, Logger


class HoudiniLogger(Logger):
    """Houdini 专用日志类

    Houdini 的 Python 输出会进入其内置的脚本输出窗口，
    这里在无法访问 hou 模块时回退到标准打印。
    """

    # channel = "Houdini"

    @classmethod
    def info(cls, message):
        super(HoudiniLogger, cls).info(message)

    @classmethod
    def warn(cls, message):
        super(HoudiniLogger, cls).warn(message)

    @classmethod
    def error(cls, message):
        super(HoudiniLogger, cls).error(message)


class HoudiniAdapter(DCCAdapter):
    """
    Houdini Adapter

    实现 Houdini 特定的逻辑，包括：
    - 日志输出到 Houdini 脚本输出窗口
    - Python 路径获取（Houdini 内置的 python3X/python.exe）
    - 初始化逻辑（定位 Qt 主窗口）
    """

    name = "houdini"

    # 主线程派发队列与一次性事件循环回调（避免每请求注册导致的永久累积/死循环）
    _main_thread_queue = queue.Queue()
    _loop_callback_ref = None
    _loop_callback_lock = threading.Lock()

    def __init__(self):
        super(HoudiniAdapter, self).__init__()
        self._ensure_event_loop_callback()

    def _ensure_event_loop_callback(self):
        """注册一次性的 hou.ui.addEventLoopCallback，用于在主线程泵送队列。"""
        with HoudiniAdapter._loop_callback_lock:
            if HoudiniAdapter._loop_callback_ref is not None:
                return
            try:
                import hou

                hou.ui.addEventLoopCallback(self._drain_main_thread_queue)
                HoudiniAdapter._loop_callback_ref = self._drain_main_thread_queue
            except Exception:
                # 注册失败时退化为调用线程直接执行（可能触发 DCC 异常但至少不崩溃）
                HoudiniAdapter._loop_callback_ref = None

    def _drain_main_thread_queue(self):
        """在主线程事件循环中每个 tick 调用，执行所有排队的回调。"""
        while True:
            try:
                item = HoudiniAdapter._main_thread_queue.get_nowait()
            except queue.Empty:
                break
            callback, args, kwargs, done_event = item
            try:
                callback(*args, **kwargs)
            except Exception:
                pass
            finally:
                done_event.set()

    def run_on_main_thread(self, callback, *args, **kwargs):
        """通过一次性注册的事件循环回调把回调派发到 Houdini 主线程。"""
        done_event = threading.Event()
        HoudiniAdapter._main_thread_queue.put(
            (callback, args, kwargs, done_event)
        )
        if HoudiniAdapter._loop_callback_ref is None:
            self._ensure_event_loop_callback()
        done_event.wait(timeout=60.0)
        return None

    def get_logger(self):
        return HoudiniLogger

    def get_python_path(self):
        """
        返回 Houdini 内置的 Python 解释器路径

        Houdini 内嵌 Python 的 sys.prefix 即指向其内置的 python3X 目录，
        该目录下存在独立的 python.exe，可用于 pip / debugpy。
        """
        exe_name = "python.exe" if sys.platform == "win32" else "python"
        return os.path.join(sys.prefix, exe_name)

    def on_connected(self):
        try:
            import hou

            parent_window = hou.qt.mainWindow()
        except Exception:
            logger = self.get_logger()
            logger.error("无法获取主窗口。hou.qt.mainWindow() 不可用。")
            return
        super(HoudiniAdapter, self)._on_connected(parent_window)

    def add_sys_path(self, path):
        super(HoudiniAdapter, self).add_sys_path(path)
        logger = self.get_logger()
        logger.info("Added to {0} sys.path: {1}".format(self.name, path))

    def get_version(self):
        try:
            import hou

            return hou.applicationVersionString()
        except Exception:
            return super(HoudiniAdapter, self).get_version()
