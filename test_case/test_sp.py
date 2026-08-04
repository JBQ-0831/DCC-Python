"""Substance Painter 测试入口"""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from test_base import controller, run_main, run_test


def get_main_window():
    try:
        import substance_painter.ui as sp_ui

        main_window = sp_ui.get_main_window()
        return main_window
    except Exception:
        print("无法获取主窗口。substance_painter.ui 不可用。")
        return None


class SPController(controller):
    """Substance Painter 控制器，重写 doit"""

    def doit(self):
        print("SPController.doit")


def _dcc_test():
    import substance_painter.project as sp_project

    print(sp_project.is_open())


if __name__ == "__main__":
    run_main(__file__, __name__, _dcc_test)
    run_test(SPController(), get_main_window())
