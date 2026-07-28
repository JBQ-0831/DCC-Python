"""
DCC 适配器包

包含各 DCC 软件的适配器实现。当前实现：
- maya: MayaAdapter
- max: MaxAdapter
- painter: SubstancePainterAdapter
- houdini: HoudiniAdapter
- blender: BlenderAdapter
"""

from __future__ import annotations

from .base import DCCAdapter, Logger
from .maya import MayaAdapter
from .max import MaxAdapter

try:
    from .painter import SubstancePainterAdapter
except ImportError:
    SubstancePainterAdapter = None  # type: ignore

try:
    from .houdini import HoudiniAdapter
except ImportError:
    HoudiniAdapter = None  # type: ignore

try:
    from .blender import BlenderAdapter
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
