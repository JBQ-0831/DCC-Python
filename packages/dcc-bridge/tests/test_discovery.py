# -*- coding: utf-8 -*-
"""discovery 模块写/读/删闭环测试（验证 py2/py3 编码修复不回归）"""
import json
import os

import pytest

from dcc_bridge import discovery


@pytest.fixture
def temp_instances_dir(tmp_path, monkeypatch):
    """把发现文件目录重定向到临时目录，避免污染用户目录"""
    d = tmp_path / "instances"
    monkeypatch.setattr(discovery, "get_instances_dir", lambda: str(d))
    return d


class _FakeMaxAdapter(object):
    name = "3dsmax"

    def get_version(self):
        return "2019"

    def get_python_path(self):
        return r"C:\Program Files\Autodesk\3ds Max 2019\3dsmaxpy.exe"


def test_register_instance_writes_valid_utf8_json(temp_instances_dir):
    """聚焦修复点：register_instance 必须以合法 UTF-8 写出可被解析的 JSON。

    py2 下旧实现用 io.open 文本模式 + json.dump(ensure_ascii=False)，
    对纯 ASCII 内容会写 str(bytes) 触发 'must be unicode' 错误。
    现改为二进制流 + 手动转码，这里直接读文件验证编码正确。
    """
    path = discovery.register_instance(_FakeMaxAdapter(), port=8080, pid=12345)
    # 直接读文件（绕过 list_instances 的 pid 存活检查），验证写入结果
    with open(path, "rb") as f:
        raw = f.read()
    # 应为合法 UTF-8，且能被 json.loads 解析（覆盖 py2 编码坑）
    text = raw.decode("utf-8")
    info = json.loads(text)
    assert info["port"] == 8080
    assert info["dcc_name"] == "3dsmax"
    assert info["dcc_version"] == "2019"
    assert info["python_path"].endswith("3dsmaxpy.exe")


def test_unregister_instance_removes_file(temp_instances_dir):
    path = discovery.register_instance(_FakeMaxAdapter(), port=8080, pid=12345)
    assert os.path.exists(path)
    assert discovery.unregister_instance("3dsmax", pid=12345) is True
    assert not os.path.exists(path)
