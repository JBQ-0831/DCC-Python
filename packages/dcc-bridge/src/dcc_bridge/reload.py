# -*- coding: utf-8 -*-
"""
Module for reloading Python modules within the VS Code workspace

兼容 Python 2.7 / 3.x：不使用 from __future__ import annotations、
list[str] 注解、f-string；time.perf_counter 在 py2 不存在改用 time.time；
reload 在 py2 用 imp.reload（importlib.reload 在 py2 不存在）。
"""

import importlib
import os
import sys
import time
import traceback

if sys.version_info >= (3,):
    from importlib import reload as _reload_module
else:
    from imp import reload as _reload_module

if hasattr(time, "perf_counter"):
    _now = time.perf_counter
else:
    _now = time.time


def reload(workspace_folders):
    start_time = _now()

    num_reloads = 0
    num_failed = 0

    workspace_folders = [
        os.path.normpath(folder).lower() for folder in workspace_folders
    ]

    for variable in list(sys.modules.values()):
        if not hasattr(variable, "__file__") or not variable.__file__:
            continue

        filepath = variable.__file__.lower()

        if not any(filepath.startswith(x) for x in workspace_folders):
            continue

        try:
            _reload_module(variable)
        except Exception:
            print(
                'Failed to reload "{0}":\n{1}'.format(
                    filepath, traceback.format_exc()
                )
            )
            num_failed += 1
            continue

        num_reloads += 1

    elapsed_time_ms = round((_now() - start_time) * 1000)

    print(
        "Reloaded {0} module{1} in {2}ms".format(
            num_reloads, "s" if num_reloads != 1 else "", elapsed_time_ms
        )
    )
