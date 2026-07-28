"""
BlenderAdapter 单元测试

Blender 运行环境（bpy 模块）在测试机通常不可用，
因此 get_python_path / get_version 需验证「无 bpy 时回退基类」，
以及「有 bpy 时派生内置 Python 路径」两种路径。
"""

from __future__ import annotations

import os
import sys

import pytest

from dcc_bridge.adapters.base import DCCAdapter, Logger
from dcc_bridge.adapters.blender import BlenderAdapter, BlenderLogger


# ==================== 基础属性 ====================

class TestBasic:
    def test_name_is_blender(self):
        assert BlenderAdapter().name == "blender"

    def test_get_logger_returns_blender_logger(self):
        logger = BlenderAdapter().get_logger()
        assert logger is BlenderLogger
        assert logger.channel == "Blender"

    def test_is_dcc_adapter_subclass(self):
        assert isinstance(BlenderAdapter(), DCCAdapter)


# ==================== on_connected ====================

class TestOnConnected:
    def test_on_connected_does_not_raise(self, capsys):
        """Blender 无 Qt 主窗口，on_connected 应只打印日志而不抛异常"""
        adapter = BlenderAdapter()
        adapter.on_connected()  # 不应抛出
        captured = capsys.readouterr()
        assert "connected" in captured.out


# ==================== add_sys_path ====================

class TestAddSysPath:
    def test_adds_to_sys_path(self):
        adapter = BlenderAdapter()
        fake = os.path.join("some", "fake", "blender", "path")
        if fake in sys.path:
            sys.path.remove(fake)
        try:
            adapter.add_sys_path(fake)
            assert fake in sys.path
        finally:
            if fake in sys.path:
                sys.path.remove(fake)

    def test_does_not_duplicate(self):
        adapter = BlenderAdapter()
        fake = os.path.join("another", "fake", "blender", "path")
        if fake in sys.path:
            sys.path.remove(fake)
        try:
            adapter.add_sys_path(fake)
            adapter.add_sys_path(fake)  # 不应重复添加
            assert sys.path.count(fake) == 1
        finally:
            if fake in sys.path:
                sys.path.remove(fake)


# ==================== get_python_path ====================

class TestGetPythonPath:
    def test_fallback_when_bpy_unavailable(self, monkeypatch):
        """bpy 不可导入时，应回退到基类（sys.executable）"""
        # 模拟 import bpy 抛 ImportError
        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "bpy" or name.startswith("bpy."):
                raise ImportError("no bpy")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        adapter = BlenderAdapter()
        assert adapter.get_python_path() == sys.executable

    def test_derives_bundled_python_when_bpy_available(self, monkeypatch):
        """bpy 可用时，应从 bpy.app.binary_path 派生内置 Python 路径"""

        class FakeApp:
            binary_path = r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
            version = (4, 5, 0)

        fake_bpy = type("bpy", (), {"app": FakeApp()})()

        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "bpy" or name.startswith("bpy."):
                return fake_bpy
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        adapter = BlenderAdapter()
        py = adapter.get_python_path()
        assert py == r"C:\Program Files\Blender Foundation\Blender 4.5\4.5\python\bin\python.exe"


# ==================== get_version ====================

class TestGetVersion:
    def test_fallback_when_bpy_unavailable(self, monkeypatch):
        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "bpy" or name.startswith("bpy."):
                raise ImportError("no bpy")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        assert BlenderAdapter().get_version() == "Unknown"

    def test_returns_bpy_version_string(self, monkeypatch):
        class FakeApp:
            version_string = "4.5.0"

        fake_bpy = type("bpy", (), {"app": FakeApp()})()

        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "bpy" or name.startswith("bpy."):
                return fake_bpy
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        assert BlenderAdapter().get_version() == "4.5.0"


# ==================== run_on_main_thread ====================

class TestRunOnMainThread:
    def test_schedules_via_bpy_timers(self, monkeypatch):
        """run_on_main_thread 应通过 bpy.app.timers.register 把回调派发到主线程"""

        scheduled = {}

        class FakeTimers:
            def register(self, callback, first_interval=0):
                scheduled["callback"] = callback
                scheduled["first_interval"] = first_interval

        class FakeApp:
            timers = FakeTimers()

        fake_bpy = type("bpy", (), {"app": FakeApp()})()

        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "bpy" or name.startswith("bpy."):
                return fake_bpy
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)

        adapter = BlenderAdapter()
        result_box = {}

        def cb(a, b):
            result_box["v"] = a + b

        adapter.run_on_main_thread(cb, 2, 3)

        # 应已登记到 bpy.app.timers，且 first_interval 为 0
        assert "callback" in scheduled
        assert scheduled["first_interval"] == 0
        # 模拟主线程事件循环触发回调
        scheduled["callback"]()
        assert result_box["v"] == 5
