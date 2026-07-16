"""
DCC 自启动注入器基类

通用逻辑（版本发现、路径计算、脚本写入/删除）全部在此实现，
子类只需实现少量抽象方法描述各自 DCC 的注册表路径与目录结构。

暂时还没有实现sp的自启动注入器，SP的注册表位置有两个可选项能找到安装目录，但是都无法判断版本
但是所有版本的SP的自启动目录都放在我的文档下面的
计算机\\HKEY_LOCAL_MACHINE\\SOFTWARE\\Classes\\SubstancePainterProject\\shell\\open\\command
计算机\\HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\Adobe Substance 3D Painter.exe
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# winreg 仅 Windows 可用，非 Windows 平台静默跳过
try:
    import winreg
except ImportError:
    winreg = None  # type: ignore


@dataclass
class DCCInstallation:
    """DCC 安装信息"""
    dcc_type: str
    version: str
    root_path: str


class DCCSetup(ABC):
    """
    DCC 自启动注入器基类

    子类需实现以下抽象方法：
      - discover_versions()              从注册表扫描已安装版本号
      - get_install_path(version)        从注册表获取安装路径
      - get_script_dir(version, language) 拼接自启动脚本写入目录

    子类可覆盖以下钩子方法：
      - get_supported_languages()      支持的语言列表（影响脚本写入位置）
      - get_startup_script_name()      启动脚本文件名
      - get_startup_script_content()   启动脚本内容
      - _post_setup()                  setup 完成后的额外操作
      - _post_unsetup()                unsetup 完成后的额外操作

    多语言支持：
      默认同时注入到 en 与 zh_CN 两个语言目录。
      脚本路径不随语言变化的 DCC（如 Substance Painter）可覆盖
      get_supported_languages() 返回 ["en"]，避免重复写入。
    """

    dcc_type: str = ""

    # 不指定 --version 时的最低支持版本，None 表示不限制
    min_supported_version: Optional[str] = None

    # ==================== 注册表工具方法 ====================

    def _read_registry_value(self, reg_path: str, value_name: str) -> Optional[str]:
        """
        读取 HKLM 下指定路径的注册表值

        Args:
            reg_path:   注册表路径，如 r"SOFTWARE\\Autodesk\\Maya"
            value_name: 值名称，空字符串表示读取默认值

        Returns:
            值字符串（自动去除首尾引号），读取失败返回 None
        """
        if winreg is None:
            return None
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, reg_path,
                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            try:
                value, _ = winreg.QueryValueEx(key, value_name)
                val = str(value)
                # 部分注册表值（如 App Paths）可能包含引号，统一去除
                if len(val) > 1 and val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                return val
            finally:
                winreg.CloseKey(key)
        except OSError:
            return None

    def _enum_registry_subkeys(self, reg_path: str) -> List[str]:
        """
        枚举 HKLM 下指定路径的所有子键名

        Args:
            reg_path: 注册表路径

        Returns:
            子键名列表，读取失败返回空列表
        """
        if winreg is None:
            return []
        subkeys: List[str] = []
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, reg_path,
                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            try:
                i = 0
                while True:
                    try:
                        subkeys.append(winreg.EnumKey(key, i))
                        i += 1
                    except OSError:
                        break
            finally:
                winreg.CloseKey(key)
        except OSError:
            pass
        return subkeys

    def _enum_registry_values(self, reg_path: str) -> Dict[str, str]:
        """
        枚举 HKLM 下指定路径的所有值名与值

        Args:
            reg_path: 注册表路径

        Returns:
            {值名: 值字符串} 字典，读取失败返回空字典
        """
        if winreg is None:
            return {}
        result: Dict[str, str] = {}
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, reg_path,
                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            try:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        if isinstance(value, str):
                            result[name] = value
                        i += 1
                    except OSError:
                        break
            finally:
                winreg.CloseKey(key)
        except OSError:
            pass
        return result

    # ==================== 抽象方法 ====================

    @abstractmethod
    def discover_versions(self) -> List[str]:
        """从注册表扫描已安装的版本号列表"""
        raise NotImplementedError

    @abstractmethod
    def get_install_path(self, version: str) -> Optional[str]:
        """从注册表获取指定版本的安装路径"""
        raise NotImplementedError

    @abstractmethod
    def get_script_dir(self, version: Optional[str] = None, language: str = "en") -> Optional[str]:
        """拼接指定版本、指定语言的自启动脚本写入目录"""
        raise NotImplementedError

    # ==================== 可覆盖的钩子 ====================

    def get_supported_languages(self) -> List[str]:
        """返回该 DCC 支持的语言列表，决定 setup 时写入的语言目录。

        默认同时注入英文与简体中文。脚本路径不随语言变化的 DCC
        （如 Substance Painter）应覆盖此方法返回 ["en"]。
        将来扩展其他语言只需在子类返回列表中追加，如 ["en", "zh_CN", "ja"]。
        """
        return ["en", "zh_CN"]

    def get_startup_script_name(self) -> str:
        """返回启动脚本文件名，默认 dcc_bridge_startup.py"""
        return "dcc_bridge_startup.py"

    def get_startup_script_content(self) -> str:
        """
        返回启动脚本内容

        关键：dcc-bridge 安装在系统 Python 的 site-packages 中，
        DCC 的 Python 解释器不知道该路径，因此需要在脚本中
        显式将 dcc_bridge 包所在目录加入 sys.path。
        """
        # 获取 dcc_bridge 包的实际安装路径（site-packages 目录）
        import dcc_bridge as _db
        _pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(_db.__file__)))

        return f'''\
# DCC Bridge 自动启动脚本
# 由 `dcc setup {self.dcc_type}` 注入，删除前请先运行 `dcc unsetup {self.dcc_type}`
import sys

# dcc-bridge 安装在系统 Python 中，DCC 的 Python 需要显式添加路径
_BRIDGE_PKG_DIR = r"{_pkg_dir}"
if _BRIDGE_PKG_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_PKG_DIR)

try:
    from dcc_bridge.start import start_server
except ImportError:
    # dcc-bridge 依赖缺失或已被卸载，静默跳过
    pass
else:
    start_server()
'''

    def _post_setup(self, script_dir: str) -> None:
        """setup 完成后的额外操作（如修改 userSetup.py），子类可覆盖"""
        pass

    def _post_unsetup(self, script_dir: str) -> None:
        """unsetup 完成后的额外操作（如还原 userSetup.py），子类可覆盖"""
        pass

    # ==================== 通用实现 ====================

    def _get_target_versions(self, version: Optional[str] = None) -> List[str]:
        """
        获取需要操作的目标版本列表

        指定 version 时直接返回 [version]；
        不指定时返回所有已安装版本中 >= min_supported_version 的版本。
        """
        if version:
            return [version]
        versions = self.discover_versions()
        if self.min_supported_version:
            versions = [v for v in versions if v >= self.min_supported_version]
        return versions

    def detect_installations(self) -> List[DCCInstallation]:
        """检测系统中已安装的 DCC 实例"""
        installations: List[DCCInstallation] = []
        for version in self.discover_versions():
            install_path = self.get_install_path(version)
            if install_path:
                installations.append(DCCInstallation(
                    dcc_type=self.dcc_type,
                    version=version,
                    root_path=install_path,
                ))
        return installations

    def get_startup_script_path(self, version: Optional[str] = None, language: str = "en") -> Optional[str]:
        """返回自启动脚本应写入的完整路径"""
        script_dir = self.get_script_dir(version, language)
        if script_dir is None:
            return None
        return os.path.join(script_dir, self.get_startup_script_name())

    def setup(self, version: Optional[str] = None) -> bool:
        """
        注入自启动脚本

        指定 version 时只注入该版本；不指定时遍历所有 >= min_supported_version 的已安装版本。
        全部成功返回 True，任一失败返回 False。
        """
        versions = self._get_target_versions(version)
        if not versions:
            print(f"{self.dcc_type} no installed versions found")
            return False

        all_success = True
        for ver in versions:
            if not self._setup_single(ver):
                all_success = False
        return all_success

    def _setup_single(self, version: str) -> bool:
        """注入单个版本的自启动脚本（覆盖所有支持的语言目录）"""
        languages = self.get_supported_languages()
        any_success = False

        for lang in languages:
            script_dir = self.get_script_dir(version, lang)
            if script_dir is None:
                # 某些语言目录可能不存在（如用户从未启动过中文版 DCC），跳过
                print(f"{self.dcc_type} scripts directory not found for version={version} lang={lang}")
                continue

            os.makedirs(script_dir, exist_ok=True)

            startup_script_path = os.path.join(script_dir, self.get_startup_script_name())
            with open(startup_script_path, "w", encoding="utf-8") as f:
                f.write(self.get_startup_script_content())

            print(f"{self.dcc_type} setup: wrote {startup_script_path}")

            self._post_setup(script_dir)
            any_success = True

        return any_success

    def unsetup(self, version: Optional[str] = None) -> bool:
        """
        移除自启动脚本

        指定 version 时只移除该版本；不指定时遍历所有 >= min_supported_version 的已安装版本。
        全部成功返回 True，任一失败返回 False。
        """
        versions = self._get_target_versions(version)
        if not versions:
            print(f"{self.dcc_type} no installed versions found")
            return False

        all_success = True
        for ver in versions:
            if not self._unsetup_single(ver):
                all_success = False
        return all_success

    def _unsetup_single(self, version: str) -> bool:
        """移除单个版本的自启动脚本（覆盖所有支持的语言目录）"""
        languages = self.get_supported_languages()
        any_success = False

        for lang in languages:
            script_dir = self.get_script_dir(version, lang)
            if script_dir is None:
                print(f"{self.dcc_type} scripts directory not found for version={version} lang={lang}")
                continue

            startup_script_path = os.path.join(script_dir, self.get_startup_script_name())
            if os.path.exists(startup_script_path):
                try:
                    os.remove(startup_script_path)
                    print(f"{self.dcc_type} unsetup: removed {startup_script_path}")
                except OSError as e:
                    print(f"{self.dcc_type} unsetup: failed to remove {startup_script_path}: {e}")
                    continue
            else:
                print(f"{self.dcc_type} unsetup: startup script not found at {startup_script_path}")

            self._post_unsetup(script_dir)
            any_success = True

        return any_success


def get_setup(dcc_type: str) -> Optional[DCCSetup]:
    """根据 DCC 类型获取注入器实例（支持别名）"""
    from ..dcc_types import normalize_dcc_type
    dcc_type = normalize_dcc_type(dcc_type)

    if dcc_type == "maya":
        from .maya import MayaSetup
        return MayaSetup()
    if dcc_type == "3dsmax":
        from .max import MaxSetup
        return MaxSetup()
    if dcc_type == "substance_painter":
        from .painter import PainterSetup
        return PainterSetup()
    if dcc_type == "substance_designer":
        from .designer import DesignerSetup
        return DesignerSetup()
    return None
