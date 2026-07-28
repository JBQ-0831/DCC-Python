"""
通用 TCP 服务端模块

基于 threading.Thread 实现，提供后台监听服务，在收到请求时执行 Python 代码。
与具体 DCC 框架（Qt 等）无关：主线程/目标线程的派发由各 DCC 的
adapter.run_on_main_thread 决定（如 Blender 用 bpy.app.timers 派发到主线程）。
"""

from __future__ import annotations

import io
import socket
import struct
import sys
import threading
import traceback

from .protocol import Request, Response, decode_message, encode_message


class RequestHandler:
    """
    请求处理器

    收到请求后在目标上下文（由 adapter.run_on_main_thread 决定）中执行代码并返回结果。
    本身不依赖任何 GUI 框架。
    """

    def __init__(self, adapter):
        self.adapter = adapter
        self.logger = adapter.get_logger()

    def handle(self, conn, request_data: dict, done_event):
        try:
            request = Request.from_dict(request_data)
        except Exception as e:
            self.logger.error(f"Failed to parse request: {e}")
            try:
                response = Response.failure(id="unknown", message=f"Invalid request: {e}")
                conn.send(encode_message(response))
            except Exception:
                pass
            finally:
                done_event.set()
            return

        try:
            response = self._process_request(request)
        except Exception as e:
            self.logger.error(f"Error processing request: {e}")
            self.logger.error(traceback.format_exc())
            response = Response.failure(
                id=request.id, message=str(e), traceback=traceback.format_exc()
            )

        try:
            conn.send(encode_message(response))
        except Exception as e:
            self.logger.error(f"Failed to send response: {e}")
        finally:
            done_event.set()

    def _process_request(self, request: Request) -> Response:
        method = request.method
        params = request.params

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured = io.StringIO()
        sys.stdout = captured
        sys.stderr = captured

        try:
            if method == "execute":
                exec_file = params.get("exec_file")
                exec_origin = params.get("exec_origin", "")
                name_var = params.get("name_var", "__main__")
                is_debugging = params.get("is_debugging", False)
                source = params.get("source")

                # 调试模式下恢复真实 stdout/stderr，让 debugpy 捕获 print 输出
                # 并发送到 VS Code 的调试控制台（DEBUG CONSOLE）
                if is_debugging:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

                from .execute import execute_code, main

                if source is not None:
                    # CLI / 外部工具直接发送代码字符串
                    execute_code(source, exec_origin or "<dcc>", is_debugging)
                else:
                    main(
                        exec_file=exec_file,
                        exec_origin=exec_origin,
                        name_var=name_var,
                        is_debugging=is_debugging,
                    )

            elif method == "reload":
                workspace_folders = params.get("workspace_folders", [])
                from .reload import reload as _reload

                _reload(workspace_folders)

            elif method == "start_debugpy":
                # 临时恢复 stdout/stderr，让所有日志和 debugpy 的调试信息能实时输出
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                try:
                    port = params.get("port", 7012)
                    python_path = params.get("python_path") or self.adapter.get_python_path()
                    self.logger.info(
                        f"[DEBUG] Handling start_debugpy: port={port}, python_path={python_path}"
                    )
                    try:
                        from .debug import start_debugpy_server

                        self.logger.info("[DEBUG] import start_debugpy_server succeeded")
                    except Exception as import_err:
                        self.logger.error(
                            f"[ERROR] Failed to import start_debugpy_server: {import_err}"
                        )
                        self.logger.error(traceback.format_exc())
                        raise
                    result = start_debugpy_server(port, python_path, self.adapter)
                    self.logger.info(f"[DEBUG] start_debugpy_server returned: {result}")

                    debug_logs = [
                        f"[DEBUG] Handling start_debugpy: port={port}, python_path={python_path}",
                        f"[DEBUG] start_debugpy_server returned: {result}",
                    ]
                    return Response.success(id=request.id, output=debug_logs)
                finally:
                    # 恢复捕获状态
                    sys.stdout = captured
                    sys.stderr = captured

            elif method == "install_debugpy":
                # 不恢复 stdout/stderr，让 pip 安装日志通过 captured 返回给
                # VS Code 的 DCC Python 输出频道，而非直接输出到 DCC 控制台
                python_path = params.get("python_path") or self.adapter.get_python_path()
                pip_index_url = params.get("pip_index_url", "")
                self.logger.info(
                    f"[DEBUG] Handling install_debugpy: python_path={python_path}, "
                    f"pip_index_url={pip_index_url}"
                )
                from .debug import install_debugpy

                install_debugpy(python_path, pip_index_url)

            elif method == "eval_function":
                module_name = params.get("module")
                func_name = params.get("function")
                kwargs = params.get("kwargs", {})

                if not module_name or not func_name:
                    return Response.failure(
                        id=request.id, message="Missing module or function name"
                    )

                module = __import__(module_name, fromlist=[func_name])
                func = getattr(module, func_name)
                func(**kwargs)

            elif method == "add_sys_path":
                path = params.get("path", "")
                self.adapter.add_sys_path(path)

            elif method == "ping":
                # 健康检查，返回服务端基本信息
                return Response.success(
                    id=request.id,
                    output=["pong"],
                    dcc_name=self.adapter.name,
                    python_path=self.adapter.get_python_path(),
                )

            else:
                return Response.failure(id=request.id, message=f"Unknown method: {method}")

            output = captured.getvalue().strip()
            output_lines = output.split("\n") if output else []

            return Response.success(id=request.id, output=output_lines)

        except Exception as e:
            error_detail = traceback.format_exc()
            self.logger.error(f"Execution failed: {e}")
            self.logger.error(f"Error detail: {error_detail}")
            return Response.failure(
                id=request.id, message=str(e), traceback=error_detail
            )

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


class SocketServerThread(threading.Thread):
    """
    后台 Socket 服务线程

    监听指定端口，接收客户端连接，解析请求并通过 adapter.run_on_main_thread
    将处理派发到目标上下文（主线程或后台线程，取决于 DCC），不依赖任何 GUI 框架。
    """

    def __init__(self, adapter, port: int = 7002, host: str = "127.0.0.1"):
        super().__init__(daemon=True)
        self.adapter = adapter
        self.logger = adapter.get_logger()
        self.port = port
        self.host = host

        self.server_socket = None
        self.running = True
        self.request_handler = RequestHandler(adapter)

    def run(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)

            self._log(f"Server started, listening on {self.host}:{self.port}")
            self._log("Waiting for connections...")

            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    # 每个客户端连接用独立后台线程处理，支持长连接多次请求
                    threading.Thread(
                        target=self._handle_client,
                        args=(conn, addr),
                        daemon=True,
                    ).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self._log(f"Error accepting connection: {e}")

        except Exception as e:
            self._log(f"Failed to start server: {e}")
        finally:
            self._cleanup()
            self._log("Server stopped")

    def _handle_client(self, conn, addr):
        try:
            # 长连接模式：较长超时，支持多次请求
            conn.settimeout(300.0)
            buffer = b""
            self._log(f"Client {addr} connected (persistent mode)")

            while self.running:
                try:
                    data = conn.recv(4096)
                    if not data:
                        # 客户端主动断开
                        break
                    buffer += data

                    # 尝试从缓冲区解析所有完整消息
                    while True:
                        if len(buffer) < 4:
                            break

                        length = struct.unpack(">I", buffer[:4])[0]
                        if len(buffer) < 4 + length:
                            break

                        message = decode_message(buffer)
                        consumed = 4 + length
                        buffer = buffer[consumed:]

                        if message is None:
                            self._log("Failed to decode message, skipping")
                            continue

                        if isinstance(message, Request):
                            # 等待目标上下文处理完成，但不关闭连接
                            done_event = threading.Event()
                            self.adapter.run_on_main_thread(
                                self.request_handler.handle,
                                conn,
                                message.to_dict(),
                                done_event,
                            )
                            done_event.wait(timeout=60.0)
                        else:
                            self._log("Received non-request message, ignoring")

                except socket.timeout:
                    # 长连接超时，检查是否仍在运行
                    continue
                except ConnectionResetError:
                    self._log(f"Client {addr} disconnected")
                    break
                except Exception as e:
                    self._log(f"Error handling client {addr}: {e}")
                    break
        except Exception as e:
            self._log(f"Error in client handler: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _cleanup(self):
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                self._log(f"Error closing server: {e}")
            finally:
                self.server_socket = None

        # 服务停止时不再主动注销发现文件：DCC 崩溃/强制结束时不可靠，
        # 由 CLI / 扩展在读取时通过惰性 PID 检查自动清理。

    def stop(self):
        self._log("Stopping server...")
        self.running = False
        # 关闭监听 socket 以唤醒 accept() 阻塞，使 run() 尽快退出
        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception:
            pass

    def is_running(self) -> bool:
        return self.running and self.is_alive()

    def _log(self, message: str):
        self.logger.info(message)
