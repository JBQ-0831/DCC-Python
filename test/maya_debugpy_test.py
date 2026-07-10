"""
Maya 环境 debugpy 安装测试脚本
在 Maya 脚本编辑器（Python 标签）中运行此脚本
"""
import sys
import os
import subprocess

print("=" * 50)
print("1. sys.executable 的值")
print(f"   sys.executable = {sys.executable}")

print("=" * 50)
print("2. 检查 mayapy.exe 路径")
maya_bin = os.path.dirname(sys.executable)
mayapy_path = os.path.join(maya_bin, "mayapy.exe")
print(f"   mayapy 路径: {mayapy_path}")
print(f"   是否存在: {os.path.exists(mayapy_path)}")

print("=" * 50)
print("3. 测试 maya.exe -m pip (会卡住，跳过)")
print("   跳过此步骤，直接测试 mayapy.exe")

print("=" * 50)
print("4. mayapy.exe -m pip install debugpy")
print(f"   执行: {mayapy_path} -m pip install debugpy")
try:
    result = subprocess.run(
        [mayapy_path, "-m", "pip", "install", "debugpy","-i","https://pypi.tuna.tsinghua.edu.cn/simple"],
        capture_output=True, text=True, timeout=30
    )
    print(f"   返回码: {result.returncode}")
    print(f"   stdout:\n{result.stdout}")
    if result.stderr:
        print(f"   stderr:\n{result.stderr}")
except subprocess.TimeoutExpired:
    print("   [错误] 超时(30秒)，命令可能卡住了")
except Exception as e:
    print(f"   [错误] {e}")

print("=" * 50)
print("5. 验证 debugpy 是否可导入")
try:
    import debugpy
    print(f"   debugpy 版本: {debugpy.__version__}")
    print(f"   导入成功")
except ImportError:
    print("   [错误] debugpy 仍然无法导入")

print("=" * 50)
print("测试完成")