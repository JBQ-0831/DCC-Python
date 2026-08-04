# -*- coding: utf-8 -*-
"""
通用 TCP 客户端，用于 CLI 和外部工具直连 DCC 服务。

兼容 Python 2.7 / 3.x：不使用 f-string、PEP 604 联合类型、内置泛型注解、
无参 super()、异常链（raise ... from e）、OSError（改用 socket.error）等
py3-only 语法。
"""

import socket
import uuid

from .protocol import Request, Response, decode_message, encode_message


class DCCClientError(Exception):
    """客户端错误"""


class DCCClient(object):
    """
    通用 DCC TCP 客户端

    显式继承 object：Python 2 下必须是 new-style class，否则 super()/多重继承在 py2 下报错。
    Python 3 下 (object) 冗余但无害。

    通过长度前缀 + JSON 协议与 DCC 端服务通信。
    """

    def __init__(self, host="127.0.0.1", port=7002, timeout=30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket = None

    def connect(self):
        """建立到 DCC 服务的连接"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
        except socket.error as e:
            raise DCCClientError(
                "Failed to connect to DCC at "
                + str(self.host)
                + ":"
                + str(self.port)
                + ": "
                + str(e)
            )

    def disconnect(self):
        """断开连接"""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            finally:
                self._socket = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def _send_request(self, method, params):
        """发送请求并等待响应"""
        if not self._socket:
            raise DCCClientError("Not connected to DCC service")

        request = Request(id=str(uuid.uuid4()), method=method, params=params)
        try:
            self._socket.sendall(encode_message(request))
        except socket.error as e:
            raise DCCClientError("Failed to send request: " + str(e))

        buffer = b""
        while True:
            try:
                data = self._socket.recv(4096)
            except socket.timeout:
                raise DCCClientError("Timeout waiting for response")
            except socket.error as e:
                raise DCCClientError("Error receiving response: " + str(e))

            if not data:
                raise DCCClientError("Connection closed before response received")

            buffer += data
            response = decode_message(buffer)
            if response is not None:
                return response

    def execute_file(self, file_path, exec_origin=None, name_var="__main__"):
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

    def execute_code(self, source, exec_origin="<dcc>"):
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

    def reload_modules(self, workspace_folders):
        """请求 DCC 重载工作区模块"""
        return self._send_request(
            "reload",
            {
                "workspace_folders": workspace_folders,
            },
        )

    def start_debugpy(self, port, python_path=None):
        """请求 DCC 启动 debugpy 服务"""
        params = {"port": port}
        if python_path:
            params["python_path"] = python_path
        return self._send_request("start_debugpy", params)

    def install_debugpy(self, python_path=None, pip_index_url=""):
        """请求 DCC 安装 debugpy"""
        params = {"pip_index_url": pip_index_url}
        if python_path:
            params["python_path"] = python_path
        return self._send_request("install_debugpy", params)

    def ping(self):
        """简单 ping，返回服务端基础信息（含 python_version）"""
        response = self._send_request("ping", {})
        if response.error:
            raise DCCClientError(response.error.get("message", "Unknown error"))
        return response.result or {}


def resolve_client(
    dcc_name=None,
    port=None,
    version=None,
    host="127.0.0.1",
    timeout=30.0,
):
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
            msg += " for type '" + str(dcc_name) + "'"
        if version:
            msg += " version '" + str(version) + "'"
        msg += ". Please start the DCC and ensure the bridge server is running."
        raise DCCClientError(msg)

    if len(instances) > 1:
        raise DCCClientError(
            "Multiple DCC instances found: "
            + ", ".join(
                "{dcc}:{ver}:{port}".format(
                    dcc=i.get("dcc_name"),
                    ver=i.get("dcc_version", "?"),
                    port=i.get("port"),
                )
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
