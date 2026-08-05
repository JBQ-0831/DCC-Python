"""
Maya 自启动注入器

通过注册表获取已安装版本与安装路径，直接拼接用户脚本目录。
仅实现 Maya 特有的注册表路径与 userSetup.py 钩子逻辑。
"""

from __future__ import annotations

import os
import re

from dcc_bridge.setup.base import DCCSetup

# Maya 注册表基路径
MAYA_REG_BASE = r"SOFTWARE\Autodesk\Maya"

# userSetup.py 中追加的 exec 启动块标记（用于整块插入/删除）。
# 主脚本位于 scripts/dcc_bridge/dcc_bridge_startup.py（隔离子目录，避免被
# Maya 递归自动执行导致双启动），userSetup.py 在主线程早期显式 exec 它。
# 该块需跨 py2/py3 兼容（Maya <=2020 为 py2），且不加 # coding（py2 入口禁写）。
_BLOCK_START = "# >>> dcc-bridge auto-start (added by `dcc setup maya`) >>>"
_BLOCK_END = "# <<< dcc-bridge auto-start end <<<"

# exec 启动块主体：主脚本绝对路径由 _post_setup 计算后写死进块内，
# 不依赖 __file__（Maya 把 userSetup.py 当脚本 exec 进内置命名空间，无 __file__）。
# py2 用 execfile、py3 用 exec(compile())，纯 ASCII。
_EXEC_BLOCK_BODY_TMPL = '''\
import os as _db_os
_db_script = r"{main_script}"
if _db_os.path.exists(_db_script):
    try:
        execfile(_db_script)
    except NameError:
        with open(_db_script, "r") as _db_f:
            exec(compile(_db_f.read(), _db_script, "exec"))
'''

# 版本号匹配：2022、2024 等
_VERSION_PATTERN = re.compile(r"^20\d{2}$")


# Maya 安装路径可能的值名称（不同版本可能不同）
_INSTALL_PATH_KEYS = ("MAYA_INSTALL_LOCATION", "InstallLocation", "")


class MayaSetup(DCCSetup):
    """
    Maya 自启动注入器

    注册表路径：HKLM\\SOFTWARE\\Autodesk\\Maya\\<version>
    安装路径：  HKLM\\SOFTWARE\\Autodesk\\Maya\\<version>\\Setup\\InstallPath
    脚本目录：  ~/maya/<version>/scripts/
    主脚本：    scripts/dcc_bridge/dcc_bridge_startup.py（隔离子目录）
    启动方式：  scripts/userSetup.py 中追加 exec 块显式启动主脚本
               （Maya 不写独立 launcher 文件，get_launcher_name 返回 None）
    """

    dcc_name = "maya"
    # 仅支持 2018+ 的 Maya
    min_supported_version = "2018"

    def should_defer_start(self) -> bool:
        """Maya 在 userSetup.py 阶段内核尚未完全就绪，
        cmds.about(version=True) 等依赖完整内核的 API 会抛异常，
        因此延迟到 Maya 完全初始化（idle）后再启动服务。
        """
        return True

    def get_launcher_name(self) -> str | None:
        """Maya 不写独立 launcher 文件。

        Maya 由 scripts/userSetup.py 在启动早期显式 exec 主脚本（见
        _post_setup 注入的启动块），无需在自动加载目录放额外 launcher。
        返回 None 让基类 _setup_single 跳过写 launcher 文件。
        """
        return None

    def discover_versions(self) -> list[str]:
        """从注册表扫描已安装的 Maya 版本号"""
        subkeys = self._enum_registry_subkeys(MAYA_REG_BASE)
        versions = [s for s in subkeys if _VERSION_PATTERN.match(s)]
        return sorted(versions)

    def get_install_path(self, version: str) -> str | None:
        """从注册表获取指定版本的安装路径"""
        reg_path = f"{MAYA_REG_BASE}\\{version}\\Setup\\InstallPath"
        # 尝试已知的值名称，包括默认值（空字符串）
        for key_name in _INSTALL_PATH_KEYS:
            value = self._read_registry_value(reg_path, key_name)
            if value:
                return value
        return None

    def get_script_dir(
        self, version: str | None = None, language: str = "en"
    ) -> str | None:
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

    def get_python_path(self, version: str) -> str | None:
        """返回 Maya 指定版本的 Python 解释器路径（mayapy.exe）"""
        install_path = self.get_install_path(version)
        if install_path:
            return os.path.join(install_path, "bin", "mayapy.exe")
        return None

    def _post_setup(self, script_dir: str) -> None:
        """setup 完成后在 userSetup.py 中追加 exec 启动块（写死主脚本绝对路径）"""
        main_script = os.path.join(
            script_dir, self.bridge_subdir, self.get_startup_script_name()
        )
        # 先移除旧块（幂等），再写入带最新绝对路径的新块，
        # 保证升级 Maya 版本后重跑 setup 时路径被刷新。
        _remove_block_from_file(
            file_path=os.path.join(script_dir, "userSetup.py"),
            dcc_label="Maya",
        )
        _ensure_block_in_file(
            file_path=os.path.join(script_dir, "userSetup.py"),
            body=_EXEC_BLOCK_BODY_TMPL.format(main_script=main_script),
            dcc_label="Maya",
        )

    def _post_unsetup(self, script_dir: str) -> None:
        """unsetup 完成后从 userSetup.py 中移除 exec 启动块"""
        _remove_block_from_file(
            file_path=os.path.join(script_dir, "userSetup.py"),
            dcc_label="Maya",
        )


# ==================== 模块级辅助函数 ====================


def _ensure_block_in_file(file_path: str, body: str, dcc_label: str) -> None:
    """在指定文件末尾追加一段由标记包裹的启动块，已存在则跳过。

    body 为启动块主体（多行字符串，不含起止标记）。
    """
    existing_lines: list[str] = []
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    # 已存在标记则跳过（避免重复注入）
    if any(_BLOCK_START in line for line in existing_lines):
        print(f"{dcc_label} setup: auto-start block already present in {file_path}")
        return

    block_lines = [_BLOCK_START + "\n", body, _BLOCK_END + "\n"]

    # 确保原有内容末尾有换行，再追加启动块
    if existing_lines and not existing_lines[-1].endswith("\n"):
        existing_lines[-1] += "\n"

    existing_lines.extend(block_lines)
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(existing_lines)
    print(f"{dcc_label} setup: updated {file_path}")


def _remove_block_from_file(file_path: str, dcc_label: str) -> None:
    """从指定文件中移除由标记包裹的整段启动块（含起止标记行）"""
    if not os.path.exists(file_path):
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return

    out: list[str] = []
    skip = False
    removed = False
    for line in lines:
        if _BLOCK_START in line:
            skip = True
            removed = True
            continue
        if _BLOCK_END in line:
            skip = False
            continue
        if not skip:
            out.append(line)

    if removed:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(out)
        print(f"{dcc_label} unsetup: removed auto-start block from {file_path}")
    else:
        print(f"{dcc_label} unsetup: no auto-start block found in {file_path}")
