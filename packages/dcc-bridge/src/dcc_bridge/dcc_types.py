"""
DCC 类型规范化与别名管理

服务端 detect_dcc() 返回的规范名称为：maya / 3dsmax / substance_painter / generic。
本模块提供别名到规范名称的统一映射，供 CLI 入口在接收用户输入后做规范化，
保证底层 discovery / client / setup 只需处理规范名称。
"""
from __future__ import annotations

from typing import Dict, List

# 规范名称 -> 支持的别名列表
_DCC_TYPE_ALIASES: Dict[str, List[str]] = {
    "maya": [],
    "3dsmax": ["max", "3dmax"],
    "substance_painter": ["sp", "painter", "substancepainter"],
    "substance_designer": ["sd", "designer", "substancedesigner"],
}

# 别名（含规范名自身、大小写不敏感）-> 规范名称
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for _canonical, _aliases in _DCC_TYPE_ALIASES.items():
    _ALIAS_TO_CANONICAL[_canonical.lower()] = _canonical
    for _alias in _aliases:
        _ALIAS_TO_CANONICAL[_alias.lower()] = _canonical


def normalize_dcc_type(dcc_type: str) -> str:
    """将 DCC 类型别名规范化为标准名称。

    大小写不敏感。未识别的输入原样返回（保留扩展性）。

    >>> normalize_dcc_type("max")
    '3dsmax'
    >>> normalize_dcc_type("SP")
    'substance_painter'
    >>> normalize_dcc_type("maya")
    'maya'
    """
    if not dcc_type:
        return dcc_type
    return _ALIAS_TO_CANONICAL.get(dcc_type.lower(), dcc_type)


def is_supported_dcc_type(dcc_type: str) -> bool:
    """判断是否为已支持的 DCC 类型（含别名）"""
    if not dcc_type:
        return False
    return dcc_type.lower() in _ALIAS_TO_CANONICAL


def list_supported_dcc_types() -> List[str]:
    """返回所有支持的 DCC 规范名称"""
    return list(_DCC_TYPE_ALIASES.keys())
