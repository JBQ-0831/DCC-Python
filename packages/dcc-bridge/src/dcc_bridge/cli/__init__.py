"""
dcc-bridge CLI 子包

提供 `dcc` 命令行工具，用于：
- 在 DCC 中执行代码/文件（dcc run）
- 注入/移除 DCC 自启动脚本（dcc setup / unsetup）
- 列出运行中的 DCC 实例（dcc list / status / ping）
"""

from __future__ import annotations
