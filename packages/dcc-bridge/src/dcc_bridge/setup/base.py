"""
DCC 自启动注入器基类

通用逻辑（版本发现、路径计算、脚本写入/删除）全部在此实现，
子类只需实现少量抽象方法描述各自 DCC 的注册表路径与目录结构。

"""

from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass

# winreg 仅 Windows 可用，非 Windows 平台静默跳过
try:
    import winreg
except ImportError:
    winreg = None  # type: ignore


@dataclass
class DCCInstallation:
    """DCC 安装信息"""

    dcc_name: str
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

    dcc_name: str = ""

    # 不指定 --version 时的最低支持版本，None 表示不限制
    min_supported_version: str | None = None

    # 主脚本隔离子目录名：主脚本统一写入 <script_dir>/<bridge_subdir>/ 下，
    # 避免被 DCC 在自动加载目录中递归执行而导致双启动；launcher 才放在自动加载根目录。
    # 子类可重写此属性以使用不同的子目录名。
    bridge_subdir: str = "dcc_bridge"

    # ==================== 注册表工具方法 ====================

    def _read_registry_value(self, reg_path: str, value_name: str) -> str | None:
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
                winreg.HKEY_LOCAL_MACHINE,
                reg_path,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
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

    def _enum_registry_subkeys(self, reg_path: str) -> list[str]:
        """
        枚举 HKLM 下指定路径的所有子键名

        Args:
            reg_path: 注册表路径

        Returns:
            子键名列表，读取失败返回空列表
        """
        if winreg is None:
            return []
        subkeys: list[str] = []
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                reg_path,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
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

    def _enum_registry_values(self, reg_path: str) -> dict[str, str]:
        """
        枚举 HKLM 下指定路径的所有值名与值

        Args:
            reg_path: 注册表路径

        Returns:
            {值名: 值字符串} 字典，读取失败返回空字典
        """
        if winreg is None:
            return {}
        result: dict[str, str] = {}
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                reg_path,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
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
    def discover_versions(self) -> list[str]:
        """从注册表扫描已安装的版本号列表"""
        raise NotImplementedError

    @abstractmethod
    def get_install_path(self, version: str) -> str | None:
        """从注册表获取指定版本的安装路径"""
        raise NotImplementedError

    @abstractmethod
    def get_script_dir(
        self, version: str | None = None, language: str = "en"
    ) -> str | None:
        """拼接指定版本、指定语言的自启动脚本写入目录"""
        raise NotImplementedError

    @abstractmethod
    def get_python_path(self, version: str) -> str | None:
        """获取指定版本的 Python 解释器路径（用于安装 debugpy）"""
        raise NotImplementedError

    # ==================== 可覆盖的钩子 ====================

    def get_supported_languages(self) -> list[str]:
        """返回该 DCC 支持的语言列表，决定 setup 时写入的语言目录。

        默认同时注入英文与简体中文。脚本路径不随语言变化的 DCC
        （如 Substance Painter）应覆盖此方法返回 ["en"]。
        将来扩展其他语言只需在子类返回列表中追加，如 ["en", "zh_CN", "ja"]。
        """
        return ["en", "zh_CN"]

    def get_startup_script_name(self) -> str:
        """返回启动脚本文件名，默认 dcc_bridge_startup.py"""
        return "dcc_bridge_startup.py"

    def get_launcher_name(self) -> str | None:
        """返回 launcher 文件名。

        launcher 是放在 DCC 自动加载根目录、负责显式 exec 主脚本的极小启动器。
        返回 None 表示该 DCC 不写独立 launcher 文件（如 Maya 由 _post_setup 修改
        userSetup.py 来启动），此时 _setup_single 不会写 launcher 文件。
        """
        return "dcc_bridge_launcher.py"

    def get_launcher_dir(
        self, version: str | None = None, language: str = "en"
    ) -> str | None:
        """返回 launcher 文件所在目录（DCC 自动加载根目录）。

        默认与主脚本基础目录（get_script_dir）相同；若 launcher 需放在与主脚本
        不同的自动加载目录（如 Max 的 startup/、Blender 的 scripts/startup/），
        子类应覆盖此方法返回真正的自动加载根目录。
        """
        return self.get_script_dir(version, language)

    def get_launcher_content(
        self, version: str | None = None, language: str = "en"
    ) -> str:
        """生成 launcher 脚本内容。

        默认生成 Python launcher（显式 exec 主脚本），跨 py2/py3 兼容。
        主脚本绝对路径由 get_startup_script_path(version, language) 计算后写死进
        launcher，避免依赖 __file__（Maya userSetup.py / Houdini uiready.py 等在
        DCC 内被 exec 时并不提供 __file__ 变量，见 root cause）。
        需要其他语言启动器的 DCC（如 Max 的 MAXScript）应覆盖此方法。
        """
        startup_script_path = self.get_startup_script_path(version, language)
        if not startup_script_path:
            # 兜底：理论上 setup 流程 version 必传、script_dir 非空
            script_dir = self.get_script_dir(version, language) or ""
            startup_script_path = os.path.join(
                script_dir, self.bridge_subdir, self.get_startup_script_name()
            )
        return _LAUNCHER_PY_TEMPLATE.format(
            dcc_name=self.dcc_name,
            startup_script_path=startup_script_path,
        )

    def should_defer_start(self) -> bool:
        """该 DCC 是否需要延迟启动。

        默认 False（同步启动）。某些 DCC 在自启动脚本执行阶段内核/场景
        尚未完全就绪（如 Maya 的 userSetup.py 阶段 cmds.about() 会抛异常），
        需延迟到 DCC 完全初始化后再启动服务。子类可覆盖此方法返回 True。

        Returns:
            True 表示应延迟启动（通过 DCC 提供的 idle/deferred 机制）。
        """
        return False

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

        # 需要延迟启动时，用 DCC 的 idle/deferred 机制把 start_server 推到
        # 主线程空闲后再执行，避免早期内核未就绪导致的 API 异常（如 Maya 的
        # cmds.about()）。否则直接在 import 阶段同步启动。
        if self.should_defer_start():
            _start_body = (
                "    import maya.utils\n"
                "    maya.utils.executeDeferred(start_server)"
            )
        else:
            _start_body = "    start_server()"

        return f'''\
# DCC Bridge auto-startup script
# Generated by `dcc setup {self.dcc_name}`. Remove with `dcc unsetup {self.dcc_name}`
import sys

# dcc-bridge is installed in system Python; DCC Python needs this path explicitly
_BRIDGE_PKG_DIR = r"{_pkg_dir}"
if _BRIDGE_PKG_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_PKG_DIR)

try:
    from dcc_bridge.start import start_server
except ImportError:
    print("dcc-bridge not installed or missing dependencies, cannot start service")
else:
{_start_body}
'''

    def _post_setup(self, script_dir: str) -> None:
        """setup 完成后的额外操作（如修改 userSetup.py），子类可覆盖"""

    def _post_unsetup(self, script_dir: str) -> None:
        """unsetup 完成后的额外操作（如还原 userSetup.py），子类可覆盖"""

    # ==================== 通用实现 ====================

    def _get_target_versions(self, version: str | None = None) -> list[str]:
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

    def detect_installations(self) -> list[DCCInstallation]:
        """检测系统中已安装的 DCC 实例"""
        installations: list[DCCInstallation] = []
        for version in self.discover_versions():
            install_path = self.get_install_path(version)
            if install_path:
                installations.append(
                    DCCInstallation(
                        dcc_name=self.dcc_name,
                        version=version,
                        root_path=install_path,
                    )
                )
        return installations

    def get_startup_script_path(
        self, version: str | None = None, language: str = "en"
    ) -> str | None:
        """返回主脚本应写入的完整路径（位于 bridge_subdir 隔离子目录内）"""
        script_dir = self.get_script_dir(version, language)
        if script_dir is None:
            return None
        return os.path.join(script_dir, self.bridge_subdir, self.get_startup_script_name())

    def _get_python_major_version(self, version):
        """探测目标 DCC 自带 Python 的主版本号（2 或 3）。

        通过实际运行 DCC 的 Python 解释器查询 sys.version_info[0]，避免依赖
        DCC 版本 -> Python 版本的脆弱映射。

        无法确定时返回 None（调用方按「视为 py3」处理，即仍尝试安装/卸载 debugpy，
        行为与原逻辑一致）。debugpy 仅支持 Python 3.x，py2 DCC 应跳过 debugpy
        的安装/卸载。
        """
        python_path = self.get_python_path(version)
        if not python_path or not os.path.exists(python_path):
            return None
        try:
            proc = subprocess.Popen(
                [python_path, "-c", "import sys; print(sys.version_info[0])"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out, _err = proc.communicate()
            if isinstance(out, bytes):
                out = out.decode("utf-8", "replace")
            out = out.strip()
            if out.isdigit():
                return int(out)
        except Exception:
            pass
        return None

    def setup(self, version: str | None = None, pip_index_url: str = "") -> bool:
        """
        注入自启动脚本，并为每个版本安装 debugpy

        指定 version 时只注入该版本；不指定时遍历所有 >= min_supported_version 的已安装版本。
        全部成功返回 True，任一失败返回 False。
        debugpy 安装失败仅输出警告，不阻断 setup 流程。

        版本策略：仅当目标 DCC 的 Python 为 3.x 时才安装 debugpy（debugpy 不支持
        py2）；py2 DCC 只注入自启动脚本，不安装 debugpy。
        """
        versions = self._get_target_versions(version)
        if not versions:
            print(f"{self.dcc_name} no installed versions found")
            return False

        all_success = True
        for ver in versions:
            if not self._setup_single(ver):
                all_success = False
            # 仅在目标 DCC 的 Python 为 3.x 时才安装 debugpy
            # （debugpy 不支持 py2；py2 DCC 仅注入启动脚本即可）
            major = self._get_python_major_version(ver)
            if major is not None and major < 3:
                print(
                    "Skipping debugpy install for {0} {1}: detected Python 2.x "
                    "(debugpy requires Python 3.x)".format(self.dcc_name, ver)
                )
                continue
            # 安装 debugpy 到该版本 DCC 的 Python 环境
            python_path = self.get_python_path(ver)
            if python_path and os.path.exists(python_path):
                try:
                    from ..debug import install_debugpy

                    print(
                        "Installing debugpy for {0} {1} (python={2})...".format(
                            self.dcc_name, ver, python_path
                        )
                    )
                    install_debugpy(python_path, pip_index_url)
                    print(
                        "debugpy installed successfully for {0} {1}".format(
                            self.dcc_name, ver
                        )
                    )
                except Exception as e:
                    print(
                        "Warning: debugpy installation failed for {0} {1}: {2}".format(
                            self.dcc_name, ver, e
                        )
                    )
                    print("  debugpy installation failure does not block startup script injection.")
            else:
                print(
                    "Warning: Python interpreter not found for {0} {1}, skipping debugpy install".format(
                        self.dcc_name, ver
                    )
                )
        return all_success

    def _setup_single(self, version: str) -> bool:
        """注入单个版本的自启动脚本（覆盖所有支持的语言目录）

        主脚本路径由 get_startup_script_path() 决定（默认位于
        <script_dir>/<bridge_subdir>/ 隔离子目录，避免被 DCC 递归自动执行）；
        launcher（若子类定义）写入 get_launcher_dir() 指定的自动加载根目录。
        """
        languages = self.get_supported_languages()
        any_success = False

        for lang in languages:
            script_dir = self.get_script_dir(version, lang)
            if script_dir is None:
                # 某些语言目录可能不存在（如用户从未启动过中文版 DCC），跳过
                print(
                    f"{self.dcc_name} scripts directory not found for version={version} lang={lang}"
                )
                continue

            # 主脚本：路径由 get_startup_script_path 决定（隔离子目录）
            startup_script_path = self.get_startup_script_path(version, lang)
            bridge_dir = os.path.dirname(startup_script_path)
            os.makedirs(bridge_dir, exist_ok=True)

            with open(startup_script_path, "w", encoding="utf-8") as f:
                f.write(self.get_startup_script_content())

            print(f"{self.dcc_name} setup: wrote {startup_script_path}")

            # launcher：写入 DCC 自动加载根目录（由子类决定文件名/内容/目录）
            launcher_name = self.get_launcher_name()
            if launcher_name:
                launcher_dir = self.get_launcher_dir(version, lang)
                if launcher_dir:
                    os.makedirs(launcher_dir, exist_ok=True)
                    launcher_path = os.path.join(launcher_dir, launcher_name)
                    with open(launcher_path, "w", encoding="utf-8") as f:
                        f.write(self.get_launcher_content(version, lang))
                    print(f"{self.dcc_name} setup: wrote launcher {launcher_path}")

            self._post_setup(script_dir)
            any_success = True

        return any_success

    def unsetup(self, version: str | None = None) -> bool:
        """
        移除自启动脚本，并为每个版本卸载该 DCC Python 环境中的 debugpy

        指定 version 时只处理该版本；不指定时遍历所有 >= min_supported_version 的已安装版本。
        全部成功返回 True，任一失败返回 False。
        debugpy 卸载失败仅输出警告，不阻断 unsetup 流程。
        """
        versions = self._get_target_versions(version)
        if not versions:
            print(f"{self.dcc_name} no installed versions found")
            return False

        all_success = True
        for ver in versions:
            if not self._unsetup_single(ver):
                all_success = False
            # 仅在目标 DCC 的 Python 为 3.x 时才卸载 debugpy
            # （py2 DCC 从未安装过 debugpy，无需卸载）
            major = self._get_python_major_version(ver)
            if major is not None and major < 3:
                print(
                    "Skipping debugpy uninstall for {0} {1}: detected Python 2.x "
                    "(debugpy was never installed)".format(self.dcc_name, ver)
                )
                continue
            # 卸载该版本 DCC Python 环境中的 debugpy
            python_path = self.get_python_path(ver)
            if python_path and os.path.exists(python_path):
                try:
                    from ..debug import uninstall_debugpy

                    print(
                        "Uninstalling debugpy for {0} {1} (python={2})...".format(
                            self.dcc_name, ver, python_path
                        )
                    )
                    uninstall_debugpy(python_path)
                    print(
                        "debugpy uninstalled successfully for {0} {1}".format(
                            self.dcc_name, ver
                        )
                    )
                except Exception as e:
                    print("Warning: debugpy uninstallation failed: {0}".format(e))
                    print("  debugpy uninstallation failure does not block startup unsetup.")
            else:
                print(
                    "Warning: Python interpreter not found for {0} {1}, skipping debugpy uninstall".format(
                        self.dcc_name, ver
                    )
                )
        return all_success

    def _unsetup_single(self, version: str) -> bool:
        """移除单个版本的自启动脚本（覆盖所有支持的语言目录）

        删除主脚本、launcher，以及已空的 bridge_subdir 隔离子目录。
        """
        languages = self.get_supported_languages()
        any_success = False

        for lang in languages:
            script_dir = self.get_script_dir(version, lang)
            if script_dir is None:
                print(
                    f"{self.dcc_name} scripts directory not found for version={version} lang={lang}"
                )
                continue

            # 删主脚本
            startup_script_path = self.get_startup_script_path(version, lang)
            bridge_dir = os.path.dirname(startup_script_path)
            if os.path.exists(startup_script_path):
                try:
                    os.remove(startup_script_path)
                    print(f"{self.dcc_name} unsetup: removed {startup_script_path}")
                except OSError as e:
                    print(
                        f"{self.dcc_name} unsetup: failed to remove {startup_script_path}: {e}"
                    )
                    continue
            else:
                print(
                    f"{self.dcc_name} unsetup: startup script not found at {startup_script_path}"
                )

            # 删已空的 bridge_subdir 子目录
            if os.path.isdir(bridge_dir) and not os.listdir(bridge_dir):
                try:
                    os.rmdir(bridge_dir)
                    print(f"{self.dcc_name} unsetup: removed empty dir {bridge_dir}")
                except OSError:
                    pass

            # 删 launcher
            launcher_name = self.get_launcher_name()
            if launcher_name:
                launcher_dir = self.get_launcher_dir(version, lang)
                if launcher_dir:
                    launcher_path = os.path.join(launcher_dir, launcher_name)
                    if os.path.exists(launcher_path):
                        try:
                            os.remove(launcher_path)
                            print(f"{self.dcc_name} unsetup: removed launcher {launcher_path}")
                        except OSError as e:
                            print(
                                f"{self.dcc_name} unsetup: failed to remove launcher {launcher_path}: {e}"
                            )

            self._post_unsetup(script_dir)
            any_success = True

        return any_success


# ==================== 模块级模板 ====================

# 默认 Python launcher 模板：放在 DCC 自动加载根目录，显式 exec 主脚本。
# 跨 Python 2/3 兼容（py2 用 execfile，py3 用 exec）；纯 ASCII，不加 # coding
# （py2 DCC 中入口文件写 # coding 会 SyntaxError，见踩坑经验库第 1 条）。
_LAUNCHER_PY_TEMPLATE = """\
# DCC Bridge launcher (auto-generated)
# Remove with: dcc unsetup {dcc_name}
import os

_bridge_script = r"{startup_script_path}"

if os.path.exists(_bridge_script):
    try:
        execfile(_bridge_script)
    except NameError:
        with open(_bridge_script, "r") as _f:
            exec(compile(_f.read(), _bridge_script, "exec"))
"""


def get_setup(dcc_name: str) -> DCCSetup | None:
    """根据 DCC 类型获取注入器实例（支持别名）"""
    from dcc_bridge.dcc_names import normalize_dcc_name

    dcc_name = normalize_dcc_name(dcc_name)

    if dcc_name == "maya":
        from .maya import MayaSetup

        return MayaSetup()
    if dcc_name == "3dsmax":
        from .max import MaxSetup

        return MaxSetup()
    if dcc_name == "substance_painter":
        from .painter import PainterSetup

        return PainterSetup()
    if dcc_name == "substance_designer":
        from .designer import DesignerSetup

        return DesignerSetup()
    if dcc_name == "houdini":
        from .houdini import HoudiniSetup

        return HoudiniSetup()
    if dcc_name == "blender":
        from .blender import BlenderSetup

        return BlenderSetup()
    return None
