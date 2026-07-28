"""
通用 TCP 客户端，用于 CLI 和外部工具直连 DCC 服务。
"""

from __future__ import annotations

import socket
import uuid
from typing import Any

from .protocol import Request, Response, decode_message, encode_message


class DCCClientError(Exception):
    """客户端错误"""


class DCCClient:
    """
    通用 DCC TCP 客户端

    通过长度前缀 + JSON 协议与 DCC 端服务通信。
    """

    def __init__(
        self, host: str = "127.0.0.1", port: int = 7002, timeout: float = 30.0
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None

    def connect(self) -> None:
        """建立到 DCC 服务的连接"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
        except OSError as e:
            raise DCCClientError(
                f"Failed to connect to DCC at {self.host}:{self.port}: {e}"
            ) from e

    def disconnect(self) -> None:
        """断开连接"""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            finally:
                self._socket = None

    def __enter__(self) -> DCCClient:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def _send_request(self, method: str, params: dict[str, Any]) -> Response:
        """发送请求并等待响应"""
        if not self._socket:
            raise DCCClientError("Not connected to DCC service")

        request = Request(id=str(uuid.uuid4()), method=method, params=params)
        try:
            self._socket.sendall(encode_message(request))
        except OSError as e:
            raise DCCClientError(f"Failed to send request: {e}") from e

        buffer = b""
        while True:
            try:
                data = self._socket.recv(4096)
            except socket.timeout:
                raise DCCClientError("Timeout waiting for response")
            except OSError as e:
                raise DCCClientError(f"Error receiving response: {e}") from e

            if not data:
                raise DCCClientError("Connection closed before response received")

            buffer += data
            response = decode_message(buffer)
            if response is not None:
                return response

    def execute_file(
        self,
        file_path: str,
        exec_origin: str | None = None,
        name_var: str = "__main__",
    ) -> Response:
        """请求 DCC 执行本地文件"""
        exec_origin = exec_origin or file_path
        return self._send_request(
            "execute",
            {
                "exec_file": file_path,
                "exec_origin": exec_origin,
                "name_var": name_var,
                "is_debugging": False,
            },
        )

    def execute_code(self, source: str, exec_origin: str = "<dcc>") -> Response:
        """请求 DCC 执行代码字符串"""
        return self._send_request(
            "execute",
            {
                "exec_file": None,
                "exec_origin": exec_origin,
                "name_var": "__main__",
                "is_debugging": False,
                "source": source,
            },
        )

    def reload_modules(self, workspace_folders: list[str]) -> Response:
        """请求 DCC 重载工作区模块"""
        return self._send_request(
            "reload",
            {
                "workspace_folders": workspace_folders,
            },
        )

    def start_debugpy(self, port: int, python_path: str | None = None) -> Response:
        """请求 DCC 启动 debugpy 服务"""
        params: dict[str, Any] = {"port": port}
        if python_path:
            params["python_path"] = python_path
        return self._send_request("start_debugpy", params)

    def install_debugpy(
        self, python_path: str | None = None, pip_index_url: str = ""
    ) -> Response:
        """请求 DCC 安装 debugpy"""
        params: dict[str, Any] = {"pip_index_url": pip_index_url}
        if python_path:
            params["python_path"] = python_path
        return self._send_request("install_debugpy", params)

    def ping(self) -> dict[str, Any]:
        """简单 ping，返回服务端基础信息"""
        response = self._send_request("ping", {})
        if response.error:
            raise DCCClientError(response.error.get("message", "Unknown error"))
        return response.result or {}


def resolve_client(
    dcc_name: str | None = None,
    port: int | None = None,
    version: str | None = None,
    host: str = "127.0.0.1",
    timeout: float = 30.0,
) -> DCCClient:
    """
    根据 dcc_name / port / version 自动解析目标并创建 DCCClient。

    当同时运行同类型多个版本时（如 Maya 2022 与 Maya 2024），
    可通过 --version 参数按版本过滤，无需指定具体端口。

    Args:
        dcc_name: DCC 类型，如 'maya'、'3dsmax'
        port: 直接指定端口
        version: DCC 版本过滤，如 '2022'、'2024'
        host: 主机地址
        timeout: 超时时间

    Returns:
        配置好的 DCCClient

    Raises:
        DCCClientError: 无法解析目标时抛出
    """
    from . import discovery

    if port is not None:
        return DCCClient(host=host, port=port, timeout=timeout)

    instances = discovery.list_instances()
    if dcc_name:
        instances = [i for i in instances if i.get("dcc_name") == dcc_name]
    if version:
        instances = [i for i in instances if i.get("dcc_version") == version]

    if not instances:
        msg = "No running DCC instance found"
        if dcc_name:
            msg += f" for type '{dcc_name}'"
        if version:
            msg += f" version '{version}'"
        msg += ". Please start the DCC and ensure the bridge server is running."
        raise DCCClientError(msg)

    if len(instances) > 1:
        raise DCCClientError(
            "Multiple DCC instances found: "
            + ", ".join(
                f"{i.get('dcc_name')}:{i.get('dcc_version', '?')}:{i.get('port')}"
                for i in instances
            )
            + ". Please specify --port, --dcc-name, or --version."
        )

    info = instances[0]
    return DCCClient(
        host=info.get("host", host),
        port=info.get("port", 7002),
        timeout=timeout,
    )
