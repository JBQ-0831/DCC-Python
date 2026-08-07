# -*- coding: utf-8 -*-
"""
DCC 内代码执行模块

提供在 DCC 主线程中执行 Python 代码字符串 / 文件的能力，并尽量复现
交互式 REPL 的「打印最后一个表达式结果」行为，以及跨版本兼容的异常回溯。

兼容 Python 2.7 / 3.x：
- 不使用 from __future__ import annotations、f-string、签名/变量注解、
  PEP 604 联合类型等 py3-only 语法。
- AST 节点构造按版本分支：py3.8+ 用 ast.Constant，py3.0~3.7 用 ast.NameConstant，
  py2 用 ast.Name(id="None")；位置信息（lineno/end_lineno）仅在 py3 传入。
- 异常回溯兼容 py2：traceback 对象通过 sys.exc_info() 显式传入（py2 无
  exception.__traceback__），格式化统一用元组形式（py2/py3 的 format_list 均支持），
  链式异常 __context__ 用 getattr 兜底（py2 无该属性）。
- 文件读取用 io.open 以支持 encoding 参数。
"""

import ast
import io
import os
import sys
import traceback


def _make_none_node(pos=None):
    """构造表示 None 的 AST 节点（按 Python 版本分支）。

    pos: py3 下携带 lineno/col_offset/end_* 的位置信息字典（py2 下为空）。
    """
    pos = pos or {}
    if sys.version_info >= (3, 8):
        return ast.Constant(value=None, **pos)
    elif sys.version_info >= (3, 0):
        return ast.NameConstant(value=None, **pos)
    else:
        # py2 中 None 是名字（不是常量节点）
        return ast.Name(id="None", ctx=ast.Load(), **pos)


def get_exec_globals():
    if "__VsCodeVariables__" not in globals():
        globals()["__VsCodeVariables__"] = {
            "__builtins__": __builtins__,
            "__IsVsCodeExec__": True,
        }
    return globals()["__VsCodeVariables__"]


def find_package(filepath):
    normalized_filepath = os.path.normpath(filepath).lower()

    valid_packages = []
    for path in sys.path:
        normalized_path = os.path.normpath(path).lower()
        if normalized_filepath.startswith(normalized_path):
            package = os.path.relpath(os.path.dirname(filepath), path).replace(
                os.sep, "."
            )
            if package != ".":
                valid_packages.append(package)

    if valid_packages:
        return min(valid_packages, key=len)

    return ""


def add_print_for_last_expr(parsed_code):
    if parsed_code.body:
        last_expr = parsed_code.body[-1]
        if isinstance(last_expr, ast.Expr):
            temp_var_name = "_"

            # py2 下 ast 节点本就支持 lineno 字段，但此处手工构造的新节点故意留空
            # （pos={}），统一交给 execute_code 里 compile 前的
            # ast.fix_missing_locations(parsed_code) 一次性补齐，避免 py2/py3 双分支重复。
            pos = {}
            if sys.version_info >= (3, 8):
                pos = {
                    "lineno": getattr(last_expr, "lineno", 1),
                    "col_offset": getattr(last_expr, "col_offset", 0),
                    "end_lineno": getattr(last_expr, "end_lineno", 1),
                    "end_col_offset": getattr(last_expr, "end_col_offset", 0),
                }
            elif sys.version_info >= (3, 0):
                pos = {
                    "lineno": getattr(last_expr, "lineno", 1),
                    "col_offset": getattr(last_expr, "col_offset", 0),
                }

            none_node_for_compare = _make_none_node(pos)
            none_node_for_else = _make_none_node(pos)

            test = ast.Compare(
                left=ast.Name(id=temp_var_name, ctx=ast.Load(), **pos),
                ops=[ast.IsNot()],
                comparators=[none_node_for_compare],
                **pos
            )
            print_call = ast.Call(
                func=ast.Name(id="print", ctx=ast.Load(), **pos),
                args=[ast.Name(id=temp_var_name, ctx=ast.Load(), **pos)],
                keywords=[],
                **pos
            )
            print_stmt = ast.IfExp(
                test=test,
                body=print_call,
                orelse=none_node_for_else,
                **pos
            )
            temp_var_assign = ast.Assign(
                targets=[ast.Name(id=temp_var_name, ctx=ast.Store(), **pos)],
                value=last_expr.value,
                **pos
            )

            parsed_code.body[-1] = temp_var_assign
            parsed_code.body.append(ast.Expr(value=print_stmt, **pos))

    return parsed_code

def safe_str(s):
    if isinstance(s, bytes):
        return s.decode("utf-8", errors="replace")
    return s

def format_exception(exception_in, filename, code, tb=None, num_ignore_tracebacks=0):
    if tb is None:
        tb = getattr(exception_in, "__traceback__", None)

    seen_exceptions = set()
    messages = []
    lines = code.splitlines()

    exception = exception_in
    while exception:
        if id(exception) in seen_exceptions:
            break
        seen_exceptions.add(id(exception))

        traceback_stack = []
        for frame_summary in traceback.extract_tb(tb):
            if num_ignore_tracebacks > 0:
                num_ignore_tracebacks -= 1
                continue

            # py2: extract_tb 返回元组 (filename, lineno, name, line)
            # py3: 返回 FrameSummary 对象，需取属性
            if isinstance(frame_summary, tuple):
                fs_filename, fs_lineno, fs_name, fs_line = frame_summary
            else:
                fs_filename = frame_summary.filename
                fs_lineno = frame_summary.lineno
                fs_name = frame_summary.name
                fs_line = frame_summary.line

            if fs_filename == filename and (
                fs_lineno is not None and 0 < fs_lineno <= len(lines)
            ):
                line = lines[fs_lineno - 1]
            else:
                line = fs_line

            tb_filename = "{0}:{1}".format(fs_filename, fs_lineno)
            # format_list 在 py2/py3 均接受 (filename, lineno, name, line) 元组
            traceback_stack.append((tb_filename, fs_lineno, fs_name, line))

        if isinstance(exception, SyntaxError):
            if exception.filename == filename:
                exception.filename = "%s:%s" % (exception.filename, exception.lineno)
                if exception.lineno is not None and 0 < exception.lineno <= len(lines):
                    line = lines[exception.lineno - 1]
                    exception.text = line

        text = "Traceback (most recent call last):\n"
        text += "".join(safe_str(line) for line in traceback.format_list(traceback_stack))
        text += "".join(safe_str(line) for line in traceback.format_exception_only(type(exception), exception))
        messages.append(text)

        # py2 异常无 __context__ 属性，getattr 兜底返回 None
        exception = getattr(exception, "__context__", None)

    return "\nDuring handling of the above exception, another exception occurred:\n\n".join(
        reversed(messages)
    )


def _safe_emit(text):
    """py2/py3 兼容安全输出。

    部分 DCC 宿主（如 3ds Max 2019 的 py2.7）会把 stdout 劫持为「只收 unicode」
    的流；py2 下把含非 ASCII 字节的 str 写进去会抛 TypeError / UnicodeEncodeError。
    这里统一把内容转成 unicode 输出，并对极端情况兜底 encode，避免「为了打印错误
    而抛出第二个错误」从而掩盖真实异常。
    """
    if sys.version_info[0] == 2 and isinstance(text, str):
        text = text.decode("utf-8", "replace")
    try:
        sys.stdout.write(text + u"\n")
    except (UnicodeEncodeError, TypeError):
        sys.stdout.write((text + u"\n").encode("utf-8", "replace"))


def handle_exception(
    exception, filename, code, use_colors, num_ignore_tracebacks=0, tb=None
):
    traceback_message = format_exception(
        exception, filename, code, tb=tb, num_ignore_tracebacks=num_ignore_tracebacks
    )

    if use_colors:
        traceback_message = "\033[0m\n\033[91m".join(traceback_message.splitlines())
        traceback_message = "\033[91m" + traceback_message + "\033[0m"

    # 输出失败（如 py2 unicode stdout）不应掩盖真实异常信息，故内部兜底
    try:
        _safe_emit(traceback_message)
    except Exception:
        pass


def execute_code(code, filename, debugging, exec_globals=None):
    if exec_globals is None:
        exec_globals = get_exec_globals()

    try:
        parsed_code = ast.parse(code, filename)
    except (SyntaxError, ValueError):
        exc_type, exc_val, exc_tb = sys.exc_info()
        handle_exception(
            exc_val, filename, code, use_colors=debugging,
            num_ignore_tracebacks=2, tb=exc_tb
        )
        raise

    parsed_code = add_print_for_last_expr(parsed_code)

    # 兜底防御（选中单行执行线）：若共享 globals 里残留了非法的 __package__
    # （空串 "" 或 非 str 非 None），本次执行前清掉，让 import 走 __name__ 缺省。
    # 只动 __package__ 这一个键，绝不碰用户变量，保证「选中单行记住上次变量」需求不受影响。
    _pkg = exec_globals.get("__package__")
    if _pkg is not None and (not isinstance(_pkg, str) or _pkg == ""):
        exec_globals.pop("__package__", None)

    try:
        # py2/py3 通用、幂等：给 add_print_for_last_expr 手工改写出的 AST 节点
        # 补上缺失的 lineno（py3 下节点本就带位置信息，无影响；py2 节点无
        # col_offset 字段会被自动跳过）。Python 2.7 的 compile() 强制要求每个
        # stmt 节点有 lineno，否则抛「required field "lineno" missing from stmt」。
        ast.fix_missing_locations(parsed_code)
        exec(compile(parsed_code, filename, "exec"), exec_globals)
    except Exception:
        exc_type, exc_val, exc_tb = sys.exc_info()
        handle_exception(
            exc_val, filename, code, use_colors=debugging,
            num_ignore_tracebacks=1, tb=exc_tb
        )
        raise


def main(exec_file, exec_origin, name_var=None, is_debugging=False):
    exec_globals = get_exec_globals()

    exec_globals["__file__"] = exec_origin
    if name_var:
        exec_globals["__name__"] = name_var
    elif "__name__" in exec_globals:
        exec_globals.pop("__name__")

    # __package__ 仅对包内脚本有意义；顶层脚本（不在任何 sys.path 包前缀下）
    # find_package 返回 ""。Autodesk 魔改的 Maya 2018 (py2.7) 把 __package__ = ""
    # 也判为非法，会抛 ValueError: __package__ set to non-string。故空串时直接 pop
    # 掉该键，让 import 机制走 __name__ 兜底。注意：只动 __package__ 这一个键，
    # 绝不碰用户变量（共享字典 __VsCodeVariables__ 里的 a/b/c 等原封不动保留）。
    pkg = find_package(exec_origin)
    if pkg:
        exec_globals["__package__"] = pkg
    else:
        exec_globals.pop("__package__", None)

    with io.open(exec_file, "r", encoding="utf-8") as vscode_in_file:
        execute_code(
            vscode_in_file.read(), exec_origin, is_debugging, exec_globals
        )

    if is_debugging:
        print(">>>")
