"""
substance painter 自启动注入器

通过注册表获取安装路径，直接拼接用户脚本目录。
仅实现 SP 特有的注册表路径与目录结构。
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from dcc_bridge.setup.base import DCCSetup

# import sys,os
# root = os.path.dirname(__file__)
# if root not in sys.path:
#     sys.path.append(root)
# from base import DCCSetup

# SP 注册表路径：默认值 = exe 完整路径，Path = 安装目录
SP_REG_BASE = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Adobe Substance 3D Painter.exe"


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


class PainterSetup(DCCSetup):
    """
    Substance Painter 自启动注入器

    注册表路径：HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\Adobe Substance 3D Painter.exe
      默认值 = "C:\\Program Files\\Adobe\\Adobe Substance 3D Painter\\Adobe Substance 3D Painter.exe"
      Path    = "C:\\Program Files\\Adobe\\Adobe Substance 3D Painter\\"
    脚本目录：~/Documents/Adobe/Adobe Substance 3D Painter/python/startup
    SP 启动时自动加载 startup/ 目录下的脚本，无需额外修改配置文件。

    SP 一台电脑只能同时安装一个版本，且脚本路径不随语言变化，
    因此 discover_versions 通过 exe 的 ProductVersion 获取版本，
    get_supported_languages 只返回 ["en"]。
    """

    dcc_name = "substance_painter"

    def discover_versions(self) -> list[str]:
        """用 ctypes 读取 exe 的版本信息，取前两段作为版本号（如 10.1）。"""
        exe_path = self._read_registry_value(SP_REG_BASE, "")
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
                buffer, "\\", ctypes.byref(info_ptr), ctypes.byref(info_len)
            ):
                return []

            ffi = ctypes.cast(info_ptr, ctypes.POINTER(_VS_FIXEDFILEINFO)).contents
            major = ffi.dwFileVersionMS >> 16
            minor = ffi.dwFileVersionMS & 0xFFFF
            return [f"{major}.{minor}"]
        except Exception:
            return []

    def get_install_path(self, version: str | None = None) -> str | None:
        """从注册表获取 SP 的安装目录（Path 值）"""
        return self._read_registry_value(SP_REG_BASE, "Path")

    def get_script_dir(
        self, version: str | None = None, language: str = "en"
    ) -> str | None:
        """拼接 SP 的 startup 目录

        SP 的目录全版本都固定在：~/Documents/Adobe/Adobe Substance 3D Painter/python/startup
        """
        home = os.path.expanduser("~")
        return os.path.join(
            home,
            "Documents",
            "Adobe",
            "Adobe Substance 3D Painter",
            "python",
            "startup",
        )

    def get_python_path(self, version: str | None = None) -> str | None:
        """返回 Substance Painter 的 Python 解释器路径"""
        install_path = self.get_install_path(version)
        if install_path:
            return os.path.join(install_path, "resources", "pythonsdk", "python.exe")
        return None

    def get_supported_languages(self) -> list[str]:
        """SP 的脚本目录不随语言变化，只注入一份即可"""
        return ["en"]


if __name__ == "__main__":
    ps = PainterSetup()
    v = ps.discover_versions()
    print(v)
