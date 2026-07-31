# -*- coding: utf-8 -*-
"""
集成 tools/check_py2_compat.py，作为 CI 门禁：
确保被 DCC 进程内解释器 import 的 dcc_bridge 模块不残留 py2 不兼容语法。

扫描脚本默认排除 setup/ cli/ dcc_names.py __main__.py（这些明确运行在系统 py3）。
"""

import os
import subprocess
import sys

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
_SCRIPT = os.path.join(_REPO_ROOT, "tools", "check_py2_compat.py")
_TARGET = os.path.join(_REPO_ROOT, "packages", "dcc-bridge", "src", "dcc_bridge")


def test_dcc_bridge_package_is_py2_compatible():
    assert os.path.exists(_SCRIPT), _SCRIPT
    result = subprocess.run(
        [sys.executable, _SCRIPT, _TARGET],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out = result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace")
    assert result.returncode == 0, out
