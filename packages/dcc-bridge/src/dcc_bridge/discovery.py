"""
DCC 服务进程自动发现模块

DCC 端 TCP 服务启动后，在本地用户目录写入发现文件；
CLI 和 VS Code 插件通过读取发现文件自动发现当前运行的 DCC 实例。
"""

from __future__ import annotations

import datetime
import json
import os
import re
from typing import Any, Dict, List, Optional


def get_user_data_dir() -> str:
    """返回 dcc-bridge 用户数据目录"""
    if sys_platform_win():
        base = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    else:
        base = os.path.expanduser("~")
    return os.path.join(base, ".dcc-bridge")


def get_instances_dir() -> str:
    """返回发现文件存放目录"""
    return os.path.join(get_user_data_dir(), "instances")


def sys_platform_win() -> bool:
    """当前是否为 Windows 平台"""
    return os.name == "nt" or os.sys.platform.startswith("win")


def _ensure_instances_dir() -> None:
    os.makedirs(get_instances_dir(), exist_ok=True)


def _instance_filename(dcc_type: str, pid: int) -> str:
    return os.path.join(get_instances_dir(), f"{dcc_type}-{pid}.json")


def _is_pid_alive(pid: int) -> bool:
    """跨平台检测进程是否存活。

    DCC 软件关闭时 atexit 钩子不可靠（可能崩溃或被强制结束），
    因此在读取发现文件时需要惰性检查 PID 是否仍存在。
    """
    if pid <= 0:
        return False

    if sys_platform_win():
        # Windows: 用 OpenProcess + GetExitCodeProcess 判断进程是否仍在运行
        import ctypes

        PROCESS_QUERY_INFORMATION = 0x0400
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    else:
        # Unix: 发送信号 0，不实际发信号，仅检查进程是否存在
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def register_instance(
    dcc_type: str,
    port: int,
    dcc_version: str = "",
    pid: Optional[int] = None,
    host: str = "127.0.0.1",
    python_path: str = "",
) -> str:
    """
    注册一个 DCC 服务实例。

    Args:
        dcc_type: DCC 类型，如 'maya'、'3dsmax'
        port: TCP 服务端口
        dcc_version: DCC 版本，如 '2024'
        pid: 进程 ID，默认使用当前进程 ID
        host: 服务监听地址
        python_path: DCC Python 解释器路径

    Returns:
        写入的发现文件路径
    """
    if pid is None:
        pid = os.getpid()

    _ensure_instances_dir()
    filepath = _instance_filename(dcc_type, pid)

    info: Dict[str, Any] = {
        "pid": pid,
        "dcc_type": dcc_type,
        "dcc_version": dcc_version,
        "host": host,
        "port": port,
        "started_at": datetime.datetime.now().isoformat(),
        "python_path": python_path or os.path.abspath(os.path.dirname(os.path.dirname(__file__))),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    return filepath


def unregister_instance(dcc_type: str, pid: Optional[int] = None) -> bool:
    """
    注销一个 DCC 服务实例。

    Args:
        dcc_type: DCC 类型
        pid: 进程 ID，默认使用当前进程 ID

    Returns:
        是否成功删除文件
    """
    if pid is None:
        pid = os.getpid()

    filepath = _instance_filename(dcc_type, pid)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return True
        except OSError:
            return False
    return False


def unregister_all_instances() -> int:
    """注销当前进程 ID 对应的所有发现文件，返回删除数量"""
    pid = os.getpid()
    count = 0
    for info in list_instances():
        if info.get("pid") == pid:
            if unregister_instance(info.get("dcc_type", "unknown"), pid):
                count += 1
    return count


def list_instances() -> List[Dict[str, Any]]:
    """读取所有发现文件，返回 DCC 实例列表。

    会自动清理已退出的 DCC 进程对应的发现文件：
    DCC 软件关闭时 atexit 钩子不可靠（崩溃/强制结束均不触发），
    因此在读取时惰性检查 PID 是否存活，已退出的实例文件会被删除。
    """
    instances: List[Dict[str, Any]] = []
    instances_dir = get_instances_dir()

    if not os.path.isdir(instances_dir):
        return instances

    pattern = re.compile(r"^([a-zA-Z0-9_]+)-(\d+)\.json$")

    for filename in os.listdir(instances_dir):
        match = pattern.match(filename)
        if not match:
            continue

        filepath = os.path.join(instances_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                info = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        # 惰性清理：进程已退出则删除发现文件并跳过
        pid = info.get("pid")
        if pid and not _is_pid_alive(pid):
            try:
                os.remove(filepath)
            except OSError:
                pass
            continue

        instances.append(info)

    # 按启动时间排序，最新的在前
    instances.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return instances


def get_instance(dcc_type: Optional[str] = None, port: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    获取指定条件的实例。

    Args:
        dcc_type: 按 DCC 类型筛选
        port: 按端口筛选

    Returns:
        匹配的第一个实例，如果没有返回 None
    """
    for info in list_instances():
        if dcc_type and info.get("dcc_type") != dcc_type:
            continue
        if port is not None and info.get("port") != port:
            continue
        return info
    return None


def find_instances(dcc_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """按 DCC 类型筛选实例"""
    if dcc_type is None:
        return list_instances()
    return [info for info in list_instances() if info.get("dcc_type") == dcc_type]
