import os
import sys

# 确保 view 模块可被导入
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from view.main_window import MainWindow, BaseController

def get_main_window():
    try:
        try:
            from PySide2.QtWidgets import QWidget
        except ImportError:
            from PySide6.QtWidgets import QWidget
        from shiboken2 import wrapInstance
        import maya.OpenMayaUI as omui
        main_window = wrapInstance(int(omui.MQtUtil.mainWindow()), QWidget)
        return main_window
    except:
        print("无法获取主窗口。maya.OpenMayaUI 不可用。")
        return None

class MayaController(BaseController):
    """Maya 控制器，重写 doit"""
    def doit(self):
        print("MayaController.doit")


def main():
    print(__file__)
    print(__name__)
    from maya import cmds
    cmds.warning("Hello from Maya")

if __name__ == "__main__":
    # main()
    _win = MainWindow(MayaController(),get_main_window())
    _win.show()

