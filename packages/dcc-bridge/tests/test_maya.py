"""
MayaSetup 单元测试

通过 mock 注册表方法测试每个公开方法，setup/unsetup 额外 mock expanduser 指向临时目录。
"""

from __future__ import annotations

import os

import pytest

from dcc_bridge.setup.base import DCCInstallation, get_setup
from dcc_bridge.setup.maya import MayaSetup, STARTUP_MODULE_NAME, MAYA_REG_BASE


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

    monkeypatch.setattr(MayaSetup, "_read_registry_value", mock_read)
    monkeypatch.setattr(MayaSetup, "_enum_registry_subkeys", mock_enum)

    return values, subkeys


@pytest.fixture
def populated_registry(mock_registry):
    """预填充 Maya 2022 + 2024 的注册表数据"""
    values, subkeys = mock_registry
    subkeys[MAYA_REG_BASE] = ["2022", "2024", "Setup", "not_a_version"]
    values[f"{MAYA_REG_BASE}\\2022\\Setup\\InstallPath"] = {
        "MAYA_INSTALL_LOCATION": r"C:\Program Files\Autodesk\Maya2022\\",
    }
    values[f"{MAYA_REG_BASE}\\2024\\Setup\\InstallPath"] = {
        "MAYA_INSTALL_LOCATION": r"C:\Program Files\Autodesk\Maya2024\\",
    }
    return mock_registry


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """将 ~ 指向临时目录，用于 setup/unsetup 文件操作"""
    monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path))
    return tmp_path


@pytest.fixture
def setup_instance():
    return MayaSetup()


# ==================== discover_versions ====================

class TestDiscoverVersions:
    def test_finds_installed_versions(self, setup_instance, populated_registry):
        """应发现 2022 和 2024"""
        versions = setup_instance.discover_versions()
        assert "2022" in versions
        assert "2024" in versions

    def test_returns_sorted(self, setup_instance, populated_registry):
        """结果应排序"""
        versions = setup_instance.discover_versions()
        assert versions == sorted(versions)

    def test_filters_non_version_subkeys(self, setup_instance, populated_registry):
        """不应包含 Setup、not_a_version 等"""
        versions = setup_instance.discover_versions()
        assert "Setup" not in versions
        assert "not_a_version" not in versions

    def test_returns_empty_when_no_registry(self, setup_instance, mock_registry):
        """注册表为空时返回空列表"""
        assert setup_instance.discover_versions() == []

    def test_returns_empty_when_no_maya_key(self, setup_instance, mock_registry):
        """注册表中没有 Maya 键时返回空列表"""
        _, subkeys = mock_registry
        subkeys["SOFTWARE\\SomeOther"] = ["2024"]
        assert setup_instance.discover_versions() == []


# ==================== get_install_path ====================

class TestGetInstallPath:
    def test_returns_path_for_existing_version(self, setup_instance, populated_registry):
        """已安装版本应返回安装路径"""
        path = setup_instance.get_install_path("2024")
        assert path is not None
        assert "Maya2024" in path

    def test_returns_none_for_nonexistent_version(self, setup_instance, populated_registry):
        """未安装版本应返回 None"""
        assert setup_instance.get_install_path("1999") is None

    def test_returns_none_when_no_registry(self, setup_instance, mock_registry):
        """注册表为空时返回 None"""
        assert setup_instance.get_install_path("2024") is None

    def test_fallback_to_default_value(self, setup_instance, mock_registry):
        """当 MAYA_INSTALL_LOCATION 不存在时尝试默认值"""
        values, subkeys = mock_registry
        subkeys[MAYA_REG_BASE] = ["2024"]
        values[f"{MAYA_REG_BASE}\\2024\\Setup\\InstallPath"] = {
            "": r"C:\Maya2024",  # 默认值
        }
        path = setup_instance.get_install_path("2024")
        assert path is not None
        assert "Maya2024" in path


# ==================== get_script_dir ====================

class TestGetScriptDir:
    def test_returns_dir_for_existing_version(self, setup_instance, populated_registry, mock_home):
        """已安装版本应返回 scripts 目录"""
        result = setup_instance.get_script_dir("2024")
        assert result is not None
        assert result.endswith(os.path.join("maya", "2024", "scripts"))

    def test_returns_none_for_nonexistent_version(self, setup_instance, populated_registry, mock_home):
        """未安装版本应返回 None"""
        assert setup_instance.get_script_dir("1999") is None

    def test_auto_discovers_when_no_version(self, setup_instance, populated_registry, mock_home):
        """不指定版本时自动发现并返回第一个"""
        result = setup_instance.get_script_dir()
        assert result is not None
        assert "scripts" in result

    def test_returns_none_when_nothing_installed(self, setup_instance, mock_registry, mock_home):
        """没有安装时返回 None"""
        assert setup_instance.get_script_dir() is None

    def test_returns_none_when_version_not_in_registry(self, setup_instance, populated_registry, mock_home):
        """版本在注册表中不存在时返回 None"""
        assert setup_instance.get_script_dir("2099") is None


# ==================== get_startup_script_name ====================

class TestGetStartupScriptName:
    def test_returns_correct_name(self, setup_instance):
        """应返回 dcc_bridge_startup.py"""
        assert setup_instance.get_startup_script_name() == "dcc_bridge_startup.py"


# ==================== get_startup_script_content ====================

class TestGetStartupScriptContent:
    def test_contains_dcc_type(self, setup_instance):
        """内容应包含 maya 标识"""
        assert "maya" in setup_instance.get_startup_script_content()

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
        """应返回 2022 和 2025 两个安装"""
        installations = setup_instance.detect_installations()
        versions = [inst.version for inst in installations]
        assert "2022" in versions
        assert "2024" in versions

    def test_installation_has_correct_dcc_type(self, setup_instance, populated_registry):
        """dcc_type 应为 maya"""
        for inst in setup_instance.detect_installations():
            assert inst.dcc_type == "maya"

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
        """应返回 scripts 目录下的 dcc_bridge_startup.py"""
        path = setup_instance.get_startup_script_path("2024")
        assert path is not None
        assert path.endswith(os.path.join("scripts", "dcc_bridge_startup.py"))

    def test_returns_none_for_nonexistent(self, setup_instance, populated_registry, mock_home):
        """版本不存在时返回 None"""
        assert setup_instance.get_startup_script_path("1999") is None


# ==================== setup ====================

class TestSetup:
    def test_writes_startup_script(self, setup_instance, populated_registry, mock_home):
        """setup 后应存在 dcc_bridge_startup.py"""
        assert setup_instance.setup("2024") is True
        script_path = mock_home / "Documents" / "maya" / "2024" / "scripts" / "dcc_bridge_startup.py"
        assert script_path.exists()

    def test_script_content_correct(self, setup_instance, populated_registry, mock_home):
        """写入的脚本内容应包含 maya 和 start_server"""
        setup_instance.setup("2024")
        script_path = mock_home / "Documents" / "maya" / "2024" / "scripts" / "dcc_bridge_startup.py"
        content = script_path.read_text(encoding="utf-8")
        assert "maya" in content
        assert "start_server" in content

    def test_modifies_user_setup(self, setup_instance, populated_registry, mock_home):
        """setup 后 userSetup.py 应包含 import 行"""
        setup_instance.setup("2024")
        usersetup = mock_home / "Documents" / "maya" / "2024" / "scripts" / "userSetup.py"
        assert usersetup.exists()
        assert f"import {STARTUP_MODULE_NAME}" in usersetup.read_text(encoding="utf-8")

    def test_idempotent_user_setup(self, setup_instance, populated_registry, mock_home):
        """多次 setup 不应重复添加 import 行"""
        setup_instance.setup("2024")
        setup_instance.setup("2024")
        usersetup = mock_home / "Documents" / "maya" / "2024" / "scripts" / "userSetup.py"
        content = usersetup.read_text(encoding="utf-8")
        assert content.count(f"import {STARTUP_MODULE_NAME}") == 1

    def test_preserves_existing_user_setup_content(self, setup_instance, populated_registry, mock_home):
        """setup 应保留 userSetup.py 中的已有内容"""
        usersetup = mock_home / "Documents" / "maya" / "2024" / "scripts" / "userSetup.py"
        usersetup.parent.mkdir(parents=True, exist_ok=True)
        usersetup.write_text("print('existing')\n", encoding="utf-8")

        setup_instance.setup("2024")
        content = usersetup.read_text(encoding="utf-8")
        assert "print('existing')" in content
        assert f"import {STARTUP_MODULE_NAME}" in content

    def test_returns_false_for_nonexistent_version(self, setup_instance, populated_registry, mock_home):
        """版本不存在时返回 False"""
        assert setup_instance.setup("1999") is False

    def test_appends_to_user_setup_without_newline(self, setup_instance, populated_registry, mock_home):
        """userSetup.py 末尾无换行时应自动补换行再追加"""
        usersetup = mock_home / "Documents" / "maya" / "2024" / "scripts" / "userSetup.py"
        usersetup.parent.mkdir(parents=True, exist_ok=True)
        usersetup.write_text("print('no newline')", encoding="utf-8")

        setup_instance.setup("2024")
        content = usersetup.read_text(encoding="utf-8")
        lines = content.split("\n")
        assert "print('no newline')" in lines[0]
        assert f"import {STARTUP_MODULE_NAME}" in lines[1]


# ==================== unsetup ====================

class TestUnsetup:
    def test_removes_startup_script(self, setup_instance, populated_registry, mock_home):
        """unsetup 后应删除 dcc_bridge_startup.py"""
        setup_instance.setup("2024")
        script_path = mock_home / "Documents" / "maya" / "2024" / "scripts" / "dcc_bridge_startup.py"
        assert script_path.exists()

        assert setup_instance.unsetup("2024") is True
        assert not script_path.exists()

    def test_removes_import_from_user_setup(self, setup_instance, populated_registry, mock_home):
        """unsetup 后 userSetup.py 中不应再有 import 行"""
        setup_instance.setup("2024")
        usersetup = mock_home / "Documents" / "maya" / "2024" / "scripts" / "userSetup.py"
        assert f"import {STARTUP_MODULE_NAME}" in usersetup.read_text(encoding="utf-8")

        setup_instance.unsetup("2024")
        assert f"import {STARTUP_MODULE_NAME}" not in usersetup.read_text(encoding="utf-8")

    def test_preserves_other_user_setup_content(self, setup_instance, populated_registry, mock_home):
        """unsetup 应保留 userSetup.py 中的其他内容"""
        usersetup = mock_home / "Documents" / "maya" / "2024" / "scripts" / "userSetup.py"
        usersetup.parent.mkdir(parents=True, exist_ok=True)
        usersetup.write_text("print('keep me')\n", encoding="utf-8")

        setup_instance.setup("2024")
        setup_instance.unsetup("2024")

        content = usersetup.read_text(encoding="utf-8")
        assert "print('keep me')" in content
        assert f"import {STARTUP_MODULE_NAME}" not in content

    def test_returns_true_when_script_not_found(self, setup_instance, populated_registry, mock_home):
        """脚本不存在时仍返回 True"""
        assert setup_instance.unsetup("2024") is True

    def test_returns_false_for_nonexistent_version(self, setup_instance, populated_registry, mock_home):
        """版本不存在时返回 False"""
        assert setup_instance.unsetup("1999") is False

    def test_unsetup_when_user_setup_not_exists(self, setup_instance, populated_registry, mock_home):
        """userSetup.py 不存在时 unsetup 不报错"""
        setup_instance.setup("2024")
        usersetup = mock_home / "Documents" / "maya" / "2024" / "scripts" / "userSetup.py"
        usersetup.unlink()

        assert setup_instance.unsetup("2024") is True


# ==================== 多版本 setup / unsetup ====================

class TestMultiVersionSetup:
    def test_setup_all_versions_when_no_version_specified(self, setup_instance, populated_registry, mock_home):
        """不指定版本时应为所有 2020+ 的已安装版本注入脚本"""
        assert setup_instance.setup() is True
        for ver in ("2022", "2024"):
            script_path = mock_home / "Documents" / "maya" / ver / "scripts" / "dcc_bridge_startup.py"
            assert script_path.exists(), f"startup script not found for {ver}"

    def test_unsetup_all_versions_when_no_version_specified(self, setup_instance, populated_registry, mock_home):
        """不指定版本时应移除所有 2020+ 的已安装版本脚本"""
        setup_instance.setup()
        assert setup_instance.unsetup() is True
        for ver in ("2022", "2024"):
            script_path = mock_home / "Documents" / "maya" / ver / "scripts" / "dcc_bridge_startup.py"
            assert not script_path.exists(), f"startup script not removed for {ver}"

    def test_setup_all_versions_modifies_user_setup(self, setup_instance, populated_registry, mock_home):
        """不指定版本时所有版本的 userSetup.py 都应被修改"""
        setup_instance.setup()
        for ver in ("2022", "2024"):
            usersetup = mock_home / "Documents" / "maya" / ver / "scripts" / "userSetup.py"
            assert usersetup.exists()
            assert f"import {STARTUP_MODULE_NAME}" in usersetup.read_text(encoding="utf-8")

    def test_returns_false_when_no_versions_installed(self, setup_instance, mock_registry, mock_home):
        """没有已安装版本时返回 False"""
        assert setup_instance.setup() is False

    def test_filters_below_min_supported(self, setup_instance, mock_registry, mock_home):
        """不指定版本时应跳过低于 2020 的版本"""
        values, subkeys = mock_registry
        subkeys[MAYA_REG_BASE] = ["2018", "2024"]
        values[f"{MAYA_REG_BASE}\\2018\\Setup\\InstallPath"] = {
            "MAYA_INSTALL_LOCATION": r"C:\Program Files\Autodesk\Maya2018\\",
        }
        values[f"{MAYA_REG_BASE}\\2024\\Setup\\InstallPath"] = {
            "MAYA_INSTALL_LOCATION": r"C:\Program Files\Autodesk\Maya2024\\",
        }
        assert setup_instance.setup() is True
        # 2024 应被注入
        script_2024 = mock_home / "Documents" / "maya" / "2024" / "scripts" / "dcc_bridge_startup.py"
        assert script_2024.exists()
        # 2018 应被跳过
        script_2018 = mock_home / "Documents" / "maya" / "2018" / "scripts" / "dcc_bridge_startup.py"
        assert not script_2018.exists()

    def test_explicit_version_below_min_still_works(self, setup_instance, mock_registry, mock_home):
        """指定 --version 2018 时即使低于 min_supported_version 也应正常注入"""
        values, subkeys = mock_registry
        subkeys[MAYA_REG_BASE] = ["2018"]
        values[f"{MAYA_REG_BASE}\\2018\\Setup\\InstallPath"] = {
            "MAYA_INSTALL_LOCATION": r"C:\Program Files\Autodesk\Maya2018\\",
        }
        assert setup_instance.setup("2018") is True
        script_2018 = mock_home / "Documents" / "maya" / "2018" / "scripts" / "dcc_bridge_startup.py"
        assert script_2018.exists()

    def test_partial_failure_returns_false(self, setup_instance, populated_registry, mock_home):
        """部分版本失败时返回 False，但其他版本仍成功"""
        original = setup_instance.get_script_dir
        def mock_get_script_dir(version=None, language="en"):
            if version == "2022":
                return None
            return original(version, language)
        setup_instance.get_script_dir = mock_get_script_dir

        result = setup_instance.setup()
        assert result is False  # 2022 失败
        # 2024 仍应成功
        script_2024 = mock_home / "Documents" / "maya" / "2024" / "scripts" / "dcc_bridge_startup.py"
        assert script_2024.exists()


class TestGetTargetVersions:
    """测试 _get_target_versions 的版本过滤逻辑"""

    def test_filters_below_min_supported(self, setup_instance, mock_registry):
        """不指定版本时应过滤掉低于 min_supported_version 的版本"""
        values, subkeys = mock_registry
        subkeys[MAYA_REG_BASE] = ["2018", "2022", "2024"]
        versions = setup_instance._get_target_versions()
        assert "2022" in versions
        assert "2024" in versions
        assert "2018" not in versions

    def test_explicit_version_not_filtered(self, setup_instance, populated_registry):
        """指定版本时不应用过滤"""
        versions = setup_instance._get_target_versions("2018")
        assert versions == ["2018"]

    def test_returns_empty_when_all_below_min(self, setup_instance, mock_registry):
        """所有版本都低于 min_supported_version 时返回空列表"""
        values, subkeys = mock_registry
        subkeys[MAYA_REG_BASE] = ["2016", "2018"]
        assert setup_instance._get_target_versions() == []


# ==================== _post_setup / _post_unsetup ====================

class TestPostHooks:
    def test_post_setup_creates_user_setup(self, setup_instance, tmp_path):
        """_post_setup 应创建或修改 userSetup.py"""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        setup_instance._post_setup(str(scripts_dir))
        usersetup = scripts_dir / "userSetup.py"
        assert usersetup.exists()
        assert f"import {STARTUP_MODULE_NAME}" in usersetup.read_text(encoding="utf-8")

    def test_post_unsetup_removes_import(self, setup_instance, tmp_path):
        """_post_unsetup 应从 userSetup.py 移除 import 行"""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        usersetup = scripts_dir / "userSetup.py"
        usersetup.write_text(f"import {STARTUP_MODULE_NAME}\nprint('keep')\n", encoding="utf-8")

        setup_instance._post_unsetup(str(scripts_dir))
        content = usersetup.read_text(encoding="utf-8")
        assert f"import {STARTUP_MODULE_NAME}" not in content
        assert "print('keep')" in content

    def test_post_unsetup_when_no_user_setup(self, setup_instance, tmp_path):
        """userSetup.py 不存在时 _post_unsetup 不报错"""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        setup_instance._post_unsetup(str(scripts_dir))  # 不应抛异常


# ==================== get_setup 工厂函数 ====================

class TestGetSetupFactory:
    def test_returns_maya_setup(self):
        """get_setup('maya') 应返回 MayaSetup 实例"""
        assert isinstance(get_setup("maya"), MayaSetup)

    def test_returns_none_for_unknown(self):
        """get_setup('unknown') 应返回 None"""
        assert get_setup("unknown") is None


# ==================== 多语言支持 ====================

class TestMultiLanguage:
    def test_get_script_dir_en_no_lang_subdir(self, setup_instance, populated_registry, mock_home):
        """英文路径不应包含语言子目录"""
        result = setup_instance.get_script_dir("2024", "en")
        assert result is not None
        assert "zh_CN" not in result
        assert result.endswith(os.path.join("maya", "2024", "scripts"))

    def test_get_script_dir_zh_cn_contains_lang_subdir(self, setup_instance, populated_registry, mock_home):
        """中文路径应包含 zh_CN 子目录"""
        result = setup_instance.get_script_dir("2024", "zh_CN")
        assert result is not None
        assert "zh_CN" in result
        assert result.endswith(os.path.join("maya", "2024", "zh_CN", "scripts"))

    def test_setup_writes_both_languages(self, setup_instance, populated_registry, mock_home):
        """setup 应同时写入英文和中文两个脚本目录"""
        assert setup_instance.setup("2024") is True
        en_script = mock_home / "Documents" / "maya" / "2024" / "scripts" / "dcc_bridge_startup.py"
        zh_script = mock_home / "Documents" / "maya" / "2024" / "zh_CN" / "scripts" / "dcc_bridge_startup.py"
        assert en_script.exists()
        assert zh_script.exists()

    def test_setup_modifies_user_setup_both_languages(self, setup_instance, populated_registry, mock_home):
        """两个语言的 userSetup.py 都应被修改"""
        setup_instance.setup("2024")
        en_usersetup = mock_home / "Documents" / "maya" / "2024" / "scripts" / "userSetup.py"
        zh_usersetup = mock_home / "Documents" / "maya" / "2024" / "zh_CN" / "scripts" / "userSetup.py"
        assert f"import {STARTUP_MODULE_NAME}" in en_usersetup.read_text(encoding="utf-8")
        assert f"import {STARTUP_MODULE_NAME}" in zh_usersetup.read_text(encoding="utf-8")

    def test_unsetup_removes_both_languages(self, setup_instance, populated_registry, mock_home):
        """unsetup 应同时移除英文和中文两个目录的脚本"""
        setup_instance.setup("2024")
        assert setup_instance.unsetup("2024") is True
        en_script = mock_home / "Documents" / "maya" / "2024" / "scripts" / "dcc_bridge_startup.py"
        zh_script = mock_home / "Documents" / "maya" / "2024" / "zh_CN" / "scripts" / "dcc_bridge_startup.py"
        assert not en_script.exists()
        assert not zh_script.exists()

    def test_unsetup_removes_import_both_languages(self, setup_instance, populated_registry, mock_home):
        """unsetup 后两个语言的 userSetup.py 都应移除 import 行"""
        setup_instance.setup("2024")
        setup_instance.unsetup("2024")
        en_usersetup = mock_home / "Documents" / "maya" / "2024" / "scripts" / "userSetup.py"
        zh_usersetup = mock_home / "Documents" / "maya" / "2024" / "zh_CN" / "scripts" / "userSetup.py"
        if en_usersetup.exists():
            assert f"import {STARTUP_MODULE_NAME}" not in en_usersetup.read_text(encoding="utf-8")
        if zh_usersetup.exists():
            assert f"import {STARTUP_MODULE_NAME}" not in zh_usersetup.read_text(encoding="utf-8")

    def test_get_supported_languages_default(self, setup_instance):
        """默认应支持 en 和 zh_CN"""
        langs = setup_instance.get_supported_languages()
        assert "en" in langs
        assert "zh_CN" in langs
