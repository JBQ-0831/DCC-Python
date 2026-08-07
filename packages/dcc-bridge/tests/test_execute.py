# -*- coding: utf-8 -*-
import sys

import pytest

from dcc_bridge.execute import (
    _safe_emit,
    execute_code,
    find_package,
    get_exec_globals,
    handle_exception,
    main,
)


def test_execute_code_runs_normal_code():
    # 正常代码不应抛异常
    execute_code("x = 1 + 1", "<test>", False)


def test_execute_code_raises_on_runtime_error():
    # 关键语义：代码运行时异常必须冒泡（让 server 返回 failure），
    # 而不是被静默吞掉返回 success=true
    with pytest.raises(ZeroDivisionError):
        execute_code("1 / 0", "<test>", False)


def test_execute_code_raises_on_syntax_error():
    with pytest.raises(SyntaxError):
        execute_code("def foo(:", "<test>", False)


class _UnicodeOnlyStdout(object):
    """模拟 3ds Max 2019(py2.7) 的 stdout：只收 unicode，收到 bytes(str) 抛 TypeError。"""

    def write(self, data):
        if isinstance(data, bytes):
            raise TypeError("unicode argument expected, got 'str'")
        return len(data)


def test_safe_emit_writes_unicode_without_crash():
    # 贴合真实场景：stdout 收 unicode 时，_safe_emit 应能正常写入且不崩
    old = sys.stdout
    sys.stdout = _UnicodeOnlyStdout()
    try:
        _safe_emit(u"hello \u4e16\u754c")  # 不应抛异常
    except Exception as exc:  # pragma: no cover
        pytest.fail("safe_emit raised unexpectedly: " + repr(exc))
    finally:
        sys.stdout = old


class _BoomStdout(object):
    """彻底坏掉的 stdout：任何 write 都抛 TypeError。"""

    def write(self, data):
        raise TypeError("stdout is dead")


def test_handle_exception_does_not_crash_on_bad_stdout():
    # 痛点：打印错误时若 stdout 坏掉，绝不能再抛出第二个异常
    # 否则会掩盖真实异常（Max 2019 py2 上踩过的坑）
    old = sys.stdout
    sys.stdout = _BoomStdout()
    try:
        handle_exception(ValueError("real error"), "<test>", "1/0", False)
    except Exception as exc:  # pragma: no cover
        pytest.fail("handle_exception should swallow emit errors, but raised: " + repr(exc))
    finally:
        sys.stdout = old


class TestPackageNonStringRegression:
    """回归：Maya 2018 (py2.7) 下 __package__ = "" 触发 ValueError。

    根因：文件执行线 main() 原无条件写 __package__ = find_package(...)，顶层脚本
    （不在任何 sys.path 包前缀下）返回 ""，被 Maya 2018 魔改 import 判为非法。
    修复：空串 pop 掉、走 __name__ 兜底；execute_code 入口也兜底清空串。
    边界：只动 __package__ 这一个键，用户变量（共享字典 __VsCodeVariables__）不受影响，
    保证「选中单行记住上次变量」的需求不被破坏。
    """

    def _clean_pkg(self):
        # 隔离：每个用例开头清掉共享 globals 里可能残留的 __package__，避免相互干扰
        get_exec_globals().pop("__package__", None)

    def test_find_package_top_level_returns_empty(self):
        # 根因实证：不在任何 sys.path 前缀下的文件，find_package 返回空串
        import os
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".py")
        os.close(fd)
        try:
            assert find_package(path) == ""
        finally:
            os.remove(path)

    def test_main_pops_empty_package_for_top_level_script(self, tmp_path):
        # 文件执行线：顶层脚本的 __package__ 应为空（被 pop），且 import 不报错
        script = tmp_path / "1.py"
        script.write_text("import sys\nprint(sys.path)\n", encoding="utf-8")
        # tmp_path 不在 sys.path 包前缀下 -> find_package 返回 "" -> pop
        self._clean_pkg()
        main(str(script), str(script))  # 不应抛 ValueError
        assert "__package__" not in get_exec_globals()

    def test_main_keeps_user_vars(self, tmp_path):
        # 需求保住：文件执行写入的用户变量仍留在共享字典
        script = tmp_path / "var.py"
        script.write_text("a = 1\nimport sys\n", encoding="utf-8")
        self._clean_pkg()
        main(str(script), str(script))
        assert get_exec_globals().get("a") == 1

    def test_execute_code_pops_empty_package_and_keeps_user_vars(self):
        # 选中单行线：残留空串 __package__ 被 pop，且用户变量不丢
        g = dict(get_exec_globals())  # 独立副本，隔离单例
        g["__package__"] = ""  # 模拟 Maya 2018 残留
        execute_code("import sys\n", "<t>", False, exec_globals=g)
        assert "__package__" not in g  # 空串被 pop
        execute_code("b = 7\n", "<t2>", False, exec_globals=g)
        assert g["b"] == 7  # 用户变量保住

    def test_var_memory_across_executions(self):
        # 需求保住回归：先 a = 1 再 print(a) 仍能拿到（选中单行记住上次变量）
        g = dict(get_exec_globals())  # 独立副本，隔离单例
        self._clean_pkg()
        execute_code("a = 1\n", "<f1>", False, exec_globals=g)
        execute_code("print(a)\n", "<f2>", False, exec_globals=g)  # 不应抛 NameError
        assert g.get("a") == 1
