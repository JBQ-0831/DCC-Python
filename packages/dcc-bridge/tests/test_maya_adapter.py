# -*- coding: utf-8 -*-
"""
MayaAdapter 单元测试

重点覆盖 get_version 的异常路径：cmds.about() 在 Maya 早期初始化阶段会抛
异常（如 userSetup.py 阶段），应回退到父类兜底值 "Unknown"，且通过 logger.error
把真实异常暴露出来，不再静默吞掉。
"""

import sys
import types

import pytest

from dcc_bridge.adapters.maya_adapter import MayaAdapter


class _FakeCmds(object):
    """模拟 maya.cmds，about() 故意抛异常，复现早期初始化阶段的错误"""

    def about(self, **kwargs):
        raise RuntimeError("Maya kernel not ready yet")


@pytest.fixture
def fake_maya(monkeypatch):
    """注入伪造的 maya 包与 maya.cmds 子模块，使 `import maya.cmds` 成功且
    cmds.about() 故意抛异常，复现 Maya 早期初始化阶段的错误

    关键点：真实 Maya 里 `maya` 是个包（有 __path__），`maya.cmds` 是子模块。
    必须把 `maya.cmds` 也注册进 sys.modules，否则 `import maya.cmds` 在伪造环境里
    会因找不到子模块而 ImportError，测不出 about() 抛异常的回退路径。
    """
    fake = types.ModuleType("maya")
    fake.__path__ = []  # 标记为包，允许 import maya.cmds 命中子模块
    fake_cmds = _FakeCmds()
    monkeypatch.setitem(sys.modules, "maya", fake)
    monkeypatch.setitem(sys.modules, "maya.cmds", fake_cmds)
    return fake


def test_get_version_falls_back_to_unknown(fake_maya):
    """about 抛异常时应回退到父类兜底值 'Unknown'"""
    adapter = MayaAdapter()
    assert adapter.get_version() == "Unknown"


def test_get_version_logs_real_error(fake_maya, capsys):
    """about 抛异常时必须在日志中输出真实 traceback，便于排查"""
    adapter = MayaAdapter()
    adapter.get_version()
    out = capsys.readouterr().out
    assert "[ERROR]" in out
    assert "Maya kernel not ready yet" in out
