"""
Blender 自启动注入器

通过注册表（文件关联）获取已安装版本与安装路径，直接拼接用户脚本目录。
仅实现 Blender 特有的注册表路径与目录结构。

注册表依据（用户实测）：
  HKLM\\SOFTWARE\\Classes\\blender.<version>
    - 子键名 blender.4.5 中的 '4.5' 即为版本号，从 Classes 下用正则匹配得到。
  HKLM\\SOFTWARE\\Classes\\blender.<version>\\shell\\open\\command
    - 默认值记录了安装位置，例如：
      "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender-launcher.exe" "%1"
    - 提取其中的 exe 路径并取所在目录作为安装根目录。
"""

from __future__ import annotations

import os
import re

from dcc_bridge.setup.base import DCCSetup

# Blender 在 HKLM\SOFTWARE\Classes 下以 blender.<version> 形式注册文件关联
BLENDER_CLASSES_BASE = r"SOFTWARE\Classes"

# 匹配 blender.4.5（捕获 4.5 作为版本号）
_BLENDER_KEY_PATTERN = re.compile(r"^blender\.((?:\d+\.)*\d+)$")

# 从 shell\open\command 的默认值中提取 exe 路径。
# 真实注册表值可能带前导引号（"C:\...\blender-launcher.exe" "%1"），
# 也可能没有前导引号（C:\...\blender-launcher.exe" "%1），两种都要兼容。
_EXE_PATTERN = re.compile(r'([A-Za-z]:\\(?:[^"\\]+\\)*[^"\\]*\.exe)')


def _version_sort_key(version: str) -> list[int]:
    """将 '4.5' 解析为 [4, 5]，便于按数值（而非字典序）排序"""
    return [int(p) for p in version.split(".") if p.isdigit()]


class BlenderSetup(DCCSetup):
    """
    Blender 自启动注入器

    注册表（文件关联）：HKLM\\SOFTWARE\\Classes\\blender.<version>
      - 子键名 blender.4.5 的 '4.5' 即为版本号，用正则从 Classes 下匹配得到。
      - blender.<version>\\shell\\open\\command 的默认值记录了安装位置：
            "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender-launcher.exe" "%1"
        提取其中的 exe 路径并取所在目录作为安装根目录。
    脚本目录：%APPDATA%\\Blender Foundation\\Blender\\<version>\\scripts\\startup
      Blender 启动时会自动执行 scripts/startup/ 下的 .py 脚本，无需额外修改配置。
    Blender 的脚本目录不随语言变化，因此 get_supported_languages 只返回 ["en"]。
    """

    dcc_name = "blender"
    # Blender 版本号为 major.minor，不做最低版本过滤
    min_supported_version = None

    def discover_versions(self) -> list[str]:
        """从 HKLM\\SOFTWARE\\Classes 下匹配 blender.<version> 子键，提取版本号"""
        subkeys = self._enum_registry_subkeys(BLENDER_CLASSES_BASE)
        versions = []
        for sk in subkeys:
            m = _BLENDER_KEY_PATTERN.match(sk)
            if m:
                versions.append(m.group(1))
        return sorted(set(versions), key=_version_sort_key)

    def get_install_path(self, version: str) -> str | None:
        """从 blender.<version>\\shell\\open\\command 默认值解析安装目录"""
        reg_path = f"{BLENDER_CLASSES_BASE}\\blender.{version}\\shell\\open\\command"
        command = self._read_registry_value(reg_path, "")
        if not command:
            return None
        m = _EXE_PATTERN.search(command)
        if not m:
            return None
        # 命令指向 blender-launcher.exe，其所在目录即为安装根目录
        return os.path.dirname(m.group(1))

    def get_script_dir(
        self, version: str | None = None, language: str = "en"
    ) -> str | None:
        """拼接 Blender 的 scripts/startup 目录（用于放置自启动脚本）

        %APPDATA% 默认等于 ~\\AppData\\Roaming，这里用 expanduser 拼接，
        与测试中的 mock_home fixture 保持一致。
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
        return os.path.join(
            home,
            "AppData",
            "Roaming",
            "Blender Foundation",
            "Blender",
            version,
            "scripts",
            "startup",
        )

    def get_python_path(self, version: str) -> str | None:
        """返回 Blender 内置 Python 解释器路径（<安装目录>/<version>/python/bin/python.exe）"""
        install_path = self.get_install_path(version)
        if install_path:
            return os.path.join(install_path, version, "python", "bin", "python.exe")
        return None

    def get_supported_languages(self) -> list[str]:
        """Blender 的脚本目录不随语言变化，只注入一份即可"""
        return ["en"]

if __name__ == "__main__":
    setup = BlenderSetup()
    version = setup.discover_versions()[0]
    print(version)
    print(setup.get_install_path(version))
    print(setup.get_script_dir(version))
    print(setup.get_python_path(version))
