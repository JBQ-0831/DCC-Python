# -*- coding: utf-8 -*-
"""adapters/base.py Logger 跨版本编码修复测试

py2 下 DCC 宿主（如 Max 2019）的 stdout 常为只收 unicode 的流，
普通 print(str) 会报 "unicode argument expected, got 'str'"。
Logger._emit 统一转 unicode 输出并用 try/except 兜底。
py2 行为靠真机复测，这里验证 py3 正常 + TypeError 兜底不崩。
"""
import sys

import pytest

from dcc_bridge.adapters.base_adapter import Logger


def test_logger_info_output(capsys):
    Logger.info("hello")
    assert "[INFO] DCC Bridge: hello" in capsys.readouterr().out


def test_logger_error_output(capsys):
    Logger.error("boom")
    assert "[ERROR] DCC Bridge: boom" in capsys.readouterr().out


def test_logger_warn_output(capsys):
    Logger.warn("careful")
    assert "[WARN] DCC Bridge: careful" in capsys.readouterr().out


def test_logger_falls_back_when_stdout_expects_bytes(monkeypatch):
    """模拟 stdout 只收 bytes（py2 cStringIO 场景）：write(unicode) 抛 TypeError
    时，_emit 应回退到 encode 后写 bytes，不崩溃。"""
    written = []

    class FakeStdout(object):
        def write(self, x):
            # py3 下 str 即 unicode；模拟"只收 bytes"的流收 str 时抛 TypeError
            if sys.version_info[0] == 3 and isinstance(x, str):
                raise TypeError("bytes expected")
            written.append(x)

    monkeypatch.setattr(sys, "stdout", FakeStdout())
    Logger.info("fallback")  # 不应抛异常
    assert len(written) == 1
    # 兜底分支写入的是 bytes（py2 cStringIO 场景），用 bytes 比较
    assert b"fallback" in written[0]
