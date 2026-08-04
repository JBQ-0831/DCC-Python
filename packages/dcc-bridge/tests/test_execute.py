# -*- coding: utf-8 -*-
import sys

import pytest

from dcc_bridge.execute import _safe_emit, execute_code, handle_exception


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
