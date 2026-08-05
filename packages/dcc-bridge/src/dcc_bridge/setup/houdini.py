"""
Houdini 自启动注入器

通过注册表枚举已安装的 Houdini 版本，定位内置 Python 解释器，
并将启动脚本写入用户的 pythonX.Ylibs 目录。

操作流程：
  1. 枚举 HKLM\\SOFTWARE\\Side Effects Software 下形如 "Houdini 19.5.773" 的子键，
     从中读取 InstallPath（安装目录）与 Version（完整版本号）。
  2. 版本号忽略补丁号，仅保留 major.minor（如 "19.5"、"22.0"）。
  3. 由安装目录拼接出内置 Python 解释器路径（python3X/python.exe）。
  4. 运行 Python 解释器查询其版本（如 "3.13"），用于拼接脚本目录。
  5. 启动脚本目录：~/Documents/houdini<version>/python<pythonversion>libs
  6. launcher 文件名固定为 uiready.py（Houdini 约定 UI 就绪时执行），主脚本位于
     pythonX.Ylibs/dcc_bridge/ 隔离子目录，避免被自动加载导致双启动。
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Optional

from dcc_bridge.setup.base import DCCSetup

# Houdini 注册表基路径
HOUDINI_REG_BASE = r"SOFTWARE\Side Effects Software"

# 匹配形如 "Houdini 19.5.773" 的子键名
# 第 1 组 = 主版本，第 2 组 = 次版本，第 3 组 = 补丁号
_HOUDINI_KEY_PATTERN = re.compile(r"^Houdini\s+(\d+)\.(\d+)\.(\d+)$")

# 用户脚本目录中的 Python libs 子目录名后缀
HOUDINI_PYTHON_LIBS_SUFFIX = "Libs"


class HoudiniSetup(DCCSetup):
    """
    Houdini 自启动注入器

    注册表路径：HKLM\\SOFTWARE\\Side Effects Software\\Houdini <X.Y.Z>
      InstallPath = "C:\\Program Files\\Side Effects Software\\Houdini 19.5.773"
      Version     = "19.5.773"
    脚本目录：  ~/Documents/houdini<X.Y>/python<pyver>libs
    主脚本：    python<pyver>libs/dcc_bridge/dcc_bridge_startup.py
    launcher：  python<pyver>libs/uiready.py（Houdini 约定 UI 就绪时执行）
    """

    dcc_name = "houdini"
    # 仅支持 19.0+ 的 Houdini
    min_supported_version = "19.0"

    def _enum_houdini_installs(self) -> list[tuple[str, str]]:
        """枚举注册表，返回 [(完整版本号子键, 安装路径)]，如 ('Houdini 19.5.773', 'C:\\...')"""
        installs: list[tuple[str, str]] = []
        for subkey in self._enum_registry_subkeys(HOUDINI_REG_BASE):
            m = _HOUDINI_KEY_PATTERN.match(subkey)
            if not m:
                continue
            install_path = self._read_registry_value(
                f"{HOUDINI_REG_BASE}\\{subkey}", "InstallPath"
            )
            if install_path:
                installs.append((subkey, install_path))
        return installs

    def discover_versions(self) -> list[str]:
        """从注册表扫描已安装的 Houdini 版本号（忽略补丁号，如 "19.5"）"""
        versions: list[str] = []
        for full_key, _ in self._enum_houdini_installs():
            m = _HOUDINI_KEY_PATTERN.match(full_key)
            if m is None:
                continue
            versions.append(f"{m.group(1)}.{m.group(2)}")
        return sorted(set(versions))

    def get_install_path(self, version: str) -> str | None:
        """根据 major.minor 版本号返回安装路径"""
        for full_key, install_path in self._enum_houdini_installs():
            m = _HOUDINI_KEY_PATTERN.match(full_key)
            if m is None:
                continue
            if f"{m.group(1)}.{m.group(2)}" == version:
                return install_path
        return None

    def get_python_path(self, version: str) -> str | None:
        """由安装目录拼接 Houdini 内置 Python 解释器路径

        Houdini 将 Python 内置在 <install>/python3X/python.exe。
        由于 X 随版本变化，这里枚举 python3* 目录并取最高版本；
        若找不到则返回None
        """
        install_path = self.get_install_path(version)
        if not install_path or not os.path.isdir(install_path):
            return None

        candidates: list[str] = []
        for entry in os.listdir(install_path):
            if entry.lower().startswith("python3"):
                candidate = os.path.join(install_path, entry, "python.exe")
                if os.path.exists(candidate):
                    candidates.append(candidate)
        if candidates:

            def _py_dir_score(path: str) -> int:
                digits = re.sub(r"\D", "", os.path.basename(os.path.dirname(path)))
                return int(digits) if digits else 0

            return max(candidates, key=_py_dir_score)

        return None

    def _query_python_version(self, python_path: str) -> str | None:
        """运行 Python 解释器，返回 major.minor 版本字符串（如 "3.13"）"""
        try:
            result = subprocess.run(
                [
                    python_path,
                    "-c",
                    "import sys; print('%d.%d' % sys.version_info[:2])",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.SubprocessError, OSError, ValueError):
            # 解释器不可用或查询失败，交由调用方决定如何处理
            pass
        return None

    def get_script_dir(
        self, version: str | None = None, language: str = "en"
    ) -> Optional[str]:  # noqa: UP045
        """拼接 Houdini 的 pythonX.Ylibs 启动脚本目录

        目录结构：~/Documents/houdini<version>/python<pythonversion>libs
        例：      ~/Documents/houdini22.0/python3.13libs
        """
        if version is None:
            versions = self.discover_versions()
            if not versions:
                return None
            version = versions[0]

        install_path = self.get_install_path(version)
        if not install_path:
            return None

        python_path = self.get_python_path(version)
        if not python_path:
            return None

        py_ver = self._query_python_version(python_path)
        if not py_ver:
            return None

        home = os.path.expanduser("~")
        return os.path.join(
            home,
            "Documents",
            f"houdini{version}",
            f"python{py_ver}{HOUDINI_PYTHON_LIBS_SUFFIX}",
        )

    def get_supported_languages(self) -> list[str]:
        """Houdini 的 pythonX.Ylibs 目录不随语言变化，只注入一份即可"""
        return ["en"]

    def get_launcher_name(self) -> str | None:
        """Houdini 的 launcher 用 uiready.py（约定 UI 就绪时被执行）。

        launcher 位于 pythonX.Ylibs 自动加载目录，显式 exec 隔离子目录中的主脚本；
        主脚本本身在 pythonX.Ylibs/dcc_bridge/ 内，不会被自动执行，避免双启动。
        """
        return "uiready.py"


if __name__ == "__main__":
    hs = HoudiniSetup()
    version_list = hs.discover_versions()
    for version in version_list:
        script_dir = hs.get_script_dir(version=version)
        install_dir = hs.get_install_path(version=version)
        python_path = hs.get_python_path(version=version)
        print(f"{version} -> {script_dir} ({install_dir}) ({python_path})")
