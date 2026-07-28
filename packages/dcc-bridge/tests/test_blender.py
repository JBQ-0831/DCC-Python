"""
BlenderSetup 单元测试

通过 mock 注册表方法测试每个公开方法，setup/unsetup 额外 mock expanduser 指向临时目录。
注册表依据：HKLM\\SOFTWARE\\Classes\\blender.<version> 子键名含版本号；
blender.<version>\\shell\\open\\command 默认值记录安装路径。
"""

from __future__ import annotations

import os

import pytest

from dcc_bridge.setup.base import DCCInstallation, get_setup
from dcc_bridge.setup.blender import BlenderSetup, BLENDER_CLASSES_BASE


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

    monkeypatch.setattr(BlenderSetup, "_read_registry_value", mock_read)
    monkeypatch.setattr(BlenderSetup, "_enum_registry_subkeys", mock_enum)

    return values, subkeys


@pytest.fixture
def populated_registry(mock_registry):
    """预填充 Blender 4.5 + 4.2 的注册表数据（含无关子键）"""
    values, subkeys = mock_registry
    subkeys[BLENDER_CLASSES_BASE] = [
        "blender.4.5",
        "blender.4.2",
        "blender",        # 无版本号子串，应被过滤
        "BlenderPro",     # 大小写/格式不符，应被过滤
        "not_blender",    # 无关键，应被过滤
    ]
    values[f"{BLENDER_CLASSES_BASE}\\blender.4.5\\shell\\open\\command"] = {
        "": r'"C:\Program Files\Blender Foundation\Blender 4.5\blender-launcher.exe" "%1"',
    }
    values[f"{BLENDER_CLASSES_BASE}\\blender.4.2\\shell\\open\\command"] = {
        "": r'"C:\Program Files\Blender Foundation\Blender 4.2\blender-launcher.exe" "%1"',
    }
    return mock_registry


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """将 ~ 指向临时目录，用于 setup/unsetup 文件操作"""
    monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path))
    return tmp_path


@pytest.fixture
def setup_instance():
    return BlenderSetup()


# ==================== discover_versions ====================

class TestDiscoverVersions:
    def test_finds_installed_versions(self, setup_instance, populated_registry):
        """应发现 4.2 和 4.5"""
        versions = setup_instance.discover_versions()
        assert "4.2" in versions
        assert "4.5" in versions

    def test_returns_sorted_numerically(self, setup_instance, populated_registry):
        """结果应按数值排序（4.2 < 4.5）"""
        versions = setup_instance.discover_versions()
        assert versions == sorted(versions, key=lambda v: [int(p) for p in v.split(".")])

    def test_filters_non_version_subkeys(self, setup_instance, populated_registry):
        """不应包含 blender / BlenderPro / not_blender 等"""
        versions = setup_instance.discover_versions()
        assert "blender" not in versions
        assert "BlenderPro" not in versions
        assert "not_blender" not in versions

    def test_returns_empty_when_no_registry(self, setup_instance, mock_registry):
        """注册表为空时返回空列表"""
        assert setup_instance.discover_versions() == []

    def test_returns_empty_when_no_blender_key(self, setup_instance, mock_registry):
        """注册表中没有 blender 子键时返回空列表"""
        _, subkeys = mock_registry
        subkeys["SOFTWARE\\SomeOther"] = ["blender.4.5"]
        assert setup_instance.discover_versions() == []


# ==================== get_install_path ====================

class TestGetInstallPath:
    def test_returns_dir_for_existing_version(self, setup_instance, populated_registry):
        """已安装版本应返回安装目录（exe 所在目录）"""
        path = setup_instance.get_install_path("4.5")
        assert path is not None
        assert "Blender Foundation" in path
        assert path.endswith("Blender 4.5")

    def test_extracts_from_command_default_value(self, setup_instance, populated_registry):
        """应从 shell\\open\\command 默认值中解析出安装目录"""
        path = setup_instance.get_install_path("4.2")
        assert path == r"C:\Program Files\Blender Foundation\Blender 4.2"

    def test_extracts_when_command_has_no_leading_quote(self, setup_instance, mock_registry):
        """真实环境 command 值可能无前导引号（如 C:\\...\\blender-launcher.exe" "%1）"""
        _, subkeys = mock_registry
        subkeys[BLENDER_CLASSES_BASE] = ["blender.4.5"]
        mock_registry[0][  # values dict
            f"{BLENDER_CLASSES_BASE}\\blender.4.5\\shell\\open\\command"
        ] = {"": r'C:\Program Files\Blender Foundation\Blender 4.5\blender-launcher.exe" "%1'}
        path = setup_instance.get_install_path("4.5")
        assert path == r"C:\Program Files\Blender Foundation\Blender 4.5"

    def test_returns_none_for_nonexistent_version(self, setup_instance, populated_registry):
        """未安装版本应返回 None"""
        assert setup_instance.get_install_path("3.0") is None

    def test_returns_none_when_no_registry(self, setup_instance, mock_registry):
        """注册表为空时返回 None"""
        assert setup_instance.get_install_path("4.5") is None


# ==================== get_script_dir ====================

class TestGetScriptDir:
    def test_returns_dir_for_existing_version(self, setup_instance, populated_registry, mock_home):
        """已安装版本应返回 scripts/startup 目录"""
        result = setup_instance.get_script_dir("4.5")
        assert result is not None
        assert result.endswith(os.path.join("Blender", "4.5", "scripts", "startup"))

    def test_returns_none_for_nonexistent_version(self, setup_instance, populated_registry, mock_home):
        """未安装版本应返回 None"""
        assert setup_instance.get_script_dir("3.0") is None

    def test_auto_discovers_when_no_version(self, setup_instance, populated_registry, mock_home):
        """不指定版本时自动发现并返回第一个"""
        result = setup_instance.get_script_dir()
        assert result is not None
        assert "startup" in result

    def test_returns_none_when_nothing_installed(self, setup_instance, mock_registry, mock_home):
        """没有安装时返回 None"""
        assert setup_instance.get_script_dir() is None

    def test_uses_appdata_layout(self, setup_instance, populated_registry, mock_home):
        """路径应包含 Blender Foundation/Blender/<version>/scripts/startup"""
        result = setup_instance.get_script_dir("4.5")
        assert "Blender Foundation" in result
        assert "scripts" in result
        assert "startup" in result


# ==================== get_python_path ====================

class TestGetPythonPath:
    def test_returns_python_for_existing_version(self, setup_instance, populated_registry):
        """已安装版本应返回内置 Python 路径"""
        path = setup_instance.get_python_path("4.5")
        assert path is not None
        assert path.endswith(os.path.join("4.5", "python", "bin", "python.exe"))

    def test_returns_none_for_nonexistent_version(self, setup_instance, populated_registry):
        """未安装版本应返回 None"""
        assert setup_instance.get_python_path("3.0") is None


# ==================== get_startup_script_name ====================

class TestGetStartupScriptName:
    def test_returns_correct_name(self, setup_instance):
        """应返回 dcc_bridge_startup.py"""
        assert setup_instance.get_startup_script_name() == "dcc_bridge_startup.py"


# ==================== get_startup_script_content ====================

class TestGetStartupScriptContent:
    def test_contains_dcc_name(self, setup_instance):
        """内容应包含 blender 标识"""
        assert "blender" in setup_instance.get_startup_script_content()

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
        """应返回 4.2 和 4.5 两个安装"""
        installations = setup_instance.detect_installations()
        versions = [inst.version for inst in installations]
        assert "4.2" in versions
        assert "4.5" in versions

    def test_installation_has_correct_dcc_name(self, setup_instance, populated_registry):
        """dcc_name 应为 blender"""
        for inst in setup_instance.detect_installations():
            assert inst.dcc_name == "blender"

    def test_installation_root_path_from_registry(self, setup_instance, populated_registry):
        """root_path 应为注册表中的安装目录"""
        installations = setup_instance.detect_installations()
        for inst in installations:
            assert "Blender Foundation" in inst.root_path
            assert inst.version in inst.root_path

    def test_returns_empty_when_nothing_installed(self, setup_instance, mock_registry):
        """没有安装时返回空列表"""
        assert setup_instance.detect_installations() == []


# ==================== get_startup_script_path ====================

class TestGetStartupScriptPath:
    def test_returns_full_path(self, setup_instance, populated_registry, mock_home):
        """应返回 scripts/startup 目录下的 dcc_bridge_startup.py"""
        path = setup_instance.get_startup_script_path("4.5")
        assert path is not None
        assert path.endswith(os.path.join("startup", "dcc_bridge_startup.py"))

    def test_returns_none_for_nonexistent(self, setup_instance, populated_registry, mock_home):
        """版本不存在时返回 None"""
        assert setup_instance.get_startup_script_path("3.0") is None


# ==================== setup ====================

class TestSetup:
    def test_writes_startup_script(self, setup_instance, populated_registry, mock_home):
        """setup 后应存在 dcc_bridge_startup.py"""
        assert setup_instance.setup("4.5") is True
        script_path = (
            mock_home / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
            / "4.5" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert script_path.exists()

    def test_script_content_correct(self, setup_instance, populated_registry, mock_home):
        """写入的脚本内容应包含 blender 和 start_server"""
        setup_instance.setup("4.5")
        script_path = (
            mock_home / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
            / "4.5" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        content = script_path.read_text(encoding="utf-8")
        assert "blender" in content
        assert "start_server" in content

    def test_returns_false_for_nonexistent_version(self, setup_instance, populated_registry, mock_home):
        """版本不存在时返回 False"""
        assert setup_instance.setup("3.0") is False

    def test_idempotent_setup(self, setup_instance, populated_registry, mock_home):
        """多次 setup 应覆盖写入，不报错"""
        assert setup_instance.setup("4.5") is True
        assert setup_instance.setup("4.5") is True

    def test_setup_creates_directory_if_not_exists(self, setup_instance, populated_registry, mock_home):
        """目录不存在时应自动创建"""
        startup_dir = (
            mock_home / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
            / "4.5" / "scripts" / "startup"
        )
        assert not startup_dir.exists()

        setup_instance.setup("4.5")
        assert startup_dir.exists()


# ==================== unsetup ====================

class TestUnsetup:
    def test_removes_startup_script(self, setup_instance, populated_registry, mock_home):
        """unsetup 后应删除 dcc_bridge_startup.py"""
        setup_instance.setup("4.5")
        script_path = (
            mock_home / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
            / "4.5" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert script_path.exists()

        assert setup_instance.unsetup("4.5") is True
        assert not script_path.exists()

    def test_returns_true_when_script_not_found(self, setup_instance, populated_registry, mock_home):
        """脚本不存在时仍返回 True"""
        assert setup_instance.unsetup("4.5") is True

    def test_returns_false_for_nonexistent_version(self, setup_instance, populated_registry, mock_home):
        """版本不存在时返回 False"""
        assert setup_instance.unsetup("3.0") is False

    def test_unsetup_after_setup_roundtrip(self, setup_instance, populated_registry, mock_home):
        """setup -> unsetup 往返后脚本应不存在"""
        setup_instance.setup("4.5")
        setup_instance.unsetup("4.5")
        script_path = (
            mock_home / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
            / "4.5" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert not script_path.exists()

    def test_unsetup_does_not_remove_other_scripts(self, setup_instance, populated_registry, mock_home):
        """unsetup 不应删除 startup 目录中的其他脚本"""
        setup_instance.setup("4.5")
        startup_dir = (
            mock_home / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
            / "4.5" / "scripts" / "startup"
        )
        other_script = startup_dir / "my_other_script.py"
        other_script.write_text("print('keep me')", encoding="utf-8")

        setup_instance.unsetup("4.5")
        assert other_script.exists()
        assert "keep me" in other_script.read_text(encoding="utf-8")


# ==================== 多版本 setup / unsetup ====================

class TestMultiVersionSetup:
    def test_setup_all_versions_when_no_version_specified(self, setup_instance, populated_registry, mock_home):
        """不指定版本时应为所有已安装版本注入脚本"""
        assert setup_instance.setup() is True
        for ver in ("4.2", "4.5"):
            script_path = (
                mock_home / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
                / ver / "scripts" / "startup" / "dcc_bridge_startup.py"
            )
            assert script_path.exists(), f"startup script not found for {ver}"

    def test_unsetup_all_versions_when_no_version_specified(self, setup_instance, populated_registry, mock_home):
        """不指定版本时应移除所有已安装版本的脚本"""
        setup_instance.setup()
        assert setup_instance.unsetup() is True
        for ver in ("4.2", "4.5"):
            script_path = (
                mock_home / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
                / ver / "scripts" / "startup" / "dcc_bridge_startup.py"
            )
            assert not script_path.exists(), f"startup script not removed for {ver}"

    def test_returns_false_when_no_versions_installed(self, setup_instance, mock_registry, mock_home):
        """没有已安装版本时返回 False"""
        assert setup_instance.setup() is False

    def test_explicit_version_works(self, setup_instance, populated_registry, mock_home):
        """指定 --version 4.2 时正常注入"""
        assert setup_instance.setup("4.2") is True
        script_4_2 = (
            mock_home / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
            / "4.2" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert script_4_2.exists()

    def test_partial_failure_returns_false(self, setup_instance, populated_registry, mock_home):
        """部分版本失败时返回 False，但其他版本仍成功"""
        original = setup_instance.get_script_dir
        def mock_get_script_dir(version=None, language="en"):
            if version == "4.2":
                return None
            return original(version, language)
        setup_instance.get_script_dir = mock_get_script_dir

        result = setup_instance.setup()
        assert result is False  # 4.2 失败
        # 4.5 仍应成功
        script_4_5 = (
            mock_home / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
            / "4.5" / "scripts" / "startup" / "dcc_bridge_startup.py"
        )
        assert script_4_5.exists()


class TestGetTargetVersions:
    """测试 _get_target_versions 的版本过滤逻辑"""

    def test_no_filter_without_min_version(self, setup_instance, populated_registry):
        """min_supported_version 为 None，应返回所有已安装版本"""
        versions = setup_instance._get_target_versions()
        assert "4.2" in versions
        assert "4.5" in versions

    def test_explicit_version_not_filtered(self, setup_instance, populated_registry):
        """指定版本时不应用过滤"""
        versions = setup_instance._get_target_versions("4.2")
        assert versions == ["4.2"]

    def test_returns_empty_when_all_below_min(self, setup_instance, mock_registry):
        """没有已安装版本时返回空列表"""
        assert setup_instance._get_target_versions() == []


# ==================== get_setup 工厂函数 ====================

class TestGetSetupFactory:
    def test_returns_blender_setup_for_blender(self):
        """get_setup('blender') 应返回 BlenderSetup 实例"""
        assert isinstance(get_setup("blender"), BlenderSetup)

    def test_returns_blender_setup_for_alias(self):
        """get_setup('bl') 别名也应返回 BlenderSetup 实例"""
        assert isinstance(get_setup("bl"), BlenderSetup)

    def test_returns_none_for_unknown(self):
        """get_setup('unknown') 应返回 None"""
        assert get_setup("unknown") is None


# ==================== 多语言支持 ====================

class TestMultiLanguage:
    def test_get_supported_languages_default(self, setup_instance):
        """默认应只支持 en（脚本目录不随语言变化）"""
        langs = setup_instance.get_supported_languages()
        assert langs == ["en"]
