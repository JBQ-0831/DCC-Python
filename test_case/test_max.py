"""3ds Max 测试入口"""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from test_base import BaseController, run_main, run_test


def get_main_window():
    try:
        import MaxPlus

        main_window = MaxPlus.GetQMaxMainWindow()
        return main_window
    except Exception:
        try:
            import qtmax

            main_window = qtmax.GetQMaxMainWindow()
            return main_window
        except Exception:
            print("无法获取主窗口。MaxPlus 和 qtmax 都不可用。")
            return None


class MaxController(BaseController):
    """3ds Max 控制器，重写 doit"""

    def doit(self):
        print("MaxController.doit")


def _dcc_test():
    from pymxs import runtime as rt

    for o in rt.objects:
        print(o)


if __name__ == "__main__":
    run_main(__file__, __name__, _dcc_test)
    run_test(MaxController(), get_main_window())
