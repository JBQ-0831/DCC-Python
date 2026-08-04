"""
server.py 单元测试

验证重构后的 server.py 完全不依赖 Qt：
- SocketServerThread 是 threading.Thread 子类
- 后台监听可正常接收请求并返回响应（以 ping 为例做端到端验证）
- 无 PySide 依赖（测试环境无 PySide 也能跑通，即证明去 Qt 成功）
"""

from __future__ import annotations

import socket
import struct
import threading

import pytest

from dcc_bridge.adapters.base_adapter import DCCAdapter
from dcc_bridge.protocol import Request, Response, decode_message, encode_message
from dcc_bridge.server import ThreadRequestHandler, SocketServerThread


class _NullLogger:
    channel = "Test"

    @classmethod
    def info(cls, message: str):
        pass

    @classmethod
    def warn(cls, message: str):
        pass

    @classmethod
    def error(cls, message: str):
        pass


class _FakeAdapter(DCCAdapter):
    """用于 server 测试的最小 adapter，不触发任何 GUI 依赖"""

    name = "testdcc"

    def get_logger(self):
        return _NullLogger

    def get_python_path(self) -> str:
        return "python"


def _find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return buf


def _send_request(port: int, request: Request) -> Response:
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        sock.sendall(encode_message(request))
        prefix = _recv_exact(sock, 4)
        length = struct.unpack(">I", prefix)[0]
        payload = _recv_exact(sock, length)
        # decode_message 期望包含 4 字节长度前缀的完整报文
        resp = decode_message(prefix + payload)
        assert isinstance(resp, Response)
        return resp
    finally:
        sock.close()


class TestServerIsQtFree:
    def test_socket_server_thread_is_threading_thread(self):
        assert issubclass(SocketServerThread, threading.Thread)

    def test_request_handler_not_qobject(self):
        # 重构后非 Qt 请求处理器不应继承 QObject（无 Signal / metaObject）
        handler = ThreadRequestHandler(_FakeAdapter())
        assert not hasattr(handler, "execute_request")
        assert not hasattr(handler, "metaObject")


class TestServerEndToEnd:
    def test_ping_returns_server_info(self):
        port = _find_free_port()
        server = SocketServerThread(adapter=_FakeAdapter(), port=port, host="127.0.0.1")
        server.start()
        try:
            resp = _send_request(port, Request(id="1", method="ping"))
        finally:
            server.stop()
            server.join(timeout=2)

        assert resp.result is not None
        assert resp.result.get("success") is True
        assert resp.result.get("dcc_name") == "testdcc"
        assert resp.result.get("python_path") == "python"
        assert resp.result.get("output") == ["pong"]
        # T3: ping 响应必须携带 python_version，供 VSCode 端(T8)做 debugpy 版本门控
        assert "python_version" in resp.result
        assert resp.result.get("python_version")

    def test_unknown_method_returns_failure(self):
        port = _find_free_port()
        server = SocketServerThread(adapter=_FakeAdapter(), port=port, host="127.0.0.1")
        server.start()
        try:
            resp = _send_request(port, Request(id="2", method="no_such_method"))
        finally:
            server.stop()
            server.join(timeout=2)

        assert resp.error is not None
        assert "Unknown method" in resp.error.get("message", "")

    def test_stop_makes_is_running_false(self):
        port = _find_free_port()
        server = SocketServerThread(adapter=_FakeAdapter(), port=port, host="127.0.0.1")
        server.start()
        assert server.is_running() is True
        server.stop()
        server.join(timeout=2)
        assert server.is_running() is False
