import os
import sys

# 确保 view 模块可被导入
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from view.main_window import MainWindow, BaseController


def get_main_window():
    try:
        import substance_painter.ui as sp_ui
        main_window = sp_ui.get_main_window()
        return main_window
    except:
        print("无法获取主窗口。substance_painter.ui 不可用。")
        return None

class SPController(BaseController):
    """Substance Painter 控制器，重写 doit"""
    def doit(self):
        print("SPController.doit")

def main():
    print(__file__)
    print(__name__)
    import substance_painter.project as sp_project
    print(sp_project.is_open())


if __name__ == "__main__":
    # main()
    _win = MainWindow(SPController(),get_main_window())
    _win.show()
