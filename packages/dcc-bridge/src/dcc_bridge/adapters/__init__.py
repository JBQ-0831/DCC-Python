"""
DCC 适配器包

包含各 DCC 软件的适配器实现。当前实现：
- maya: MayaAdapter
- max: MaxAdapter
- painter: SubstancePainterAdapter（接口保留）
"""

from __future__ import annotations

from .base import DCCAdapter, Logger
from .maya import MayaAdapter
from .max import MaxAdapter

try:
    from .painter import SubstancePainterAdapter
except ImportError:
    SubstancePainterAdapter = None  # type: ignore

__all__ = [
    "DCCAdapter",
    "Logger",
    "MayaAdapter",
    "MaxAdapter",
    "SubstancePainterAdapter",
]
