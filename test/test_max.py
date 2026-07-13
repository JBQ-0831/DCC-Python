import os
import sys

# 确保 view 模块可被导入
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from view.main_window import MainWindow, BaseController

def get_main_window():
    try:
        import MaxPlus
        main_window = MaxPlus.GetQMaxMainWindow()
        return main_window
    except :
        try:
            import qtmax
            main_window = qtmax.GetQMaxMainWindow()
            return main_window
        except :
            print("无法获取主窗口。MaxPlus 和 qtmax 都不可用。")
            return None

class MaxController(BaseController):
    """3ds Max 控制器，重写 doit"""
    def doit(self):
        print("MaxController.doit")


def main():
    print(__file__)
    print(__name__)
    from pymxs import runtime as rt
    for o in rt.objects:
        print(o)

if __name__ == "__main__":
    # main()
    _win = MainWindow(MaxController(),get_main_window())
    _win.show()
