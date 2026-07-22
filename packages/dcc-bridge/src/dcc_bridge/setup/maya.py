"""
Maya 自启动注入器

通过注册表获取已安装版本与安装路径，直接拼接用户脚本目录。
仅实现 Maya 特有的注册表路径与 userSetup.py 钩子逻辑。
"""

from __future__ import annotations

import os
import re
from typing import List, Optional

from .base import DCCSetup


# Maya 注册表基路径
MAYA_REG_BASE = r"SOFTWARE\Autodesk\Maya"

# 版本号匹配：2022、2024 等
_VERSION_PATTERN = re.compile(r"^20\d{2}$")

# Maya 启动脚本模块名（写入 userSetup.py 的 import 语句使用）
STARTUP_MODULE_NAME = "dcc_bridge_startup"

# Maya 安装路径可能的值名称（不同版本可能不同）
_INSTALL_PATH_KEYS = ("MAYA_INSTALL_LOCATION", "InstallLocation", "")


class MayaSetup(DCCSetup):
    """
    Maya 自启动注入器

    注册表路径：HKLM\\SOFTWARE\\Autodesk\\Maya\\<version>
    安装路径：  HKLM\\SOFTWARE\\Autodesk\\Maya\\<version>\\Setup\\InstallPath
    脚本目录：  ~/maya/<version>/scripts/
    额外操作：  在 scripts/userSetup.py 中追加 import 行
    """

    dcc_type = "maya"
    # 仅支持 2020+ 的 Maya
    min_supported_version = "2020"

    def discover_versions(self) -> List[str]:
        """从注册表扫描已安装的 Maya 版本号"""
        subkeys = self._enum_registry_subkeys(MAYA_REG_BASE)
        versions = [s for s in subkeys if _VERSION_PATTERN.match(s)]
        return sorted(versions)

    def get_install_path(self, version: str) -> Optional[str]:
        """从注册表获取指定版本的安装路径"""
        reg_path = f"{MAYA_REG_BASE}\\{version}\\Setup\\InstallPath"
        # 尝试已知的值名称，包括默认值（空字符串）
        for key_name in _INSTALL_PATH_KEYS:
            value = self._read_registry_value(reg_path, key_name)
            if value:
                return value
        return None

    def get_script_dir(self, version: Optional[str] = None, language: str = "en") -> Optional[str]:
        """拼接指定版本、指定语言 Maya 的 scripts 目录

        英文：  ~/Documents/maya/<version>/scripts
        中文：  ~/Documents/maya/<version>/zh_CN/scripts
        """
        if version is None:
            versions = self.discover_versions()
            if not versions:
                return None
            version = versions[0]

        # 验证版本是否已安装
        if not self.get_install_path(version):
            return None

        home = os.path.expanduser("~")
        # 中文路径多一层 zh_CN，英文路径无语言子目录
        lang_parts = [language] if language != "en" else []
        return os.path.join(home, "Documents", "maya", version, *lang_parts, "scripts")

    def get_python_path(self, version: str) -> Optional[str]:
        """返回 Maya 指定版本的 Python 解释器路径（mayapy.exe）"""
        install_path = self.get_install_path(version)
        if install_path:
            return os.path.join(install_path, "bin", "mayapy.exe")
        return None

    def _post_setup(self, script_dir: str) -> None:
        """setup 完成后在 userSetup.py 中追加 import 行"""
        _ensure_import_in_file(
            file_path=os.path.join(script_dir, "userSetup.py"),
            import_line=f"import {STARTUP_MODULE_NAME}\n",
            dcc_label="Maya",
        )

    def _post_unsetup(self, script_dir: str) -> None:
        """unsetup 完成后从 userSetup.py 中移除 import 行"""
        _remove_import_from_file(
            file_path=os.path.join(script_dir, "userSetup.py"),
            import_line=f"import {STARTUP_MODULE_NAME}\n",
            dcc_label="Maya",
        )


# ==================== 模块级辅助函数 ====================

def _ensure_import_in_file(file_path: str, import_line: str, dcc_label: str) -> None:
    """确保指定文件中包含 import 行，不存在则追加"""
    existing_lines: List[str] = []
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    # 已存在则跳过
    if any(line.strip() == import_line.strip() for line in existing_lines):
        print(f"{dcc_label} setup: userSetup.py already imports {import_line.strip()}")
        return

    # 确保文件末尾有换行
    if existing_lines and not existing_lines[-1].endswith("\n"):
        existing_lines[-1] += "\n"

    existing_lines.append(import_line)
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(existing_lines)
    print(f"{dcc_label} setup: updated {file_path}")


def _remove_import_from_file(file_path: str, import_line: str, dcc_label: str) -> None:
    """从指定文件中移除 import 行"""
    if not os.path.exists(file_path):
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = [line for line in lines if line.strip() != import_line.strip()]

        if len(new_lines) != len(lines):
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print(f"{dcc_label} unsetup: removed import from {file_path}")
        else:
            print(f"{dcc_label} unsetup: no import line found in {file_path}")
    except OSError as e:
        print(f"{dcc_label} unsetup: failed to update {file_path}: {e}")
