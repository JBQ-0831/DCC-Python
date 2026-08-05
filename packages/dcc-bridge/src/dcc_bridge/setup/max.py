"""
3ds Max 自启动注入器

通过注册表获取已安装版本与安装路径，直接拼接用户脚本目录。
仅实现 Max 特有的注册表路径与版本匹配规则。
"""

from __future__ import annotations

import os
import re
from typing import Optional

from dcc_bridge.setup.base import DCCSetup

# Max 注册表基路径
MAX_REG_BASE = r"SOFTWARE\Autodesk\3dsMax"

# 从安装路径中提取年份，如 C:\\Program Files\\Autodesk\\3ds Max 2019\\ -> 2019
_YEAR_PATTERN = re.compile(r"(\d{4})")

# Max 语言代码 -> 用户设置目录名映射
# 英文: ENU，简体中文: CHS
_MAX_LANG_DIR = {
    "en": "ENU",
    "zh_CN": "CHS",
}

# Max launcher 模板（MAXScript）：显式用 python.ExecuteFile 执行主脚本。
# 主脚本绝对路径由 get_startup_script_path 计算后嵌入，确保与写入位置一致。
# @"" 为 MAXScript 逐字字符串，反斜杠不转义。
_MAX_LAUNCHER_MS_TEMPLATE = '''\
-- DCC Bridge launcher (auto-generated)
-- Remove with: dcc unsetup {dcc_name}
python.ExecuteFile @"{main_script}"
'''


class MaxSetup(DCCSetup):
    """
    3ds Max 自启动注入器

    注册表路径：HKLM\\SOFTWARE\\Autodesk\\3dsMax\\<internal_version>
    安装路径：  上述子键下的 Installdir 值
    脚本目录：  ~/AppData/Local/Autodesk/3dsMax/<year> - 64bit/ENU/scripts/startup/
    Max 启动时自动加载 startup/ 目录下的脚本，无需额外修改配置文件。
    """

    dcc_name = "3dsmax"
    # 仅支持 2019+ 的 3ds Max
    min_supported_version = "2019"

    def discover_versions(self) -> list[str]:
        """从注册表扫描已安装的 3ds Max 版本号（年份）"""
        subkeys = self._enum_registry_subkeys(MAX_REG_BASE)
        versions: list[str] = []
        for sk in subkeys:
            install_dir = self._read_registry_value(
                f"{MAX_REG_BASE}\\{sk}", "Installdir"
            )
            if install_dir:
                match = _YEAR_PATTERN.search(install_dir)
                if match:
                    versions.append(match.group(1))
        return sorted(set(versions))

    def get_install_path(self, version: str) -> str | None:
        """从注册表获取指定版本的安装路径"""
        subkeys = self._enum_registry_subkeys(MAX_REG_BASE)
        for sk in subkeys:
            install_dir = self._read_registry_value(
                f"{MAX_REG_BASE}\\{sk}", "Installdir"
            )
            if install_dir:
                match = _YEAR_PATTERN.search(install_dir)
                if match and match.group(1) == version:
                    return install_dir
        return None

    def get_script_dir(
        self, version: str | None = None, language: str = "en"
    ) -> Optional[str]:  # noqa: UP045
        """拼接指定版本、指定语言 Max 的 scripts/startup 目录

        language: 'en' -> ENU，'zh_CN' -> CHS
        """
        if version is None:
            versions = self.discover_versions()
            if not versions:
                return None
            version = versions[0]

        # 验证版本是否已安装
        if not self.get_install_path(version):
            return None

        # 未知语言回退为英文
        lang_dir = _MAX_LANG_DIR.get(language, _MAX_LANG_DIR["en"])

        home = os.path.expanduser("~")
        return os.path.join(
            home,
            "AppData",
            "Local",
            "Autodesk",
            "3dsMax",
            f"{version} - 64bit",
            lang_dir,
            "scripts",
            "startup",
        )

    def get_python_path(self, version: str) -> str | None:
        """返回 3ds Max 指定版本的 Python 解释器路径

        2020 之前的版本（2017-2019）Python 解析器位于 <max root>/3dsmaxpy.exe；
        2020 及以上版本位于 <max root>/Python/python.exe。
        """
        install_path = self.get_install_path(version)
        if not install_path:
            return None
        # 2020 之前版本使用 3dsmaxpy.exe，2020+ 使用 Python/python.exe
        if int(version) < 2020:
            return os.path.join(install_path, "3dsmaxpy.exe")
        return os.path.join(install_path, "Python", "python.exe")

    def get_launcher_name(self) -> str | None:
        """Max 的 launcher 是放在自动加载根目录 startup/ 下的 MAXScript 文件。"""
        return "start_dcc_bridge.ms"

    def get_startup_script_path(
        self, version: str | None = None, language: str = "en"
    ) -> str | None:
        """主脚本写入 scripts/dcc_bridge/（startup 的上级 scripts 目录）。

        这样主脚本不会落在 startup/ 内被 Max 递归自动加载，从而避免双启动；
        launcher（start_dcc_bridge.ms）才放在 startup/ 中显式启动它。
        """
        script_dir = self.get_script_dir(version, language)
        if script_dir is None:
            return None
        scripts_root = os.path.dirname(script_dir)
        return os.path.join(scripts_root, self.bridge_subdir, self.get_startup_script_name())

    def get_launcher_content(
        self, version: str | None = None, language: str = "en"
    ) -> str:
        """生成 MAXScript launcher：显式用 python.ExecuteFile 执行主脚本。

        主脚本的绝对路径由 get_startup_script_path 计算后嵌入，确保与写入位置一致
        （Max 的 GetDir #userScripts 指向 Documents 目录，与本工具实际写入的
        AppData/Local 路径不同，不能依赖它）。
        """
        main_script = self.get_startup_script_path(version, language)
        if main_script is None:
            return ""
        return _MAX_LAUNCHER_MS_TEMPLATE.format(
            dcc_name=self.dcc_name,
            main_script=main_script,
        )
