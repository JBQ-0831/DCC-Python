#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DCC Python CLI

用于向 VS Code 中的 DCC Python 扩展发起 socket 请求，在 DCC 中执行 Python
文件或代码字符串，并返回结构化结果。

用法示例：
    dcc-run file e:/vscode-maya-python/test/test_max.py
    dcc-run code "print('hello')"
    dcc-run ping
    echo "print(1+1)" | dcc-run stdin
"""
import argparse
import json
import os
import socket
import struct
import sys


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7005
DEFAULT_TIMEOUT = 30
RETRY_COUNT = 1


def get_config(args):
    """按优先级合并配置：命令行参数 > 环境变量 > 默认值"""
    host = args.host or os.environ.get("DCC_PYTHON_HOST") or DEFAULT_HOST
    port = args.port or int(os.environ.get("DCC_PYTHON_PORT", DEFAULT_PORT))
    timeout = args.timeout or int(os.environ.get("DCC_PYTHON_TIMEOUT", DEFAULT_TIMEOUT))
    return host, port, timeout


def send_request(host, port, timeout, request, retries=RETRY_COUNT):
    """通过长度前缀 + JSON 协议发送请求并返回响应"""
    data = json.dumps(request, ensure_ascii=False).encode("utf-8")
    message = struct.pack(">I", len(data)) + data

    last_error = None
    for attempt in range(retries + 1):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.sendall(message)

            # 读取响应
            buffer = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                if len(buffer) >= 4:
                    length = struct.unpack(">I", buffer[:4])[0]
                    if len(buffer) >= 4 + length:
                        response_data = buffer[4:4 + length]
                        return json.loads(response_data.decode("utf-8"))

            return _make_error("No response from server")
        except socket.timeout:
            last_error = "Connection timeout"
        except ConnectionRefusedError:
            last_error = "Connection refused, is VS Code server enabled and DCC connected?"
        except Exception as e:
            last_error = str(e)
        finally:
            if sock:
                sock.close()

    return _make_error(last_error)


def _make_error(message):
    return {
        "id": "unknown",
        "error": {"message": message}
    }


def parse_response(response):
    """把服务端响应转换为统一的结果字典"""
    if response.get("error"):
        return {
            "success": False,
            "output": [],
            "error": response["error"].get("message", "Unknown error"),
            "traceback": response["error"].get("traceback")
        }

    result = response.get("result", {})
    return {
        "success": result.get("success", False),
        "output": result.get("output", []),
        "error": None,
        "traceback": None
    }


def print_result(result, plain=False):
    """输出执行结果"""
    if plain:
        if result["output"]:
            print("\n".join(result["output"]))
        if result["error"]:
            print("ERROR: {}".format(result["error"]), file=sys.stderr)
            if result["traceback"]:
                print(result["traceback"], file=sys.stderr)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def get_exit_code(result):
    """根据结果返回进程退出码"""
    if result["success"]:
        return 0
    return 2 if result["error"] else 1


def cmd_file(args):
    """执行本地 Python 文件"""
    host, port, timeout = get_config(args)
    file_path = os.path.abspath(args.path)

    if not os.path.exists(file_path):
        result = {
            "success": False,
            "output": [],
            "error": "File not found: {}".format(file_path),
            "traceback": None
        }
        print_result(result, args.plain)
        return 3

    request = {
        "id": "file",
        "method": "execute_file",
        "params": {"file_path": file_path}
    }
    response = send_request(host, port, timeout, request)
    result = parse_response(response)
    print_result(result, args.plain)
    return get_exit_code(result)


def cmd_code(args):
    """执行代码字符串"""
    host, port, timeout = get_config(args)

    request = {
        "id": "code",
        "method": "execute_code",
        "params": {
            "source": args.source,
            "exec_origin": args.origin or "<dcc-run>"
        }
    }
    response = send_request(host, port, timeout, request)
    result = parse_response(response)
    print_result(result, args.plain)
    return get_exit_code(result)


def cmd_stdin(args):
    """从标准输入读取代码并执行"""
    source = sys.stdin.read()
    args.source = source
    args.origin = args.origin or "<dcc-run-stdin>"
    return cmd_code(args)


def cmd_ping(args):
    """测试 VS Code 服务端是否可达"""
    host, port, timeout = get_config(args)

    request = {
        "id": "ping",
        "method": "execute_code",
        "params": {
            "source": "pass",
            "exec_origin": "<dcc-run-ping>"
        }
    }
    response = send_request(host, port, timeout, request)
    result = parse_response(response)

    if result["success"]:
        print("DCC Python server is reachable at {}:{}".format(host, port))
        return 0
    else:
        print("Failed to reach DCC Python server: {}".format(result["error"]), file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="DCC Python CLI: send Python files or code snippets to DCC via VS Code socket server."
    )
    parser.add_argument(
        "--host",
        help="VS Code socket server host (default: 127.0.0.1, env: DCC_PYTHON_HOST)"
    )
    parser.add_argument(
        "--port",
        type=int,
        help="VS Code socket server port (default: 7005, env: DCC_PYTHON_PORT)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Socket timeout in seconds (default: 30, env: DCC_PYTHON_TIMEOUT)"
    )
    parser.add_argument(
        "--origin",
        help="Optional exec_origin for execute_code"
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Print plain output instead of JSON"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    file_parser = subparsers.add_parser("file", help="Execute a Python file")
    file_parser.add_argument("path", help="Path to the Python file")

    code_parser = subparsers.add_parser("code", help="Execute a Python code string")
    code_parser.add_argument("source", help="Python source code")

    stdin_parser = subparsers.add_parser("stdin", help="Execute Python code from stdin")

    ping_parser = subparsers.add_parser("ping", help="Check if the VS Code server is reachable")

    args = parser.parse_args()

    commands = {
        "file": cmd_file,
        "code": cmd_code,
        "stdin": cmd_stdin,
        "ping": cmd_ping,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
