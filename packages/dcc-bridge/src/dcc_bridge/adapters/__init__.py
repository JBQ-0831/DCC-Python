# -*- coding: utf-8 -*-
"""
DCC 适配器包

包含各 DCC 软件的适配器实现。当前实现：
- maya_adapter: MayaAdapter
- max_adapter: MaxAdapter
- painter_adapter: SubstancePainterAdapter
- houdini_adapter: HoudiniAdapter
- blender_adapter: BlenderAdapter

兼容 Python 2.7 / 3.x：不使用 from __future__ import annotations。
"""

from .base_adapter import DCCAdapter, Logger
from .maya_adapter import MayaAdapter
from .max_adapter import MaxAdapter

try:
    from .painter_adapter import SubstancePainterAdapter
except ImportError:
    SubstancePainterAdapter = None  # type: ignore

try:
    from .houdini_adapter import HoudiniAdapter
except ImportError:
    HoudiniAdapter = None  # type: ignore

try:
    from .blender_adapter import BlenderAdapter
except ImportError:
    BlenderAdapter = None  # type: ignore

__all__ = [
    "DCCAdapter",
    "Logger",
    "MayaAdapter",
    "MaxAdapter",
    "SubstancePainterAdapter",
    "HoudiniAdapter",
    "BlenderAdapter",
]
