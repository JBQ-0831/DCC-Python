# -*- coding: utf-8 -*-
"""
验证 T7: setup/unsetup 的 Python 主版本门控逻辑。

_get_python_major_version 通过真实运行目标 DCC 的 Python 解释器查询
sys.version_info[0]，避免依赖脆弱的版本映射。本测试在各分支上 mock
subprocess.Popen 与 get_python_path，覆盖 py3 / py2 / 缺失 / 异常等场景。
"""

import dcc_bridge.setup.base as base_mod
from dcc_bridge.setup.base import DCCSetup


class _FakeSetup(DCCSetup):
    """最小可实例化子类，仅实现抽象方法，python_path 由测试动态注入。"""

    def discover_versions(self):
        return []

    def get_install_path(self, version):
        return None

    def get_script_dir(self, version=None, language="en"):
        return None

    def get_python_path(self, version):
        return self._fake_path


def _make_popen(stdout_str):
    """返回一个伪装成 subprocess.Popen 的工厂，communicate 返回给定 stdout。"""

    class _Proc:
        def communicate(self):
            out = stdout_str.encode("utf-8") if isinstance(stdout_str, str) else stdout_str
            return (out, b"")

    return lambda *a, **k: _Proc()


class TestGetPythonMajorVersion:
    def test_returns_3_for_py3(self, monkeypatch):
        inst = _FakeSetup()
        monkeypatch.setattr(inst, "get_python_path", lambda v: "/py/python.exe")
        monkeypatch.setattr(base_mod.os.path, "exists", lambda p: True)
        monkeypatch.setattr(base_mod.subprocess, "Popen", _make_popen("3\n"))
        assert inst._get_python_major_version("1.0") == 3

    def test_returns_2_for_py2(self, monkeypatch):
        inst = _FakeSetup()
        monkeypatch.setattr(inst, "get_python_path", lambda v: "/py/python.exe")
        monkeypatch.setattr(base_mod.os.path, "exists", lambda p: True)
        monkeypatch.setattr(base_mod.subprocess, "Popen", _make_popen("2\n"))
        assert inst._get_python_major_version("1.0") == 2

    def test_returns_none_when_path_missing(self, monkeypatch):
        inst = _FakeSetup()
        monkeypatch.setattr(inst, "get_python_path", lambda v: None)
        assert inst._get_python_major_version("1.0") is None

    def test_returns_none_when_not_exists(self, monkeypatch):
        inst = _FakeSetup()
        monkeypatch.setattr(inst, "get_python_path", lambda v: "/py/python.exe")
        monkeypatch.setattr(base_mod.os.path, "exists", lambda p: False)
        assert inst._get_python_major_version("1.0") is None

    def test_returns_none_on_garbage_output(self, monkeypatch):
        inst = _FakeSetup()
        monkeypatch.setattr(inst, "get_python_path", lambda v: "/py/python.exe")
        monkeypatch.setattr(base_mod.os.path, "exists", lambda p: True)
        monkeypatch.setattr(base_mod.subprocess, "Popen", _make_popen("not-a-number\n"))
        assert inst._get_python_major_version("1.0") is None

    def test_returns_none_on_popen_exception(self, monkeypatch):
        inst = _FakeSetup()
        monkeypatch.setattr(inst, "get_python_path", lambda v: "/py/python.exe")
        monkeypatch.setattr(base_mod.os.path, "exists", lambda p: True)

        def _boom(*a, **k):
            raise OSError("no interpreter")

        monkeypatch.setattr(base_mod.subprocess, "Popen", _boom)
        assert inst._get_python_major_version("1.0") is None
