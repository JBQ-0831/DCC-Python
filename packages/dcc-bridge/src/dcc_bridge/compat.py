# -*- coding: utf-8 -*-
"""py2 / py3 跨版本兼容辅助。

集中放置“stdout/stderr 自适应转码包装”，供 start_server 启动时打补丁、
以及 server 请求处理时的输出捕获流共用，避免重复实现、保证行为一致。

本模块会被 DCC 进程内的 Python 直接 import（py2.7 环境），因此严格使用
兼容语法：不使用 f-string、变量/签名注解、无参 super 等 py3-only 写法。
"""

import sys


def _decode_py2_bytes(s):
    """py2 下把 str(bytes) 尽量还原为 unicode，按 utf-8 -> gbk -> latin-1 顺序尝试，
    最终以 replace 兜底，保证任何字节流都能写出、绝不崩溃。"""
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return s.decode(enc)
        except UnicodeDecodeError:
            continue
    return s.decode("utf-8", "replace")


class _Py2UnicodeWriter(object):
    """py2 DCC（如 Max 2019）的 stdout 被宿主劫持为只收 unicode 的流，
    用户代码 print 含非 ASCII 字节的 str(bytes) 时直接 TypeError。

    本类在 write 时把 bytes 自动 decode 为 unicode 再写，彻底屏蔽该坑；
    py3 下 bytes 分支不触发，原样透传，零副作用。
    """

    def __init__(self, stream):
        self._stream = stream

    def write(self, s):
        if sys.version_info[0] == 2 and isinstance(s, bytes):
            s = _decode_py2_bytes(s)
        self._stream.write(s)

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)
