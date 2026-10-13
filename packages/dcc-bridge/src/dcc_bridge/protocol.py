# -*- coding: utf-8 -*-
"""
通信协议模块
定义请求/响应格式，实现长度前缀编码/解码和 JSON 序列化/反序列化

协议格式: [4字节长度][JSON payload]
长度前缀使用大端序（big-endian）

兼容 Python 2.7 / 3.x：不使用 f-string、PEP 604 联合类型（X | Y）、
内置泛型注解（dict[str, ...]）等 py3-only 语法。
"""

import json
import struct

from .compat import _decode_py2_bytes


class Request(object):
    """请求对象

    显式继承 object：Python 2 下必须是 new-style class（经典类会导致 super()/多重继承在 py2 下报错）。
    Python 3 下 (object) 冗余但无害。
    """

    def __init__(self, id, method, params=None):
        self.id = id
        self.method = method
        self.params = params or {}

    def to_dict(self):
        return {"id": self.id, "method": self.method, "params": self.params}

    @classmethod
    def from_dict(cls, data):
        return cls(id=data["id"], method=data["method"], params=data.get("params", {}))


class Response(object):
    """响应对象

    显式继承 object：Python 2 下必须是 new-style class（经典类会导致 super()/多重继承在 py2 下报错）。
    Python 3 下 (object) 冗余但无害。
    """

    def __init__(self, id, result=None, error=None):
        self.id = id
        self.result = result
        self.error = error

    def to_dict(self):
        return {"id": self.id, "result": self.result, "error": self.error}

    @classmethod
    def from_dict(cls, data):
        return cls(id=data["id"], result=data.get("result"), error=data.get("error"))

    @classmethod
    def success(cls, id, output=None, **kwargs):
        result = {"success": True}
        if output:
            result["output"] = output
        result.update(kwargs)
        return cls(id=id, result=result)

    @classmethod
    def failure(cls, id, message, traceback=None):
        error = {"message": message}
        if traceback:
            error["traceback"] = traceback
        return cls(id=id, error=error)


def _to_bytes(s):
    """把 JSON 字符串统一转成 bytes，兼容 py2（str 即 bytes）与 py3。"""
    if isinstance(s, bytes):
        return s
    return s.encode("utf-8")


def _ensure_unicode(obj):
    """递归把 py2 的 str(bytes) 归一为 unicode，确保 json.dumps(ensure_ascii=False)
    在 py2 下不会因为遇到含非 ASCII 字节的 str 而用 ASCII 解码崩溃。

    根因：py2 的 json C 编码器假设输入是 unicode，一旦值是 str(字节)且含非 ASCII，
    会在内部用默认 ASCII 编码去解码这段字节，抛出 UnicodeDecodeError，导致整个响应
    发不出去、真实错误(如含中文源码的 SyntaxError traceback)被彻底掩盖。

    py3 下 str 即 unicode、仅 bytes 走解码，行为一致且安全；本函数在两个版本都无所谓
    副作用。复用 compat._decode_py2_bytes 的 utf-8 -> gbk -> latin-1 -> replace 兜底。
    """
    if isinstance(obj, bytes):
        return _decode_py2_bytes(obj)
    if isinstance(obj, dict):
        return {_ensure_unicode(k): _ensure_unicode(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_ensure_unicode(v) for v in obj]
    return obj


def encode_message(data):
    """
    将数据编码为协议格式的字节串

    Args:
        data: 要编码的数据，可以是字典、Request 或 Response 对象

    Returns:
        编码后的字节串：[4字节长度][JSON payload]
    """
    if isinstance(data, (Request, Response)):
        payload = data.to_dict()
    else:
        payload = data

    # 归一化：py2 下 payload 里的 str(字节)值(如 traceback.format_exc() 返回的
    # 含中文源码的字节串)会让 json.dumps(ensure_ascii=False) 用 ASCII 解码崩溃，
    # 进而掩盖真实错误。先递归转成 unicode，保证任何字符串值都能安全序列化。
    payload = _ensure_unicode(payload)

    # ensure_ascii=False 让中文等直接以 UTF-8 多字节输出；py2 下 json.dumps
    # 返回 str(bytes)，py3 下返回 str(unicode)，统一由 _to_bytes 归一为 bytes。
    json_str = json.dumps(payload, ensure_ascii=False)
    json_bytes = _to_bytes(json_str)

    length = len(json_bytes)
    length_bytes = struct.pack(">I", length)

    return length_bytes + json_bytes


def decode_message(data):
    """
    从字节串解码出请求或响应对象

    Args:
        data: 包含长度前缀和 JSON 的字节串

    Returns:
        Request 或 Response 对象，如果数据不完整返回 None
    """
    if len(data) < 4:
        return None

    length = struct.unpack(">I", data[:4])[0]

    if len(data) < 4 + length:
        return None

    json_bytes = data[4 : 4 + length]

    try:
        json_str = json_bytes.decode("utf-8")
        data_dict = json.loads(json_str)
    except (UnicodeDecodeError, ValueError):
        # py2 中 JSONDecodeError 不存在，json.loads 失败抛 ValueError
        return None

    if "method" in data_dict:
        return Request.from_dict(data_dict)
    else:
        return Response.from_dict(data_dict)


def decode_raw(data):
    """
    从字节串解码出原始字典

    Args:
        data: 包含长度前缀和 JSON 的字节串

    Returns:
        解码后的字典，如果数据不完整或格式错误返回 None
    """
    if len(data) < 4:
        return None

    # 兼容 py2/py3：调用方可能传入 str（py2 即 bytes）或 bytes（py3）。
    if not isinstance(data, bytes):
        data = _to_bytes(data)

    length = struct.unpack(">I", data[:4])[0]

    if len(data) < 4 + length:
        return None

    json_bytes = data[4 : 4 + length]

    try:
        json_str = json_bytes.decode("utf-8")
        return json.loads(json_str)
    except (UnicodeDecodeError, ValueError):
        return None
