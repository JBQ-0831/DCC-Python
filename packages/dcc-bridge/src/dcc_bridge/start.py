"""
DCC TCP 服务端启动脚本

此脚本可在任意 DCC 软件（Maya、3ds Max、Substance Painter 等）中运行，
启动 TCP 服务端以接收外部发送的 Python 代码执行请求。

使用方法：
1. Maya：在脚本编辑器（Python 标签）中运行此脚本
2. 3ds Max：拖拽此脚本到视图，或在脚本监听器中运行
3. Substance Painter：在 Python 控制台中运行此脚本
4. 其他 DCC：在任意 Python 环境中运行此脚本

默认端口：7002
如需更改端口，修改下方的 DEFAULT_PORT 常量，或在调用 start_server() 时传入参数
"""

from __future__ import annotations

DEFAULT_PORT = 7002
DEFAULT_HOST = "127.0.0.1"


def detect_dcc() -> str:
    """自动检测当前运行的 DCC 软件

    Returns:
        DCC 名称：'maya', '3dsmax', 'substance_painter', 或 'generic'
    """
    # 检测 Maya
    try:
        import maya.cmds

        return "maya"
    except ImportError:
        pass

    # 检测 3ds Max
    try:
        import pymxs

        return "3dsmax"
    except ImportError:
        pass

    # 检测 Substance Painter
    try:
        import substance_painter

        return "substance_painter"
    except ImportError:
        pass

    # 检测 Substance Designer
    try:
        import sd

        return "substance_designer"
    except ImportError:
        pass

    # 检测 Houdini
    try:
        import hou

        return "houdini"
    except ImportError:
        pass

    # 检测 Blender
    try:
        import bpy

        return "blender"
    except ImportError:
        pass

    # 未检测到特定 DCC，使用通用适配器
    return "generic"


def get_adapter(dcc_name: str):
    """根据 DCC 名称获取对应的 Adapter

    Args:
        dcc_name: DCC 名称

    Returns:
        DCCAdapter 实例
    """
    from dcc_bridge.adapters.base import DCCAdapter

    if dcc_name == "maya":
        try:
            from dcc_bridge.adapters.maya import MayaAdapter

            return MayaAdapter()
        except ImportError:
            print("MayaAdapter not available, using generic adapter")
            return DCCAdapter()

    elif dcc_name == "3dsmax":
        try:
            from dcc_bridge.adapters.max import MaxAdapter

            return MaxAdapter()
        except ImportError:
            print("MaxAdapter not available, using generic adapter")
            return DCCAdapter()

    elif dcc_name == "substance_painter":
        try:
            from dcc_bridge.adapters.painter import SubstancePainterAdapter

            return SubstancePainterAdapter()
        except ImportError:
            print("SubstancePainterAdapter not available, using generic adapter")
            return DCCAdapter()

    elif dcc_name == "substance_designer":
        try:
            from dcc_bridge.adapters.designer import SubstanceDesignerAdapter

            return SubstanceDesignerAdapter()
        except ImportError:
            print("SubstanceDesignerAdapter not available, using generic adapter")
            return DCCAdapter()

    elif dcc_name == "houdini":
        try:
            from dcc_bridge.adapters.houdini import HoudiniAdapter

            return HoudiniAdapter()
        except ImportError:
            print("HoudiniAdapter not available, using generic adapter")
            return DCCAdapter()

    elif dcc_name == "blender":
        try:
            from dcc_bridge.adapters.blender import BlenderAdapter

            return BlenderAdapter()
        except ImportError:
            print("BlenderAdapter not available, using generic adapter")
            return DCCAdapter()

    else:
        # 通用适配器
        return DCCAdapter()


def _find_available_port(
    start_port: int, host: str = DEFAULT_HOST, max_tries: int = 100
) -> int:
    """从 start_port 开始递增，找到可用端口"""
    import socket as _socket

    for offset in range(max_tries):
        candidate = start_port + offset
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.bind((host, candidate))
            s.close()
            return candidate
        except OSError:
            continue
    return start_port  # fallback，让 server 自行报错


def start_server(
    port: int = DEFAULT_PORT, host: str = DEFAULT_HOST, dcc_name: str = None
):
    """启动 DCC Bridge TCP 服务端

    如果指定端口已被占用，自动递增寻找可用端口。

    Args:
        port: 监听端口，默认 7002
        host: 监听地址，默认 127.0.0.1
        dcc_name: DCC 类型，默认自动检测

    Returns:
        SocketServerThread 实例（服务端后台线程）
    """
    # 自动检测 DCC 环境
    dcc_name = dcc_name or detect_dcc()
    print(f"Detected DCC: {dcc_name}")
    try:
        from dcc_bridge import discovery
        from dcc_bridge.server import SocketServerThread

        # 端口冲突时自动递增
        actual_port = _find_available_port(port, host)
        if actual_port != port:
            print(f"Port {port} is in use, using {actual_port} instead")

        adapter = get_adapter(dcc_name)

        # Houdini 走 adapter.run_on_main_thread（一次性事件循环回调），不 import
        # PySide，避免双 Qt 崩溃；Blender 无 Qt 也走 adapter 路径；其余 Qt DCC
        # 用 Signal 派发。
        use_qt_signal = dcc_name not in ("houdini", "blender")

        server_thread = SocketServerThread(
            adapter=adapter,
            port=actual_port,
            host=host,
            use_qt_signal=use_qt_signal,
        )
        server_thread.start()

        # 注册进程发现文件
        discovery.register_instance(
            adapter=adapter,
            port=actual_port,
            host=host,
        )

        # 注意：不注册 atexit 清理。DCC 崩溃/强制结束时 atexit 不可靠，
        # 发现文件由 CLI / 扩展在读取时通过惰性 PID 检查自动清理。

        logger = adapter.get_logger()
        logger.info(f"DCC Bridge Server started on {host}:{actual_port}")
        print(f"DCC Bridge Server started on {host}:{actual_port}")
        print("Waiting for connections...")

        return server_thread

    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure the dcc-bridge package is installed and in sys.path")
        raise
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    start_server(DEFAULT_PORT)
