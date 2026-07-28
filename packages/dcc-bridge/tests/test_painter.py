"""
PainterSetup 单元测试

通过 mock 注册表方法测试每个公开方法，setup/unsetup 额外 mock expanduser 指向临时目录。
discover_versions 依赖 ctypes 读取 exe 版本信息，这里用 mock_version_info 伪造版本号。
"""

from __future__ import annotations

import os

import pytest

import dcc_bridge.setup.painter as painter
from dcc_bridge.setup.base import DCCInstallation, get_setup
from dcc_bridge.setup.painter import PainterSetup, SP_REG_BASE


# ==================== fixture ====================

@pytest.fixture
def mock_registry(monkeypatch):
    """模拟注册表 _read_registry_value，返回 values 字典供测试修改"""
    values: dict = {}

    def mock_read(self, reg_path, value_name):
        return values.get(reg_path, {}).get(value_name)

    monkeypatch.setattr(PainterSetup, "_read_registry_value", mock_read)
    return values


@pytest.fixture
def populated_registry(mock_registry):
    """预填充 Painter 的 App Paths 注册表数据"""
    mock_registry[SP_REG_BASE] = {
        "": r"C:\Program Files\Adobe\Adobe Substance 3D Painter\Adobe Substance 3D Painter.exe",
        "Path": r"C:\Program Files\Adobe\Adobe Substance 3D Painter\\",
    }
    return mock_registry


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """将 ~ 指向临时目录，用于 setup/unsetup 文件操作"""
    monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path))
    return tmp_path


@pytest.fixture
def mock_version_info(monkeypatch):
    """
    伪造 ctypes 版本信息层，使 discover_versions 返回受控的版本号。

    使用方式：在测试中调用 mock_version_info(主版本, 次版本)。
    同时让 os.path.exists(exe_path) 恒为 True，跳过真实 exe 存在性检查。
    """
    def install(major: int, minor: int):
        ffi = type(
            "FFI", (), {"dwFileVersionMS": (major << 16) | minor, "dwFileVersionLS": 0}
        )()
        pointer_cls = type("Pointer", (), {"contents": ffi})
        fake = type(
            "FakeCtypes",
            (),
            {
                "windll": type(
                    "W",
                    (),
                    {
                        "version": type(
                            "V",
                            (),
                            {
                                "GetFileVersionInfoSizeW": staticmethod(lambda *a: 1024),
                                "GetFileVersionInfoW": staticmethod(lambda *a: 1),
                                "VerQueryValueW": staticmethod(lambda *a: 1),
                            },
                        )()
                    },
                )(),
                "create_string_buffer": staticmethod(lambda size: bytearray(size)),
                "c_void_p": staticmethod(lambda: object()),
                "byref": staticmethod(lambda x: x),
                "cast": staticmethod(lambda ptr, ptype: pointer_cls()),
                "POINTER": staticmethod(lambda typ: pointer_cls),
            },
        )()
        monkeypatch.setattr(painter, "ctypes", fake)
        # 仅对 exe 路径返回 True，避免破坏 os.makedirs（其内部会调用
        # os.path.exists(head) 判断父目录是否已存在）
        _real_exists = painter.os.path.exists
        monkeypatch.setattr(
            painter.os.path, "exists", lambda p: str(p).endswith(".exe") or _real_exists(p)
        )

    return install


@pytest.fixture
def setup_instance():
    return PainterSetup()


# ==================== discover_versions ====================

class TestDiscoverVersions:
    def test_returns_version_from_exe(self, setup_instance, populated_registry, mock_version_info):
        """应读取 exe 版本信息得到 10.1"""
        mock_version_info(10, 1)
        assert setup_instance.discover_versions() == ["10.1"]

    def test_returns_empty_when_no_exe_path(self, setup_instance, mock_registry, mock_version_info):
        """注册表无 exe 路径时返回空列表"""
        mock_version_info(10, 1)
        assert setup_instance.discover_versions() == []

    def test_returns_empty_when_exe_not_exists(self, setup_instance, populated_registry, monkeypatch):
        """exe 路径存在但文件不存在时返回空列表"""
        monkeypatch.setattr(painter.os.path, "exists", lambda p: False)
        assert setup_instance.discover_versions() == []


# ==================== get_install_path ====================

class TestGetInstallPath:
    def test_returns_install_dir(self, setup_instance, populated_registry):
        """应返回注册表中的 Path 安装目录"""
        path = setup_instance.get_install_path("10.1")
        assert path is not None
        assert "Adobe Substance 3D Painter" in path

    def test_returns_none_when_no_registry(self, setup_instance, mock_registry):
        """注册表为空时返回 None"""
        assert setup_instance.get_install_path("10.1") is None


# ==================== get_script_dir ====================

class TestGetScriptDir:
    def test_returns_startup_dir(self, setup_instance, populated_registry, mock_home):
        """脚本目录应为 .../python/startup"""
        result = setup_instance.get_script_dir("10.1")
        assert result is not None
        assert result.endswith(
            os.path.join("Adobe", "Adobe Substance 3D Painter", "python", "startup")
        )

    def test_dir_not_version_dependent(self, setup_instance, populated_registry, mock_home):
        """SP 单版本安装，脚本目录不随版本号变化"""
        r1 = setup_instance.get_script_dir("10.1")
        r2 = setup_instance.get_script_dir("9.9")
        assert r1 == r2

    def test_returns_dir_when_nothing_installed(self, setup_instance, mock_registry, mock_home):
        """即使注册表为空，get_script_dir 仍返回固定路径（不依赖注册表）"""
        result = setup_instance.get_script_dir()
        assert result is not None
        assert "startup" in result


# ==================== get_python_path ====================

class TestGetPythonPath:
    def test_returns_pythonsdk_path(self, setup_instance, populated_registry):
        """应拼接 resources/pythonsdk/python.exe"""
        result = setup_instance.get_python_path("10.1")
        assert result is not None
        assert result.endswith(os.path.join("resources", "pythonsdk", "python.exe"))

    def test_returns_none_when_no_install(self, setup_instance, mock_registry):
        """无安装目录时返回 None"""
        assert setup_instance.get_python_path("10.1") is None


# ==================== get_supported_languages ====================

class TestGetSupportedLanguages:
    def test_returns_only_en(self, setup_instance):
        """SP 脚本目录不随语言变化，只注入 en"""
        assert setup_instance.get_supported_languages() == ["en"]


# ==================== get_startup_script_name ====================

class TestGetStartupScriptName:
    def test_returns_default_name(self, setup_instance):
        """应返回 dcc_bridge_startup.py"""
        assert setup_instance.get_startup_script_name() == "dcc_bridge_startup.py"


# ==================== get_startup_script_content ====================

class TestGetStartupScriptContent:
    def test_contains_dcc_name(self, setup_instance):
        """内容应包含 substance_painter 标识"""
        assert "substance_painter" in setup_instance.get_startup_script_content()

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
    def test_returns_installation(self, setup_instance, populated_registry, mock_version_info):
        """应返回一个 installation"""
        mock_version_info(10, 1)
        installations = setup_instance.detect_installations()
        assert len(installations) == 1
        inst = installations[0]
        assert inst.dcc_name == "substance_painter"
        assert inst.version == "10.1"
        assert "Adobe" in inst.root_path

    def test_returns_empty_when_nothing_installed(self, setup_instance, mock_registry):
        """没有安装时返回空列表"""
        assert setup_instance.detect_installations() == []


# ==================== get_startup_script_path ====================

class TestGetStartupScriptPath:
    def test_returns_full_path(self, setup_instance, populated_registry, mock_home):
        """应返回 startup 目录下的 dcc_bridge_startup.py"""
        path = setup_instance.get_startup_script_path("10.1")
        assert path is not None
        assert path.endswith(
            os.path.join("python", "startup", "dcc_bridge_startup.py")
        )


# ==================== setup ====================

class TestSetup:
    def test_writes_startup_script(self, setup_instance, populated_registry, mock_home):
        """setup 后应存在 dcc_bridge_startup.py"""
        assert setup_instance.setup("10.1") is True
        script_path = mock_home / "Documents" / "Adobe" / "Adobe Substance 3D Painter" / "python" / "startup" / "dcc_bridge_startup.py"
        assert script_path.exists()

    def test_script_content_correct(self, setup_instance, populated_registry, mock_home):
        """写入的脚本内容应包含 substance_painter 和 start_server"""
        setup_instance.setup("10.1")
        script_path = mock_home / "Documents" / "Adobe" / "Adobe Substance 3D Painter" / "python" / "startup" / "dcc_bridge_startup.py"
        content = script_path.read_text(encoding="utf-8")
        assert "substance_painter" in content
        assert "start_server" in content

    def test_idempotent_setup(self, setup_instance, populated_registry, mock_home):
        """多次 setup 应覆盖写入，不报错"""
        assert setup_instance.setup("10.1") is True
        assert setup_instance.setup("10.1") is True

    def test_setup_without_version_discovers(self, setup_instance, populated_registry, mock_home, mock_version_info):
        """不指定版本时通过 discover_versions 找到 10.1 并注入"""
        mock_version_info(10, 1)
        assert setup_instance.setup() is True
        script_path = mock_home / "Documents" / "Adobe" / "Adobe Substance 3D Painter" / "python" / "startup" / "dcc_bridge_startup.py"
        assert script_path.exists()


# ==================== unsetup ====================

class TestUnsetup:
    def test_removes_startup_script(self, setup_instance, populated_registry, mock_home):
        """unsetup 后应删除 dcc_bridge_startup.py"""
        setup_instance.setup("10.1")
        script_path = mock_home / "Documents" / "Adobe" / "Adobe Substance 3D Painter" / "python" / "startup" / "dcc_bridge_startup.py"
        assert script_path.exists()

        assert setup_instance.unsetup("10.1") is True
        assert not script_path.exists()

    def test_returns_true_when_script_not_found(self, setup_instance, populated_registry, mock_home):
        """脚本不存在时仍返回 True"""
        assert setup_instance.unsetup("10.1") is True

    def test_unsetup_after_setup_roundtrip(self, setup_instance, populated_registry, mock_home):
        """setup -> unsetup 往返后脚本应不存在"""
        setup_instance.setup("10.1")
        setup_instance.unsetup("10.1")
        script_path = mock_home / "Documents" / "Adobe" / "Adobe Substance 3D Painter" / "python" / "startup" / "dcc_bridge_startup.py"
        assert not script_path.exists()


# ==================== get_setup 工厂函数 ====================

class TestGetSetupFactory:
    def test_returns_painter_setup_for_substance_painter(self):
        """get_setup('substance_painter') 应返回 PainterSetup 实例"""
        assert isinstance(get_setup("substance_painter"), PainterSetup)

    def test_returns_painter_setup_for_alias(self):
        """get_setup('painter') 也应返回 PainterSetup 实例"""
        assert isinstance(get_setup("painter"), PainterSetup)

    def test_returns_none_for_unknown(self):
        """get_setup('unknown') 应返回 None"""
        assert get_setup("unknown") is None
