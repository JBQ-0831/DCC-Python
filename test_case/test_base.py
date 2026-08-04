# coding: utf-8

"""DCC 测试公共基模块 —— 提供通用导入、main() 和窗口启动辅助函数"""

import os
import sys

# ── 确保 view 模块可被导入 ──
_here = os.path.dirname(os.path.abspath(__file__))
# print(_here)
if _here not in sys.path:
    sys.path.insert(0, _here)
for p in sys.path:
    print(p)
from view.main_window import MainWindow,BaseController

controller = BaseController

def run_main(caller_file, caller_name, dcc_test_fn=None):
    """统一的 main() 实现：打印调用文件信息并执行 DCC 特有测试。

    用法:
        if __name__ == "__main__":
            run_main(__file__, __name__, _dcc_test)
            run_test(MyController(), get_main_window())
    """
    print(caller_file)
    print(caller_name)
    if dcc_test_fn:
        dcc_test_fn()


def run_test(controller, parent=None):
    """创建并显示测试窗口的通用入口。"""
    _win = MainWindow(controller, parent)
    _win.show()
    return _win
