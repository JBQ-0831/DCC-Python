# -*- coding: utf-8 -*-
"""修复 py2 DCC（Max 2019 等）stdout/stderr 只收 unicode，导致用户代码 print
含非 ASCII 字节时崩溃的问题：server 启动前将流替换为自适应转码包装流。"""
import sys

from dcc_bridge.start import _Py2UnicodeWriter, _patch_std_streams_for_py2


class _UnicodeOnlyStream(object):
    """模拟 Max 2019 的 stdout：只收 unicode，收到 bytes(str) 抛 TypeError。"""

    def __init__(self):
        self.written = []

    def write(self, s):
        if isinstance(s, bytes):
            raise TypeError("unicode argument expected, got 'str'")
        self.written.append(s)

    def flush(self):
        pass


def test_py2_writer_decodes_utf8_bytes(monkeypatch):
    # 模拟 py2 运行时：version_info 主版本为 2
    monkeypatch.setattr(sys, "version_info", (2, 7, 18, "final", 0))
    fake = _UnicodeOnlyStream()
    w = _Py2UnicodeWriter(fake)
    w.write(u"hello ".encode("utf-8") + u"中文".encode("utf-8"))
    assert len(fake.written) == 1
    assert fake.written[0] == u"hello 中文"


def test_py2_writer_gbk_fallback(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (2, 7, 18, "final", 0))
    gbk_bytes = u"中文".encode("gbk")
    fake = _UnicodeOnlyStream()
    w = _Py2UnicodeWriter(fake)
    w.write(gbk_bytes)
    assert fake.written[0] == u"中文"


def test_py2_writer_passes_through_unicode(monkeypatch):
    # py3 的 str 在 wrapper 中视为已解码内容，直接转发，不崩
    monkeypatch.setattr(sys, "version_info", (2, 7, 18, "final", 0))
    fake = _UnicodeOnlyStream()
    w = _Py2UnicodeWriter(fake)
    w.write(u"already unicode")
    assert fake.written[0] == u"already unicode"


def test_py2_writer_forwards_unknown_attrs(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (2, 7, 18, "final", 0))
    fake = _UnicodeOnlyStream()
    fake.custom_attr = 42
    w = _Py2UnicodeWriter(fake)
    assert w.custom_attr == 42
    w.flush()


def test_patch_noop_on_py3():
    # py3 下不应替换 sys.stdout
    original = sys.stdout
    _patch_std_streams_for_py2()
    assert sys.stdout is original
