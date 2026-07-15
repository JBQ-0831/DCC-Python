"""
支持 `python -m dcc_bridge` 调用，转发到 CLI 主入口。
"""

from __future__ import annotations

from dcc_bridge.cli.main import main

if __name__ == "__main__":
    main()
