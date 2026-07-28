"""
通信协议模块
定义请求/响应格式，实现长度前缀编码/解码和 JSON 序列化/反序列化

协议格式: [4字节长度][JSON payload]
长度前缀使用大端序（big-endian）
"""

from __future__ import annotations

import json
import struct
from typing import Any


class Request:
    """请求对象"""

    def __init__(self, id: str, method: str, params: dict[str, Any] | None = None):
        self.id = id
        self.method = method
        self.params = params or {}

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "method": self.method, "params": self.params}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Request:
        return cls(id=data["id"], method=data["method"], params=data.get("params", {}))


class Response:
    """响应对象"""

    def __init__(
        self,
        id: str,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ):
        self.id = id
        self.result = result
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "result": self.result, "error": self.error}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Response:
        return cls(id=data["id"], result=data.get("result"), error=data.get("error"))

    @classmethod
    def success(cls, id: str, output: list | None = None, **kwargs) -> Response:
        result = {"success": True}
        if output:
            result["output"] = output
        result.update(kwargs)
        return cls(id=id, result=result)

    @classmethod
    def failure(cls, id: str, message: str, traceback: str | None = None) -> Response:
        error = {"message": message}
        if traceback:
            error["traceback"] = traceback
        return cls(id=id, error=error)


def encode_message(data: dict[str, Any] | Request | Response) -> bytes:
    """
    将数据编码为协议格式的字节串

    Args:
        data: 要编码的数据，可以是字典、Request 或 Response 对象

    Returns:
        编码后的字节串：[4字节长度][JSON payload]
    """
    if isinstance(data, (Request, Response)):
        data = data.to_dict()

    json_str = json.dumps(data, ensure_ascii=False)
    json_bytes = json_str.encode("utf-8")

    length = len(json_bytes)
    length_bytes = struct.pack(">I", length)

    return length_bytes + json_bytes


def decode_message(data: bytes) -> Request | Response | None:
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
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if "method" in data_dict:
        return Request.from_dict(data_dict)
    else:
        return Response.from_dict(data_dict)


def decode_raw(data: bytes) -> dict[str, Any] | None:
    """
    从字节串解码出原始字典

    Args:
        data: 包含长度前缀和 JSON 的字节串

    Returns:
        解码后的字典，如果数据不完整或格式错误返回 None
    """
    if len(data) < 4:
        return None

    length = struct.unpack(">I", data[:4])[0]

    if len(data) < 4 + length:
        return None

    json_bytes = data[4 : 4 + length]

    try:
        json_str = json_bytes.decode("utf-8")
        return json.loads(json_str)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
