print(__file__)

for i in range(10):
    print(i)

try:
    from PySide2.QtWidgets import (QWidget, QPushButton, QLabel,
                                QVBoxLayout, QDialog)
except ImportError:
    from PySide6.QtWidgets import (QWidget, QPushButton, QLabel,
                               QVBoxLayout, QDialog)
import hou

# ===================== UI窗口类 =====================
class HoudiniCustomWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 窗口基础设置
        self.setWindowTitle("Houdini PySide6 示例窗口")
        self.resize(400, 220)

        # 构建布局与控件
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout()

        self.label = QLabel("Houdini + PySide6 标准窗体")
        self.btn = QPushButton("点击创建Sphere")
        self.btn.clicked.connect(self.on_create_sphere)

        layout.addWidget(self.label)
        layout.addWidget(self.btn)
        self.setLayout(layout)

    def on_create_sphere(self):
        # 示例：操作Houdini场景
        hou.node("/obj").createNode("geo").createNode("sphere")
        hou.ui.displayMessage("球体创建成功！")


# ===================== 启动入口（固定写法） =====================
# 全局变量保存窗口实例，防止GC回收！
# 若放在函数内局部变量，弹窗瞬间消失
window_instance = None

def show_window():
    global window_instance
    # 获取Houdini主Qt窗口作为父对象
    houdini_main_win = hou.ui.mainQtWindow()

    # 单例控制：窗口只打开一次
    if window_instance is None:
        window_instance = HoudiniCustomWindow(parent=houdini_main_win)
    
    # 窗口显示、前置
    window_instance.show()
    window_instance.raise_()
    window_instance.activateWindow()

# 执行打开窗口
show_window()