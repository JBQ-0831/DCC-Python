"""VS Code 内部 socket 服务端测试客户端

用法：
    1. 在 VS Code 设置中启用 dcc-python.vscodeServer.enabled
    2. 重启 VS Code 扩展（Reload Window）
    3. 在 DCC 中启动 start.py 服务端
    4. 执行文件：python vscode_server_client.py file <file_path>
    5. 执行代码字符串：python vscode_server_client.py code "print('hello')"
"""
import socket
import struct
import json
import sys


HOST = "127.0.0.1"
PORT = 7005


def send_request(request):
    data = json.dumps(request).encode("utf-8")
    message = struct.pack(">I", len(data)) + data

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
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
                response = json.loads(response_data.decode("utf-8"))
                print(json.dumps(response, ensure_ascii=False, indent=2))
                break

    sock.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python vscode_server_client.py file <file_path>")
        print("  python vscode_server_client.py code <python_code>")
        sys.exit(1)

    mode = sys.argv[1]
    value = sys.argv[2]

    if mode == "file":
        request = {
            "id": "1",
            "method": "execute_file",
            "params": {"file_path": value}
        }
    elif mode == "code":
        request = {
            "id": "1",
            "method": "execute_code",
            "params": {
                "source": value,
                "exec_origin": "<vscode-server>"
            }
        }
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)

    send_request(request)
