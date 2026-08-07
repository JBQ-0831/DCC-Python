# -*- coding: utf-8 -*-
"""
Module for reloading Python modules within the VS Code workspace
兼容 Python 2.7 / 3.x：无f-string、无类型注解、无nonlocal
reload Py2使用imp.reload，Py3使用importlib.reload
Qt优先尝试PySide2，失败再试PySide6，都无则跳过UI销毁
"""
import os
import sys
import time
import traceback
import gc

# 暴力尝试导入 PySide2 / PySide6，Py27完全支持该导入写法
QtWidgets = None
try:
    from PySide2 import QtWidgets
except ImportError:
    try:
        from PySide6 import QtWidgets
    except ImportError:
        # 当前环境无Qt（Blender等）
        pass

# Py2/Py3 reload 适配
if sys.version_info >= (3,):
    from importlib import reload as _reload_module
else:
    from imp import reload as _reload_module

# 兼容高精度时间函数
if hasattr(time, "perf_counter"):
    _now = time.perf_counter
else:
    _now = time.time


def destroy_all_widgets_by_module(target_modules):
    """
    递归销毁所有属于待重载模块的Qt控件（顶层+内嵌子控件）
    Py27兼容实现，无nonlocal，无Qt环境直接return
    """
    if QtWidgets is None or not target_modules:
        return

    app = QtWidgets.QApplication.instance()
    if app is None:
        return

    target_mod_set = set(mod.__name__ for mod in target_modules)
    # Py2.7 无nonlocal，用列表可变容器存储计数
    destroy_cnt = [0]

    def recursive_clear(widget):
        cls = type(widget)
        if cls.__module__ in target_mod_set:
            widget.close()
            widget.deleteLater()
            destroy_cnt[0] += 1
        # 递归遍历子控件
        for child_widget in widget.children():
            recursive_clear(child_widget)

    # 遍历所有顶层窗口
    for top_win in app.topLevelWidgets():
        recursive_clear(top_win)

    gc.collect()
    if destroy_cnt[0] > 0:
        # Py27 print 中文兼容
        print("[SafeReload] 销毁 %d 个待重载模块关联的Qt控件" % destroy_cnt[0])


def reload(workspace_folders):
    """原有批量重载逻辑完全保留，接口不变"""
    print("fn reload, workspace = {}".format(workspace_folders))
    start_time = _now()

    num_reloads = 0
    num_failed = 0

    workspace_folders = [
        os.path.normpath(folder).lower() for folder in workspace_folders
    ]

    # 先收集全部待重载模块，不立刻reload
    to_reload_modules = []
    for variable in list(sys.modules.values()):
        if not hasattr(variable, "__file__") or not variable.__file__:
            continue

        filepath = variable.__file__.lower()
        if not any(filepath.startswith(x) for x in workspace_folders):
            continue
        to_reload_modules.append(variable)

    # 前置销毁Qt控件（无Qt自动跳过）
    destroy_all_widgets_by_module(to_reload_modules)

    # 原生重载逻辑未改动
    for module in to_reload_modules:
        try:
            _reload_module(module)
            print("Reloaded {0}".format(module.__name__))
        except Exception:
            filepath = module.__file__
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
        "Reloaded {0} module{1} in {2}ms, failed: {3}".format(
            num_reloads, "s" if num_reloads != 1 else "", elapsed_time_ms, num_failed
        )
    )