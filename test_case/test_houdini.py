"""Houdini 测试入口"""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from test_base import controller, run_main, run_test


def get_main_window():
    try:
        import hou

        main_window = hou.ui.mainQtWindow()
        return main_window
    except Exception:
        print("无法获取主窗口。hou 不可用。")
        return None


class HoudiniController(controller):
    """Houdini 控制器，重写 doit"""

    def doit(self):
        print("HoudiniController.doit")


def _dcc_test():
    import hou

    print(f"hou.pwd() = {hou.pwd()}")


if __name__ == "__main__":
    # run_main(__file__, __name__, _dcc_test)

    run_test(HoudiniController(), get_main_window())