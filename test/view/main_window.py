"""通用 PySide 窗体，用于测试 DCC Python 调试功能"""
try:
    from PySide2.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget
except ImportError:
    from PySide6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget


class BaseController(object):
    """基础控制器，子类重写 doit 实现各 DCC 特有逻辑"""
    def doit(self):
        print("BaseController.doit")


class MainWindow(QMainWindow):
    """最简单的窗体：一个按钮，点击时调用传入控制器的 doit 方法"""
    __obj_name = 'dcc_python_test_main_window'
    def __init__(self, controller,parent=None):
        super(MainWindow, self).__init__(parent)
        self.setObjectName(self.__obj_name)
        self.controller = controller
        self.setWindowTitle("DCC Python Debug Test")
        central = QWidget()
        layout = QVBoxLayout(central)
        btn = QPushButton("Do It123123")
        btn.clicked.connect(self.controller.doit)
        layout.addWidget(btn)
        self.setCentralWidget(central)
        self.resize(800, 600)

    def close_latest(self):
        """关闭同名窗体"""
        for w in self.parent().findChildren(QWidget, self.__obj_name):
            w.close()
            print("关闭窗体：", self.__obj_name)

    def show(self):
        """显示窗体前，先关闭同名窗体"""
        self.close_latest()
        super(MainWindow, self).show()