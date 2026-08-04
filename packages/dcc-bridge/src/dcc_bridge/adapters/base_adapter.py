# -*- coding: utf-8 -*-
"""
DCC Adapter 基类
所有 DCC Adapter 都应继承此类并实现特定逻辑

兼容 Python 2.7 / 3.x：不使用 from __future__ import annotations、
变量注解（name: str = ...）、f-string、无参 super() 等 py3-only 语法。
"""

import sys
import os


class Logger(object):
    """通用日志类，各 DCC 可继承并覆盖

    显式继承 object：Python 2 下必须保证是 new-style class，否则所有
    子类（MaxAdapter 等）在 py2 下都会变成经典类，导致
    super(MaxAdapter, self) 报 "super() argument 1 must be type, not classobj"。
    Python 3 下 (object) 冗余但无害。
    """

    channel = "DCC Bridge"

    @classmethod
    def _emit(cls, level, message):
        # py2 + DCC 宿主（如 Max 2019）常把 stdout/stderr 劫持为只收 unicode 的流，
        # 普通 print 语句写 str(bytes) 会报 "unicode argument expected, got 'str'"。
        # 统一把内容转成 unicode（py2）/ str（py3）再输出，并用 try/except 兜底，
        # 兼容 stdout 既可能期望 unicode（io.StringIO / DCC 日志流）也可能期望
        # bytes（cStringIO）的情况。
        if sys.version_info[0] == 2 and isinstance(message, str):
            message = message.decode("utf-8", "replace")
        text = u"[{0}] {1}: {2}".format(level, cls.channel, message)
        try:
            sys.stdout.write(text + u"\n")
        except (UnicodeEncodeError, TypeError):
            # stdout 只收 bytes 的极端情况，回退编码后写
            sys.stdout.write((text + u"\n").encode("utf-8", "replace"))

    @classmethod
    def info(cls, message):
        cls._emit("INFO", message)

    @classmethod
    def warn(cls, message):
        cls._emit("WARN", message)

    @classmethod
    def error(cls, message):
        cls._emit("ERROR", message)


class DCCAdapter(object):
    """
    DCC Adapter 基类

    各 DCC 应继承此类并实现特定逻辑。
    基类提供默认实现，确保服务端可以正常运行。

    显式继承 object：Python 2 下必须保证是 new-style class，否则所有
    子类在 py2 下都会变成经典类（classobj），导致 super(SubClass, self)
    报 "super() argument 1 must be type, not classobj"。Python 3 下
    (object) 冗余但无害。
    """

    name = "unknown"
    """DCC 名称，如 "maya", "3dsmax", "substance_painter" """

    def get_logger(self):
        """返回 DCC 特定的日志对象"""
        return Logger

    def get_python_path(self):
        """
        返回 DCC 的 Python 解释器路径

        用于 debugpy 配置和 pip 安装。
        默认返回 sys.executable，各 DCC 子类可覆盖此方法。
        """
        return sys.executable

    def _on_connected(self, parent_window):
        """
        连接建立后的初始化回调

        可用于执行 DCC 特定的初始化操作
        """
        logger = self.get_logger()
        logger.info("DCC Bridge Server connected")

        try:
            try:
                from PySide2.QtWidgets import QMessageBox
            except ImportError:
                from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                parent_window, "DCC Python", "DCC Bridge Server connected"
            )

        except:
            logger.warn("PySide2/PySide6 not found, cannot show connection message box")

    def add_sys_path(self, path):
        """
        将指定路径添加到 sys.path

        Args:
            path: 要添加的路径
        """
        if path not in sys.path:
            sys.path.append(path)

    def get_version(self):
        return "Unknown"

    def format_output(self, line):
        """
        可选：DCC 特定的输出格式化

        Args:
            line: 原始输出行

        Returns:
            格式化后的输出行
        """
        return line

    def is_main_thread(self):
        """
        检查当前是否在主线程中

        默认返回 True（假设调用者已确保在主线程）

        Returns:
            True 如果在主线程，否则 False
        """
        return True

    def run_on_main_thread(self, callback, *args, **kwargs):
        """
        在 DCC 的主线程（或合适的目标上下文）中执行回调

        默认实现直接在调用线程（服务端后台线程）中执行，
        适用于不强制要求主线程的 DCC / 通用环境。

        需要主线程的 DCC（如 Blender）应覆写此方法，
        例如通过 bpy.app.timers 把回调派发到主线程。

        Args:
            callback: 要执行的可调用对象
            *args, **kwargs: 传递给 callback 的参数

        Returns:
            callback 的执行结果
        """
        return callback(*args, **kwargs)

    def ensure_main_thread(self):
        """
        确保在主线程中执行（如果需要）

        默认实现不做任何操作
        """
        pass

    def configure_debugpy(self, python_path):
        """
        配置 debugpy 的全局选项

        默认调用 debugpy.configure(python=python_path)。
        各 DCC 子类可覆盖此方法来避免特定 DCC 下的兼容性问题。

        Args:
            python_path: 用于启动子进程的 Python 解释器路径
        """
        import debugpy

        debugpy.configure(python=python_path)
