"""
dcc-bridge: DCC Python 桥接核心包

提供 DCC 端 TCP 服务端、通用 TCP 客户端、CLI 入口、DCC 适配器、
代码执行、模块热重载、debugpy 调试集成等底层能力。
"""

from __future__ import annotations

# 从已安装包的元数据中读取版本号，与 pyproject.toml 保持一致
try:
    from importlib.metadata import version as _get_version
    __version__ = _get_version("dcc-bridge")
except Exception:
    __version__ = "0.0.0"  # 包未安装时的回退值

from .client import DCCClient
from .discovery import list_instances, get_instance, register_instance, unregister_instance

__all__ = [
    "__version__",
    "DCCClient",
    "list_instances",
    "get_instance",
    "register_instance",
    "unregister_instance",
]
