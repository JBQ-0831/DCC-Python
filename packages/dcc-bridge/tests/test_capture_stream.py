# -*- coding: utf-8 -*-
"""
验证 server._process_request 的请求捕获流设置：sys.stdout 必须包一层
_Py2UnicodeWriter，否则 py2 DCC（如 Max 2019）里用户代码 print 非 ASCII 字节
会直接落进 io.StringIO（py2 文本流只收 unicode）而 TypeError。

本测试固化该修复点：server 的捕获流 = _Py2UnicodeWriter(io.StringIO())。
"""

import io
import sys

from dcc_bridge.compat import _Py2UnicodeWriter


def test_capture_stream_accepts_py2_bytes(monkeypatch):
    # 复现 py2 宿主：_Py2UnicodeWriter 仅在 py2 分支处理 bytes
    monkeypatch.setattr(sys, "version_info", (2, 7, 18))

    captured = io.StringIO()
    wrapped = _Py2UnicodeWriter(captured)

    # 模拟 py2 下 print 节点对象写出 gbk 编码字节（例：“测试”）
    wrapped.write(b"\xb2\xe2\xca\xd4")

    out = captured.getvalue()
    assert "测试" in out  # 已自动 decode 为 unicode 写入，未被 io.StringIO 拒绝


def test_capture_stream_transparent_in_py3():
    # py3 下无处理分支，str 原样写入、不崩
    captured = io.StringIO()
    wrapped = _Py2UnicodeWriter(captured)
    wrapped.write("测试")
    assert "测试" in captured.getvalue()
