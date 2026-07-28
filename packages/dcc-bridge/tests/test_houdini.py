"""
HoudiniSetup 单元测试

通过 mock 注册表方法测试每个公开方法，setup/unsetup 额外 mock expanduser 指向临时目录。
get_python_path / get_script_dir 依赖目录枚举 (os.listdir) 与运行 python 解释器 (subprocess)，
这里用 mock_python_env 伪造这些行为，并把 install_debugpy 替换为空操作以免触发真实 pip。
"""

from __future__ import annotations

import os
import subprocess

import pytest

import dcc_bridge.setup.houdini as houdini
from dcc_bridge.setup.base import DCCInstallation, get_setup
from dcc_bridge.setup.houdini import (
    HOUDINI_PYTHON_LIBS_SUFFIX,
    HOUDINI_REG_BASE,
    HoudiniSetup,
)


# ==================== fixture ====================

@pytest.fixture
def mock_registry(monkeypatch):
    """
    模拟注册表，返回 (values, subkeys) 字典供测试修改

    values:  {reg_path: {value_name: value_str}}
    subkeys: {reg_path: [subkey1, subkey2, ...]}
    """
    values: dict = {}
    subkeys: dict = {}

    def mock_read(self, reg_path, value_name):
        return values.get(reg_path, {}).get(value_name)

    def mock_enum(self, reg_path):
        return subkeys.get(reg_path, [])

    monkeypatch.setattr(HoudiniSetup, "_read_registry_value", mock_read)
    monkeypatch.setattr(HoudiniSetup, "_enum_registry_subkeys", mock_enum)

    return values, subkeys


@pytest.fixture
def populated_registry(mock_registry):
    """预填充 Houdini 19.5.773 + 22.0.368 的注册表数据"""
    values, subkeys = mock_registry
    subkeys[HOUDINI_REG_BASE] = [
        "Houdini 19.5.773",
        "Houdini 22.0.368",
        "NotHoudini",
    ]
    values[f"{HOUDINI_REG_BASE}\\Houdini 19.5.773"] = {
        "InstallPath": r"C:\Program Files\Side Effects Software\Houdini 19.5.773",
    }
    values[f"{HOUDINI_REG_BASE}\\Houdini 22.0.368"] = {
        "InstallPath": r"C:\Program Files\Side Effects Software\Houdini 22.0.368",
    }
    return mock_registry


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """将 ~ 指向临时目录，用于 setup/unsetup 文件操作"""
    monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path))
    return tmp_path


@pytest.fixture
def mock_python_env(monkeypatch):
    """
    伪造 Python 解释器探测相关的系统调用：

    - os.listdir(install_path) 返回 ["python313"]，模拟内置 python3X 目录
    - os.path.isdir / os.path.exists 恒为 True，让 get_python_path 找到候选
    - subprocess.run 返回 "3.13"，模拟 python -c 查询到的版本号
    - 将 install_debugpy 替换为空操作，避免 setup 时触发真实 pip 安装
    """
    monkeypatch.setattr(houdini.os, "listdir", lambda path: ["python313"])
    # isdir 仅对安装目录返回 True，避免破坏 os.makedirs（其内部会调用
    # os.path.exists/isdir(head) 判断父目录是否已存在）
    _real_isdir = houdini.os.path.isdir
    _real_exists = houdini.os.path.exists
    monkeypatch.setattr(
        houdini.os.path,
        "isdir",
        lambda p: ("Side Effects Software" in str(p)) or _real_isdir(p),
    )
    # exists 仅对 python.exe 候选路径返回 True（供 get_python_path 探测）
    monkeypatch.setattr(
        houdini.os.path,
        "exists",
        lambda p: str(p).endswith("python.exe") or _real_exists(p),
    )

    class _FakeResult:
        returncode = 0
        stdout = "3.13\n"
        stderr = ""

    monkeypatch.setattr(houdini.subprocess, "run", lambda *a, **k: _FakeResult())
    monkeypatch.setattr(
        "dcc_bridge.debug.install_debugpy", lambda *a, **k: None
    )


@pytest.fixture
def setup_instance():
    return HoudiniSetup()


# ==================== discover_versions ====================

class TestDiscoverVersions:
    def test_finds_installed_versions(self, setup_instance, populated_registry):
        """应发现 19.5 和 22.0（忽略补丁号）"""
        versions = setup_instance.discover_versions()
        assert "19.5" in versions
        assert "22.0" in versions

    def test_returns_sorted(self, setup_instance, populated_registry):
        """结果应排序"""
        versions = setup_instance.discover_versions()
        assert versions == sorted(versions)

    def test_filters_non_version_subkeys(self, setup_instance, populated_registry):
        """不应包含 NotHoudini 这类不符合格式的键"""
        versions = setup_instance.discover_versions()
        assert "NotHoudini" not in versions

    def test_returns_empty_when_no_registry(self, setup_instance, mock_registry):
        """注册表为空时返回空列表"""
        assert setup_instance.discover_versions() == []

    def test_returns_empty_when_no_houdini_key(self, setup_instance, mock_registry):
        """注册表中没有 Houdini 键时返回空列表"""
        _, subkeys = mock_registry
        subkeys["SOFTWARE\\SomeOther"] = ["Houdini 19.5.773"]
        assert setup_instance.discover_versions() == []


# ==================== get_install_path ====================

class TestGetInstallPath:
    def test_returns_path_for_existing_version(self, setup_instance, populated_registry):
        """已安装版本应返回安装路径"""
        path = setup_instance.get_install_path("22.0")
        assert path is not None
        assert "Houdini 22.0.368" in path

    def test_returns_path_for_19_5(self, setup_instance, populated_registry):
        """19.5 版本也能正确获取"""
        path = setup_instance.get_install_path("19.5")
        assert path is not None
        assert "Houdini 19.5.773" in path

    def test_returns_none_for_nonexistent_version(self, setup_instance, populated_registry):
        """未安装版本应返回 None"""
        assert setup_instance.get_install_path("99.9") is None

    def test_returns_none_when_no_registry(self, setup_instance, mock_registry):
        """注册表为空时返回 None"""
        assert setup_instance.get_install_path("19.5") is None


# ==================== get_python_path ====================

class TestGetPythonPath:
    def test_returns_python_exe(self, setup_instance, populated_registry, mock_python_env):
        """应拼接出 python313/python.exe"""
        result = setup_instance.get_python_path("19.5")
        assert result is not None
        assert result.endswith(os.path.join("python313", "python.exe"))

    def test_returns_none_when_install_missing(self, setup_instance, mock_registry, mock_python_env):
        """注册表无安装路径时返回 None"""
        assert setup_instance.get_python_path("19.5") is None

    def test_returns_none_when_no_python_dir(self, setup_instance, populated_registry, mock_python_env, monkeypatch):
        """安装目录下没有 python3* 目录时返回 None"""
        monkeypatch.setattr(houdini.os, "listdir", lambda path: ["bin", "houdini"])
        result = setup_instance.get_python_path("19.5")
        assert result is None


# ==================== get_script_dir ====================

class TestGetScriptDir:
    def test_returns_python_libs_dir(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """应返回 ~/Documents/houdini19.5/python3.13Libs"""
        result = setup_instance.get_script_dir("19.5")
        assert result is not None
        assert result.endswith(
            os.path.join(f"houdini19.5", f"python3.13{HOUDINI_PYTHON_LIBS_SUFFIX}")
        )

    def test_returns_none_for_nonexistent_version(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """未安装版本应返回 None"""
        assert setup_instance.get_script_dir("99.9") is None

    def test_auto_discovers_when_no_version(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """不指定版本时自动发现并返回第一个"""
        result = setup_instance.get_script_dir()
        assert result is not None
        assert "houdini" in result

    def test_returns_none_when_nothing_installed(self, setup_instance, mock_registry, mock_home, mock_python_env):
        """没有安装时返回 None"""
        assert setup_instance.get_script_dir() is None


# ==================== get_startup_script_name ====================

class TestGetStartupScriptName:
    def test_returns_uiread(self, setup_instance):
        """Houdini 启动脚本固定为 uiread.py"""
        assert setup_instance.get_startup_script_name() == "uiread.py"


# ==================== get_startup_script_content ====================

class TestGetStartupScriptContent:
    def test_contains_dcc_name(self, setup_instance):
        """内容应包含 houdini 标识"""
        assert "houdini" in setup_instance.get_startup_script_content()

    def test_contains_start_server(self, setup_instance):
        """内容应包含 start_server 调用"""
        assert "start_server" in setup_instance.get_startup_script_content()

    def test_contains_dcc_bridge_path(self, setup_instance):
        """内容应包含 sys.path 注入和 dcc_bridge 导入"""
        content = setup_instance.get_startup_script_content()
        assert "sys.path.insert" in content
        assert "from dcc_bridge.start import start_server" in content


# ==================== get_supported_languages ====================

class TestGetSupportedLanguages:
    def test_returns_only_en(self, setup_instance):
        """Houdini 的 pythonX.Ylibs 目录不随语言变化，只注入 en"""
        assert setup_instance.get_supported_languages() == ["en"]


# ==================== detect_installations ====================

class TestDetectInstallations:
    def test_returns_installations_for_all_versions(self, setup_instance, populated_registry):
        """应返回 19.5 和 22.0 两个安装"""
        installations = setup_instance.detect_installations()
        versions = [inst.version for inst in installations]
        assert "19.5" in versions
        assert "22.0" in versions

    def test_installation_has_correct_dcc_name(self, setup_instance, populated_registry):
        """dcc_name 应为 houdini"""
        for inst in setup_instance.detect_installations():
            assert inst.dcc_name == "houdini"

    def test_installation_root_path_from_registry(self, setup_instance, populated_registry):
        """root_path 应为注册表中的安装路径"""
        installations = setup_instance.detect_installations()
        for inst in installations:
            assert "Side Effects Software" in inst.root_path
            assert inst.version in inst.root_path

    def test_returns_empty_when_nothing_installed(self, setup_instance, mock_registry):
        """没有安装时返回空列表"""
        assert setup_instance.detect_installations() == []


# ==================== get_startup_script_path ====================

class TestGetStartupScriptPath:
    def test_returns_full_path(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """应返回 pythonX.Ylibs 目录下的 uiread.py"""
        path = setup_instance.get_startup_script_path("19.5")
        assert path is not None
        assert path.endswith(os.path.join(f"python3.13{HOUDINI_PYTHON_LIBS_SUFFIX}", "uiread.py"))

    def test_returns_none_for_nonexistent(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """版本不存在时返回 None"""
        assert setup_instance.get_startup_script_path("99.9") is None


# ==================== setup ====================

class TestSetup:
    def test_writes_startup_script(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """setup 后应存在 uiread.py"""
        assert setup_instance.setup("19.5") is True
        script_path = (
            mock_home / "Documents" / "houdini19.5"
            / f"python3.13{HOUDINI_PYTHON_LIBS_SUFFIX}" / "uiread.py"
        )
        assert script_path.exists()

    def test_script_content_correct(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """写入的脚本内容应包含 houdini 和 start_server"""
        setup_instance.setup("19.5")
        script_path = (
            mock_home / "Documents" / "houdini19.5"
            / f"python3.13{HOUDINI_PYTHON_LIBS_SUFFIX}" / "uiread.py"
        )
        content = script_path.read_text(encoding="utf-8")
        assert "houdini" in content
        assert "start_server" in content

    def test_idempotent_setup(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """多次 setup 应覆盖写入，不报错"""
        assert setup_instance.setup("19.5") is True
        assert setup_instance.setup("19.5") is True

    def test_returns_false_for_nonexistent_version(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """版本不存在时返回 False"""
        assert setup_instance.setup("99.9") is False

    def test_setup_all_versions_when_no_version_specified(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """不指定版本时应为所有 19.0+ 的已安装版本注入脚本"""
        assert setup_instance.setup() is True
        for ver, py in (("19.5", "3.13"), ("22.0", "3.13")):
            script_path = (
                mock_home / "Documents" / f"houdini{ver}"
                / f"python{py}{HOUDINI_PYTHON_LIBS_SUFFIX}" / "uiread.py"
            )
            assert script_path.exists(), f"startup script not found for {ver}"


# ==================== unsetup ====================

class TestUnsetup:
    def test_removes_startup_script(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """unsetup 后应删除 uiread.py"""
        setup_instance.setup("19.5")
        script_path = (
            mock_home / "Documents" / "houdini19.5"
            / f"python3.13{HOUDINI_PYTHON_LIBS_SUFFIX}" / "uiread.py"
        )
        assert script_path.exists()

        assert setup_instance.unsetup("19.5") is True
        assert not script_path.exists()

    def test_returns_true_when_script_not_found(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """脚本不存在时仍返回 True"""
        assert setup_instance.unsetup("19.5") is True

    def test_returns_false_for_nonexistent_version(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """版本不存在时返回 False"""
        assert setup_instance.unsetup("99.9") is False

    def test_unsetup_after_setup_roundtrip(self, setup_instance, populated_registry, mock_home, mock_python_env):
        """setup -> unsetup 往返后脚本应不存在"""
        setup_instance.setup("19.5")
        setup_instance.unsetup("19.5")
        script_path = (
            mock_home / "Documents" / "houdini19.5"
            / f"python3.13{HOUDINI_PYTHON_LIBS_SUFFIX}" / "uiread.py"
        )
        assert not script_path.exists()


# ==================== 版本过滤 ====================

class TestGetTargetVersions:
    def test_filters_below_min_supported(self, setup_instance, populated_registry):
        """不指定版本时应过滤掉低于 min_supported_version (19.0) 的版本"""
        values, subkeys = populated_registry
        subkeys[HOUDINI_REG_BASE].append("Houdini 18.5.123")
        values[f"{HOUDINI_REG_BASE}\\Houdini 18.5.123"] = {
            "InstallPath": r"C:\Program Files\Side Effects Software\Houdini 18.5.123",
        }
        versions = setup_instance.discover_versions()
        assert "18.5" in versions  # discover 返回全部
        target = setup_instance._get_target_versions()
        assert "18.5" not in target
        assert "19.5" in target
        assert "22.0" in target

    def test_explicit_version_not_filtered(self, setup_instance, populated_registry):
        """指定版本时不应用过滤"""
        versions = setup_instance._get_target_versions("18.5")
        assert versions == ["18.5"]


# ==================== get_setup 工厂函数 ====================

class TestGetSetupFactory:
    def test_returns_houdini_setup_for_houdini(self):
        """get_setup('houdini') 应返回 HoudiniSetup 实例"""
        assert isinstance(get_setup("houdini"), HoudiniSetup)

    def test_returns_houdini_setup_for_alias(self):
        """get_setup('h') / get_setup('sidefx') 也应返回 HoudiniSetup 实例"""
        assert isinstance(get_setup("h"), HoudiniSetup)
        assert isinstance(get_setup("sidefx"), HoudiniSetup)

    def test_returns_none_for_unknown(self):
        """get_setup('unknown') 应返回 None"""
        assert get_setup("unknown") is None
