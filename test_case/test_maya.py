"""Maya 测试入口"""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from test_base import BaseController, run_main, run_test


def get_main_window():
    try:
        try:
            from PySide2.QtWidgets import QWidget
            from shiboken2 import wrapInstance
        except ImportError:
            from PySide6.QtWidgets import QWidget
            from shiboken6 import wrapInstance
        import maya.OpenMayaUI as omui

        main_window = wrapInstance(int(omui.MQtUtil.mainWindow()), QWidget)
        return main_window
    except Exception:
        print("无法获取主窗口。maya.OpenMayaUI 不可用。")
        return None


class MayaController(BaseController):
    """Maya 控制器，重写 doit"""

    def doit(self):
        print("MayaController.doit")


def _dcc_test():
    from maya import cmds

    cmds.warning("Hello from Maya")


if __name__ == "__main__":
    run_main(__file__, __name__, _dcc_test)
    run_test(MayaController(), get_main_window())
