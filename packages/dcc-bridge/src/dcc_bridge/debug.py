# -*- coding: utf-8 -*-
"""
debugpy 安装 / 启动相关逻辑

Windows UAC 提权安装、subprocess 调用 pip、启动 debugpy 监听等。
本模块由 server.py 在 start_debugpy / install_debugpy 分支中懒导入，
因此即便在 py2 DCC 中也不会真正执行（debugpy 不支持 py2）。但模块必须能在
py2 下编译通过，故清除所有 f-string、注解等 py3-only 语法；并将
subprocess.run（py2 无）替换为跨版本 helpers。

兼容 Python 2.7 / 3.x。
"""

import ctypes
import io
import os
import subprocess
import sys
import tempfile
from ctypes import wintypes

# 模块级标志：debugpy.listen() 在 DCC 进程生命周期内只能调用一次，
# 重复调用会导致端口占用错误。VS Code 断开重连时复用已有监听。
_debugpy_listening = False


def get_python_path():
    """返回当前 Python 解释器路径，各 DCC 的 Adapter 可覆盖此方法"""
    return sys.executable


def _run_subprocess(cmd):
    """跨版本运行命令，返回 (returncode, stdout_text, stderr_text)。

    py2 无 subprocess.run，统一用 Popen + communicate；输出在 py2 为 bytes，
    统一解码为文本（utf-8 + replace 兜底）。
    """
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate()

    def _to_text(b):
        if isinstance(b, bytes):
            return b.decode("utf-8", errors="replace")
        return b

    return proc.returncode, _to_text(out), _to_text(err)


# ─── Windows UAC 提权安装（供 install_debugpy 在权限不足时调用）────────────
# Blender/Maya 等 DCC 的内置 Python 通常位于 C:\Program Files，受 UAC 保护。
# 非管理员进程调用其 pip 时无法写入 DCC 的 site-packages，pip 会回退到用户全局
# 目录，导致 DCC 内部 import debugpy 失败。下面用 ShellExecuteEx(runas) 提权后
# 再安装，确保包落到 DCC 自己的 site-packages。

class _SHELLEXECUTEINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hKeyClass", wintypes.HANDLE),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def _is_user_admin():
    """Windows 下返回当前进程是否为管理员；非 Windows 一律返回 True（无需提权）。"""
    if sys.platform != "win32" or ctypes is None:
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _shell_execute_ex_runas(exe, params, cwd=None):
    """以管理员权限（UAC）同步启动 exe，返回退出码。用户取消 UAC 时抛出 RuntimeError。"""
    sei = _SHELLEXECUTEINFO()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = 0x00000040  # SEE_MASK_NOCLOSEPROCESS：保留 hProcess 以便等待
    sei.hwnd = None
    sei.lpVerb = "runas"
    sei.lpFile = exe
    sei.lpParameters = params
    sei.lpDirectory = cwd
    sei.nShow = 1  # SW_SHOWNORMAL

    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei)):
        err = ctypes.GetLastError()
        if err == 1223:  # ERROR_CANCELLED：用户在 UAC 弹窗中点了"否"
            raise RuntimeError("用户取消了 UAC 提权（错误码 1223）")
        raise ctypes.WinError(err)

    h_process = sei.hProcess
    ctypes.windll.kernel32.WaitForSingleObject(h_process, 0xFFFFFFFF)
    exit_code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(h_process, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(h_process)
    return exit_code.value


def _run_pip_elevated(cmd):
    """Windows 下以管理员权限运行 pip 命令（install/uninstall），返回 (exit_code, 合并输出)。

    cmd 形如 [python_path, "-m", "pip", "install"|"uninstall", ...]，其中 python_path
    可能位于受保护的 C:\\Program Files。通过临时 bat 脚本 + ShellExecuteEx(runas) 提权，
    并把输出重定向到临时文件以便捕获。

    注意：不使用 PowerShell Out-File，因其在提权隔离会话中可能静默失败（utf8NoBOM 编码
    参数不识别、管道断裂等），导致输出丢失且 exit_code 仍为 0。
    cmd.exe 的 > 重定向是最可靠的选择。
    """
    pid = os.getpid()
    out_file = os.path.join(tempfile.gettempdir(), "dcc_bridge_debugpy_{0}.log".format(pid))
    bat_file = os.path.join(tempfile.gettempdir(), "dcc_bridge_debugpy_{0}.bat".format(pid))

    python_path = cmd[0]
    # 其余参数原样拼接；含空格的参数加引号
    pip_args = " ".join('"{0}"'.format(a) if " " in a else a for a in cmd[1:])
    # chcp 65001 确保 pip 输出被重定向为 UTF-8，便于后续读取
    bat_content = (
        "@chcp 65001 > nul\r\n"
        '@"{0}" {1} > "{2}" 2>&1\r\n'
    ).format(python_path, pip_args, out_file)

    print("[DEBUG] _run_pip_elevated: python_path={0}".format(python_path))
    print("[DEBUG] _run_pip_elevated: pip_args={0}".format(pip_args))
    print("[DEBUG] _run_pip_elevated: bat_file={0}".format(bat_file))
    print("[DEBUG] _run_pip_elevated: out_file={0}".format(out_file))
    print("[DEBUG] _run_pip_elevated: python exists={0}".format(os.path.exists(python_path)))
    print("[DEBUG] _run_pip_elevated: bat content:")
    for line in bat_content.strip().split("\n"):
        print("  | {0}".format(line))

    with io.open(bat_file, "w", encoding="ascii") as f:
        f.write(bat_content)
    print(
        "[DEBUG] _run_pip_elevated: bat written, size={0} bytes".format(
            os.path.getsize(bat_file)
        )
    )

    cmd_exe = os.environ.get("ComSpec", "cmd.exe")
    cmd_params = '/c "{0}"'.format(bat_file)
    print("[DEBUG] _run_pip_elevated: ShellExecuteEx runas exe={0}".format(cmd_exe))
    print("[DEBUG] _run_pip_elevated: ShellExecuteEx runas params={0}".format(cmd_params))

    try:
        exit_code = _shell_execute_ex_runas(cmd_exe, cmd_params)
        print(
            "[DEBUG] _run_pip_elevated: ShellExecuteEx returned exit_code={0}".format(
                exit_code
            )
        )
    except Exception as e:
        print("[ERROR] _run_pip_elevated: ShellExecuteEx failed: {0}".format(e))
        raise

    output = ""
    if os.path.exists(out_file):
        out_size = os.path.getsize(out_file)
        print(
            "[DEBUG] _run_pip_elevated: out_file exists, size={0} bytes".format(out_size)
        )
        try:
            with io.open(out_file, "r", encoding="utf-8", errors="replace") as f:
                output = f.read()
            print(
                "[DEBUG] _run_pip_elevated: out_file content ({0} chars):".format(
                    len(output)
                )
            )
            for line in output.strip().split("\n")[:30]:
                print("  | {0}".format(line))
            if output.count("\n") >= 30:
                print(
                    "  | ... ({0} lines total, truncated)".format(
                        output.count("\n")
                    )
                )
        except Exception as e:
            print("[ERROR] _run_pip_elevated: failed to read out_file: {0}".format(e))
    else:
        print("[DEBUG] _run_pip_elevated: out_file does NOT exist after ShellExecuteEx!")
        # 保留 bat/log 文件以便排查问题
        print("[DEBUG] _run_pip_elevated: keeping temp files for debugging:")
        print("  bat_file = {0}".format(bat_file))
        print("  out_file = {0}".format(out_file))
        return exit_code, output

    print(
        "[DEBUG] _run_pip_elevated: cleaning up {0}, {1}".format(bat_file, out_file)
    )
    for p in (bat_file, out_file):
        try:
            if os.path.exists(p):
                os.remove(p)
                print("[DEBUG] _run_pip_elevated: removed {0}".format(p))
        except OSError as e:
            print("[WARN] _run_pip_elevated: failed to remove {0}: {1}".format(p, e))

    return exit_code, output


def _safe_console_write(text):
    """安全地将文本写入 stdout，自动处理控制台编码不兼容的字符。

    Windows 中文系统控制台编码为 GBK，若输出中包含 GBK 无法编码的字符
    （如 BOM \\ufeff，即便已从源头去除仍有极小概率出现），
    直接 sys.stdout.write 会导致 UnicodeEncodeError。
    这里用 errors='replace' 兜底，并回退到 sys.stdout.encoding 真实编码。
    """
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode(encoding, errors="replace").decode(encoding))


def install_debugpy(python_path, pip_index_url=""):
    if python_path is None:
        return "[ERROR] install_debugpy: python_path is None, cannot install debugpy"

    cmd = [python_path, "-m", "pip", "install", "debugpy"]
    if pip_index_url:
        cmd.extend(["-i", pip_index_url])

    print("[DEBUG] install_debugpy: python_path={0}".format(python_path))
    print("[DEBUG] install_debugpy: sys.executable={0}".format(sys.executable))
    print("[DEBUG] install_debugpy: pip_index_url={0}".format(pip_index_url))
    print("[DEBUG] install_debugpy: running: {0}".format(" ".join(cmd)))

    # Windows 且非管理员时，普通进程无法写入 DCC 受 UAC 保护的 site-packages，
    # 必须先提权再安装，否则 pip 会回退到用户全局目录导致 DCC 内 import 失败。
    if sys.platform == "win32" and not _is_user_admin():
        print("[DEBUG] install_debugpy: non-admin process, elevating via UAC to install into DCC site-packages")
        try:
            exit_code, output = _run_pip_elevated(cmd)
        except RuntimeError as e:
            raise RuntimeError(
                "[ERROR] install_debugpy: UAC elevation failed (user may have cancelled): {0}".format(e)
            )
        _safe_console_write(output)
        if exit_code != 0:
            raise subprocess.CalledProcessError(exit_code, cmd)
        return output

    try:
        returncode, stdout, stderr = _run_subprocess(cmd)
        print("[DEBUG] install_debugpy: returncode={0}".format(returncode))
        _safe_console_write(stdout)
        if stderr:
            sys.stderr.write(stderr)

        # The old implementation invoked installation via VSCode plugin calling DCC Python, which required refreshing module cache and appending debugpy path for immediate discovery.
        # Now this function is called directly by `dcc setup`. Since dcc-bridge runs under global Python, this logic is no longer needed.
        # After running `dcc setup`, users launch DCC afterwards, and DCC Python will be able to load debugpy normally.

        return stdout
    except subprocess.CalledProcessError as e:
        print("[ERROR] install_debugpy failed: {0}".format(e))
        print("[ERROR] stdout: {0}".format(getattr(e, "stdout", "")))
        print("[ERROR] stderr: {0}".format(getattr(e, "stderr", "")))
        raise


def uninstall_debugpy(python_path, pip_index_url=""):
    if python_path is None:
        return "[ERROR] uninstall_debugpy: python_path is None, cannot uninstall debugpy"

    cmd = [python_path, "-m", "pip", "uninstall", "-y", "debugpy"]
    if pip_index_url:
        cmd.extend(["-i", pip_index_url])

    print("[DEBUG] uninstall_debugpy: python_path={0}".format(python_path))
    print("[DEBUG] uninstall_debugpy: running: {0}".format(" ".join(cmd)))

    # 与 install_debugpy 同理：Windows 非管理员进程无法删除受 UAC 保护的
    # DCC site-packages 中的 debugpy，需先提权再卸载。
    if sys.platform == "win32" and not _is_user_admin():
        print("[DEBUG] uninstall_debugpy: non-admin process, elevating via UAC to uninstall from DCC site-packages")
        try:
            exit_code, output = _run_pip_elevated(cmd)
        except RuntimeError as e:
            raise RuntimeError(
                "[ERROR] uninstall_debugpy: UAC elevation failed (user may have cancelled): {0}".format(e)
            )
        _safe_console_write(output)
        # pip uninstall 对"未安装"的包返回 0 并提示 Skipping，仍视为成功；
        # 仅当确实卸载失败（且非"未安装"）时才抛出。
        if exit_code != 0 and "not installed" not in output and "Skipping" not in output:
            raise subprocess.CalledProcessError(exit_code, cmd)
        return output

    try:
        returncode, stdout, stderr = _run_subprocess(cmd)
        print("[DEBUG] uninstall_debugpy: returncode={0}".format(returncode))
        _safe_console_write(stdout)
        if stderr:
            sys.stderr.write(stderr)
        return stdout
    except subprocess.CalledProcessError as e:
        # pip uninstall 对已不存在的包仍返回 0，这里仅在确实失败时提示
        combined = "{0}\n{1}".format(
            getattr(e, "stdout", ""), getattr(e, "stderr", "")
        )
        if "not installed" in combined or "Skipping" in combined:
            print("[DEBUG] uninstall_debugpy: debugpy 未安装，跳过")
            return combined
        print("[ERROR] uninstall_debugpy failed: {0}".format(e))
        print("[ERROR] stdout: {0}".format(getattr(e, "stdout", "")))
        print("[ERROR] stderr: {0}".format(getattr(e, "stderr", "")))
        raise


def start_debugpy_server(port, python_path, adapter=None):
    global _debugpy_listening

    if python_path is None:
        print(
            "[ERROR] start_debugpy_server: python_path is None, cannot start debugpy server"
        )
        return False

    if not os.path.exists(python_path):
        print("[WARN] Python executable not found at: {0}".format(python_path))
        return False
    else:
        print("[DEBUG] Python executable exists at: {0}".format(python_path))

    print(
        "[DEBUG] start_debugpy_server called with port={0}, python_path={1}".format(
            port, python_path
        )
    )

    try:
        import debugpy

        print("[DEBUG] debugpy imported successfully, version={0}".format(debugpy.__version__))
    except ImportError as e:
        print("[ERROR] Failed to import debugpy: {0}".format(e))
        print("[ERROR] Please run install_debugpy first")
        raise

    try:
        if adapter is not None and hasattr(adapter, "configure_debugpy"):
            adapter.configure_debugpy(python_path)
        else:
            debugpy.configure(python=python_path)
        print("[DEBUG] debugpy.configure() succeeded")
    except Exception as e:
        print("[ERROR] debugpy.configure() failed: {0}".format(e))
        raise

    # debugpy.listen() 在进程中只能调用一次，重复调用会导致端口占用
    # VS Code 断开重连时复用已有监听，无需重新 listen
    if _debugpy_listening:
        print("[DEBUG] debugpy already listening, reusing existing listener")
        return True

    try:
        debugpy.listen(port)
        _debugpy_listening = True
        print(
            "[DEBUG] debugpy.listen({0}) succeeded, debug server is now listening".format(
                port
            )
        )
    except RuntimeError as e:
        if "debugpy.listen() has already been called on this process" in str(e):
            print("[DEBUG] debugpy.listen() already called on this process, skipping")
            _debugpy_listening = True
            return True
        print("[ERROR] debugpy.listen() RuntimeError: {0}".format(e))
        raise
    except Exception as e:
        print(
            "[ERROR] debugpy.listen() failed with unexpected error: {0}: {1}".format(
                type(e).__name__, e
            )
        )
        raise

    return True
