"""
MaxSetup 单元测试

通过 mock 注册表方法测试每个公开方法，setup/unsetup 额外 mock expanduser 指向临时目录。
"""

from __future__ import annotations

import os

import pytest

from dcc_bridge.setup.base import DCCInstallation, get_setup
from dcc_bridge.setup.max import MaxSetup, MAX_REG_BASE


# ==================== fixture ====================

@pytest.fixture
def mock_registry(monkeypatch):
    """
    模拟注册表，返回 (values, subkeys) 字典供测试修改

    values:   {reg_path: {value_name: value_str}}
    subkeys:  {reg_path: [subkey1, subkey2, ...]}
    """
    values: dict = {}
    subkeys: dict = {}

    def mock_read(self, reg_path, value_name):
        return values.get(reg_path, {}).get(value_name)

    def mock_enum(self, reg_path):
        return subkeys.get(reg_path, [])

    monkeypatch.setattr(MaxSetup, "_read_registry_value", mock_read)
    monkeypatch.setattr(MaxSetup, "_enum_registry_subkeys", mock_enum)

    return values, subkeys


@pytest.fixture
def populated_registry(mock_registry):
    """预填充 3ds Max 2019 (21.0) + 2024 (26.0) 的注册表数据"""
    values, subkeys = mock_registry
    subkeys[MAX_REG_BASE] = ["21.0", "26.0", "not_a_version"]
    values[f"{MAX_REG_BASE}\\21.0"] = {
        "Installdir": r"C:\Program Files\Autodesk\3ds Max 2019\\",
    }
    values[f"{MAX_REG_BASE}\\26.0"] = {
        "Installdir": r"C:\Program Files\Autodesk\3ds Max 2024\\",
    }
    return mock_registry


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """将 ~ 指向临时目录，用于 setup/unsetup 文件操作"""
    monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path))
    return tmp_path


@pytest.fixture
def setup_instance():
    return MaxSetup()


# ==================== discover_versions ====================

class TestDiscoverVersions:
    def test_finds_installed_versions(self, setup_instance, populated_registry):
        """应发现 2019 和 2024 两个版本"""
        versions = setup_instance.discover_versions()
        assert "2019" in versions
        assert "2024" in versions

    def test_returns_sorted(self, setup_instance, populated_registry):
        """结果应排序"""
        versions = setup_instance.discover_versions()
        assert versions == sorted(versions)

    def test_filters_non_version_subkeys(self, setup_instance, populated_registry):
        """不应包含 not_a_version"""
        versions = setup_instance.discover_versions()
        assert "not_a_version" not in versions

    def test_ignores_subkeys_without_installdir(self, setup_instance, mock_registry):
        """没有 Installdir 值的子键应被忽略"""
        values, subkeys = mock_registry
        subkeys[MAX_REG_BASE] = ["26.0", "bad"]
        values[f"{MAX_REG_BASE}\\26.0"] = {
            "Installdir": r"C:\Program Files\Autodesk\3ds Max 2024\\",
        }
        # bad 没有 Installdir
        versions = setup_instance.discover_versions()
        assert "2024" in versions
        assert len(versions) == 1

    def test_returns_empty_when_no_registry(self, setup_instance, mock_registry):
        """注册表为空时返回空列表"""
        assert setup_instance.discover_versions() == []

    def test_returns_empty_when_no_max_key(self, setup_instance, mock_registry):
        """注册表中没有 3dsMax 键时返回空列表"""
        _, subkeys = mock_registry
        subkeys["SOFTWARE\\SomeOther"] = ["26.0"]
        assert setup_instance.discover_versions() == []


# ==================== get_install_path ====================

class TestGetInstallPath:
    def test_returns_path_for_existing_version(self, setup_instance, populated_registry):
        """已安装版本应返回安装路径"""
        path = setup_instance.get_install_path("2024")
        assert path is not None
        assert "3ds Max 2024" in path

    def test_returns_path_for_2019(self, setup_instance, populated_registry):
        """2019 版本也能正确获取"""
        path = setup_instance.get_install_path("2019")
        assert path is not None
        assert "3ds Max 2019" in path

    def test_returns_none_for_nonexistent_version(self, setup_instance, populated_registry):
        """未安装版本应返回 None"""
        assert setup_instance.get_install_path("2099") is None

    def test_returns_none_when_no_registry(self, setup_instance, mock_registry):
        """注册表为空时返回 None"""
        assert setup_instance.get_install_path("2024") is None


# ==================== get_script_dir ====================

class TestGetScriptDir:
    def test_returns_dir_for_existing_version(self, setup_instance, populated_registry, mock_home):
        """已安装版本应返回 startup 目录"""
        result = setup_instance.get_script_dir("2024")
        assert result is not None
        assert result.endswith(os.path.join("scripts", "startup"))

    def test_constructs_correct_path_format(self, setup_instance, populated_registry, mock_home):
        """路径中应包含 '<year> - 64bit' 格式"""
        result = setup_instance.get_script_dir("2024")
        assert result is not None
        assert "2024 - 64bit" in result

    def test_returns_none_for_nonexistent_version(self, setup_instance, populated_registry, mock_home):
        """未安装版本应返回 None"""
        assert setup_instance.get_script_dir("1999") is None

    def test_auto_discovers_when_no_version(self, setup_instance, populated_registry, mock_home):
        """不指定版本时自动发现并返回第一个"""
        result = setup_instance.get_script_dir()
        assert result is not None
        assert "startup" in result

    def test_returns_none_when_nothing_installed(self, setup_instance, mock_registry, mock_home):
        """没有安装时返回 None"""
        assert setup_instance.get_script_dir() is None


# ==================== get_startup_script_name ====================

class TestGetStartupScriptName:
    def test_returns_correct_name(self, setup_instance):
        """应返回 dcc_bridge_startup.py"""
        assert setup_instance.get_startup_script_name() == "dcc_bridge_startup.py"


# ==================== get_startup_script_content ====================

class TestGetStartupScriptContent:
    def test_contains_dcc_name(self, setup_instance):
        """内容应包含 3dsmax 标识"""
        assert "3dsmax" in setup_instance.get_startup_script_content()

    def test_contains_start_server(self, setup_instance):
        """内容应包含 start_server 调用"""
        assert "start_server" in setup_instance.get_startup_script_content()

    def test_contains_dcc_bridge_path(self, setup_instance):
        """内容应包含 sys.path 注入和 dcc_bridge 导入"""
        content = setup_instance.get_startup_script_content()
        assert "sys.path.insert" in content
        assert "from dcc_bridge.start import start_server" in content


# ==================== detect_installations ====================

class TestDetectInstallations:
    def test_returns_installations_for_all_versions(self, setup_instance, populated_registry):
        """应返回 2019 和 2024 两个安装"""
        installations = setup_instance.detect_installations()
        versions = [inst.version for inst in installations]
        assert "2019" in versions
        assert "2024" in versions

    def test_installation_has_correct_dcc_name(self, setup_instance, populated_registry):
        """dcc_name 应为 3dsmax"""
        for inst in setup_instance.detect_installations():
            assert inst.dcc_name == "3dsmax"

    def test_installation_root_path_from_registry(self, setup_instance, populated_registry):
        """root_path 应为注册表中的安装路径"""
        installations = setup_instance.detect_installations()
        for inst in installations:
            assert "Autodesk" in inst.root_path
            assert inst.version in inst.root_path

    def test_returns_empty_when_nothing_installed(self, setup_instance, mock_registry):
        """没有安装时返回空列表"""
        assert setup_instance.detect_installations() == []


# ==================== get_startup_script_path ====================

class TestGetStartupScriptPath:
    def test_returns_full_path(self, setup_instance, populated_registry, mock_home):
        """应返回 startup 目录下的 dcc_bridge_startup.py"""
        path = setup_instance.get_startup_script_path("2024")
        assert path is not None
        assert path.endswith(os.path.join("startup", "dcc_bridge_startup.py"))

    def test_returns_none_for_nonexistent(self, setup_instance, populated_registry, mock_home):
        """版本不存在时返回 None"""
        assert setup_instance.get_startup_script_path("1999") is None


# ==================== setup ====================

class TestSetup:
    def test_writes_startup_script(self, setup_instance, populated_registry, mock_home):
        """setup 后应存在 dcc_bridge_startup.py"""
        assert setup_instance.setup("2024") is True
        script_path = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "ENU" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert script_path.exists()

    def test_script_content_correct(self, setup_instance, populated_registry, mock_home):
        """写入的脚本内容应包含 3dsmax 和 start_server"""
        setup_instance.setup("2024")
        script_path = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "ENU" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        content = script_path.read_text(encoding="utf-8")
        assert "3dsmax" in content
        assert "start_server" in content

    def test_returns_false_for_nonexistent_version(self, setup_instance, populated_registry, mock_home):
        """版本不存在时返回 False"""
        assert setup_instance.setup("1999") is False

    def test_idempotent_setup(self, setup_instance, populated_registry, mock_home):
        """多次 setup 应覆盖写入，不报错"""
        assert setup_instance.setup("2024") is True
        assert setup_instance.setup("2024") is True

    def test_setup_creates_directory_if_not_exists(self, setup_instance, populated_registry, mock_home):
        """目录不存在时应自动创建"""
        startup_dir = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "ENU" / "scripts" / "startup"
        )
        assert not startup_dir.exists()

        setup_instance.setup("2024")
        assert startup_dir.exists()


# ==================== unsetup ====================

class TestUnsetup:
    def test_removes_startup_script(self, setup_instance, populated_registry, mock_home):
        """unsetup 后应删除 dcc_bridge_startup.py"""
        setup_instance.setup("2024")
        script_path = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "ENU" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert script_path.exists()

        assert setup_instance.unsetup("2024") is True
        assert not script_path.exists()

    def test_returns_true_when_script_not_found(self, setup_instance, populated_registry, mock_home):
        """脚本不存在时仍返回 True"""
        assert setup_instance.unsetup("2024") is True

    def test_returns_false_for_nonexistent_version(self, setup_instance, populated_registry, mock_home):
        """版本不存在时返回 False"""
        assert setup_instance.unsetup("1999") is False

    def test_unsetup_after_setup_roundtrip(self, setup_instance, populated_registry, mock_home):
        """setup -> unsetup 往返后脚本应不存在"""
        setup_instance.setup("2024")
        setup_instance.unsetup("2024")
        script_path = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "ENU" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert not script_path.exists()

    def test_unsetup_does_not_remove_other_scripts(self, setup_instance, populated_registry, mock_home):
        """unsetup 不应删除 startup 目录中的其他脚本"""
        setup_instance.setup("2024")
        startup_dir = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "ENU" / "scripts" / "startup"
        )
        other_script = startup_dir / "my_other_script.py"
        other_script.write_text("print('keep me')", encoding="utf-8")

        setup_instance.unsetup("2024")
        assert other_script.exists()
        assert "keep me" in other_script.read_text(encoding="utf-8")


# ==================== 多版本 setup / unsetup ====================

class TestMultiVersionSetup:
    def test_setup_all_versions_when_no_version_specified(self, setup_instance, populated_registry, mock_home):
        """不指定版本时应只为 2021+ 的版本注入脚本（2019 应被跳过）"""
        assert setup_instance.setup() is True
        # 2024 应被注入
        script_2024 = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "ENU" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert script_2024.exists()
        # 2019 应被跳过（低于 min_supported_version）
        script_2019 = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2019 - 64bit" / "ENU" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert not script_2019.exists()

    def test_unsetup_all_versions_when_no_version_specified(self, setup_instance, populated_registry, mock_home):
        """不指定版本时应只移除 2021+ 的版本脚本"""
        setup_instance.setup()
        assert setup_instance.unsetup() is True
        script_2024 = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "ENU" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert not script_2024.exists()

    def test_returns_false_when_no_versions_installed(self, setup_instance, mock_registry, mock_home):
        """没有已安装版本时返回 False"""
        assert setup_instance.setup() is False

    def test_explicit_version_below_min_still_works(self, setup_instance, populated_registry, mock_home):
        """指定 --version 2019 时即使低于 min_supported_version 也应正常注入"""
        assert setup_instance.setup("2019") is True
        script_2019 = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2019 - 64bit" / "ENU" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert script_2019.exists()

    def test_partial_failure_returns_false(self, setup_instance, populated_registry, mock_home):
        """部分版本失败时返回 False，但其他版本仍成功"""
        original = setup_instance.get_script_dir
        def mock_get_script_dir(version=None, language="en"):
            if version == "2024":
                return None
            return original(version, language)
        setup_instance.get_script_dir = mock_get_script_dir

        result = setup_instance.setup()
        assert result is False  # 2024 失败


class TestGetTargetVersions:
    """测试 _get_target_versions 的版本过滤逻辑"""

    def test_filters_below_min_supported(self, setup_instance, populated_registry):
        """不指定版本时应过滤掉低于 min_supported_version 的版本"""
        versions = setup_instance._get_target_versions()
        assert "2024" in versions
        assert "2019" not in versions

    def test_explicit_version_not_filtered(self, setup_instance, populated_registry):
        """指定版本时不应用过滤"""
        versions = setup_instance._get_target_versions("2019")
        assert versions == ["2019"]

    def test_returns_empty_when_all_below_min(self, setup_instance, mock_registry):
        """所有版本都低于 min_supported_version 时返回空列表"""
        values, subkeys = mock_registry
        subkeys[MAX_REG_BASE] = ["19.0"]
        values[f"{MAX_REG_BASE}\\19.0"] = {
            "Installdir": r"C:\Program Files\Autodesk\3ds Max 2017\\",
        }
        assert setup_instance._get_target_versions() == []


# ==================== get_setup 工厂函数 ====================

class TestGetSetupFactory:
    def test_returns_max_setup_for_3dsmax(self):
        """get_setup('3dsmax') 应返回 MaxSetup 实例"""
        assert isinstance(get_setup("3dsmax"), MaxSetup)

    def test_returns_max_setup_for_max(self):
        """get_setup('max') 也应返回 MaxSetup 实例"""
        assert isinstance(get_setup("max"), MaxSetup)

    def test_returns_none_for_unknown(self):
        """get_setup('unknown') 应返回 None"""
        assert get_setup("unknown") is None


# ==================== 多语言支持 ====================

class TestMultiLanguage:
    def test_get_script_dir_en_returns_enu(self, setup_instance, populated_registry, mock_home):
        """英文路径应包含 ENU"""
        result = setup_instance.get_script_dir("2024", "en")
        assert result is not None
        assert "ENU" in result

    def test_get_script_dir_zh_cn_returns_chs(self, setup_instance, populated_registry, mock_home):
        """中文路径应包含 CHS"""
        result = setup_instance.get_script_dir("2024", "zh_CN")
        assert result is not None
        assert "CHS" in result

    def test_get_script_dir_unknown_language_fallback_en(self, setup_instance, populated_registry, mock_home):
        """未知语言应回退为英文 ENU"""
        result = setup_instance.get_script_dir("2024", "ja")
        assert result is not None
        assert "ENU" in result

    def test_setup_writes_both_languages(self, setup_instance, populated_registry, mock_home):
        """setup 应同时写入 ENU 和 CHS 两个目录"""
        assert setup_instance.setup("2024") is True
        enu_script = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "ENU" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        chs_script = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "CHS" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert enu_script.exists()
        assert chs_script.exists()

    def test_unsetup_removes_both_languages(self, setup_instance, populated_registry, mock_home):
        """unsetup 应同时移除 ENU 和 CHS 两个目录的脚本"""
        setup_instance.setup("2024")
        assert setup_instance.unsetup("2024") is True
        enu_script = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "ENU" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        chs_script = (
            mock_home / "AppData" / "Local" / "Autodesk" / "3dsMax"
            / "2024 - 64bit" / "CHS" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert not enu_script.exists()
        assert not chs_script.exists()

    def test_get_supported_languages_default(self, setup_instance):
        """默认应支持 en 和 zh_CN"""
        langs = setup_instance.get_supported_languages()
        assert "en" in langs
        assert "zh_CN" in langs
