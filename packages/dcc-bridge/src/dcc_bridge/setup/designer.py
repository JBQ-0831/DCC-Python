"""
substance designer 自启动注入器

通过注册表获取安装路径，直接拼接用户脚本目录。
仅实现 SD 特有的注册表路径与目录结构。
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import List, Optional
from .base import DCCSetup

# import sys,os
# root = os.path.dirname(__file__)
# if root not in sys.path:
#     sys.path.append(root)
# from base import DCCSetup

# SD 注册表路径：默认值 = exe 完整路径，Path = 安装目录
SD_REG_BASE = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Adobe Substance 3D Designer.exe"


# Windows VS_FIXEDFILEINFO 结构，用于解析 exe 版本信息
class _VS_FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [
        ("dwSignature", wintypes.DWORD),
        ("dwStrucVersion", wintypes.DWORD),
        ("dwFileVersionMS", wintypes.DWORD),
        ("dwFileVersionLS", wintypes.DWORD),
        ("dwProductVersionMS", wintypes.DWORD),
        ("dwProductVersionLS", wintypes.DWORD),
        ("dwFileFlagsMask", wintypes.DWORD),
        ("dwFileFlags", wintypes.DWORD),
        ("dwFileOS", wintypes.DWORD),
        ("dwFileType", wintypes.DWORD),
        ("dwFileSubtype", wintypes.DWORD),
        ("dwFileDateMS", wintypes.DWORD),
        ("dwFileDateLS", wintypes.DWORD),
    ]


class DesignerSetup(DCCSetup):
    """
    Substance Designer 自启动注入器

    注册表路径：HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\Adobe Substance 3D Designer.exe
      默认值 = "C:\\Program Files\\Adobe\\Adobe Substance 3D Designer\\Adobe Substance 3D Designer.exe"
      Path    = "C:\\Program Files\\Adobe\\Adobe Substance 3D Designer\\"
    脚本目录：~/Documents/Adobe/Adobe Substance 3D Designer/python/sduserplugins
    SD 启动时自动加载 sduserplugins/ 目录下的脚本，无需额外修改配置文件。

    SD 一台电脑只能同时安装一个版本，且脚本路径不随语言变化，
    因此 discover_versions 通过 exe 的 ProductVersion 获取版本，
    get_supported_languages 只返回 ["en"]。
    """

    dcc_type = "substance_designer"

    def discover_versions(self) -> List[str]:
        """用 ctypes 读取 exe 的版本信息，取前两段作为版本号（如 10.1）。"""
        exe_path = self._read_registry_value(SD_REG_BASE, "")
        if not exe_path or not os.path.exists(exe_path):
            return []

        try:
            size = ctypes.windll.version.GetFileVersionInfoSizeW(exe_path, None)
            if size == 0:
                return []

            buffer = ctypes.create_string_buffer(size)
            if not ctypes.windll.version.GetFileVersionInfoW(exe_path, 0, size, buffer):
                return []

            info_ptr = ctypes.c_void_p()
            info_len = wintypes.UINT()
            if not ctypes.windll.version.VerQueryValueW(
                buffer, "\\",
                ctypes.byref(info_ptr), ctypes.byref(info_len)
            ):
                return []

            ffi = ctypes.cast(info_ptr, ctypes.POINTER(_VS_FIXEDFILEINFO)).contents
            major = ffi.dwFileVersionMS >> 16
            minor = ffi.dwFileVersionMS & 0xFFFF
            return [f"{major}.{minor}"]
        except Exception:
            return []

    def get_install_path(self, version: Optional[str] = None) -> Optional[str]:
        """从注册表获取 SD 的安装目录（Path 值）"""
        return self._read_registry_value(SD_REG_BASE, "Path")

    def get_script_dir(self, version: Optional[str] = None, language: str = "en") -> Optional[str]:
        """拼接 SD 的 sduserplugins 目录

        SD 的目录全版本都固定在：~/Documents/Adobe/Adobe Substance 3D Designer/python/sduserplugins
        """
        home = os.path.expanduser("~")
        return os.path.join(
            home, "Documents", "Adobe", "Adobe Substance 3D Designer", "python", "sduserplugins",
        )

    def get_python_path(self, version: Optional[str] = None) -> Optional[str]:
        """返回 Substance Designer 的 Python 解释器路径"""
        install_path = self.get_install_path(version)
        if install_path:
            return os.path.join(install_path, "plugins", "pythonsdk", "python.exe")
        return None

    def get_supported_languages(self) -> List[str]:
        """SD 的脚本目录不随语言变化，只注入一份即可"""
        return ["en"]

if __name__ == "__main__" :
    ds = DesignerSetup()
    v = ds.discover_versions()
    print(v)