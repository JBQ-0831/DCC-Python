"""
Module for reloading Python modules within the VS Code workspace
"""
from __future__ import annotations

import importlib
import traceback
import time
import sys
import os


def reload(workspace_folders: list[str]):
    start_time = time.perf_counter()

    num_reloads = 0
    num_failed = 0

    workspace_folders = [os.path.normpath(folder).lower() for folder in workspace_folders]

    for variable in list(sys.modules.values()):
        if not hasattr(variable, '__file__') or not variable.__file__:
            continue

        filepath = variable.__file__.lower()

        if not any(filepath.startswith(x) for x in workspace_folders):
            continue

        try:
            importlib.reload(variable)
        except Exception as e:
            print(f'Failed to reload "{filepath}":\n{traceback.format_exc()}')
            num_failed += 1
            continue

        num_reloads += 1

    elapsed_time_ms = round((time.perf_counter() - start_time) * 1000)

    print(f"Reloaded {num_reloads} module{'s' if num_reloads != 1 else ''} in {elapsed_time_ms}ms")
