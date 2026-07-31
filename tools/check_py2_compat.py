# -*- coding: utf-8 -*-
"""
Py2 兼容性静态扫描器

作用:
    在已改造为"兼容 Python 2.7"的 DCC 模块上，静态检测是否残留 py3-only 写法，
    防止后续改动把 py2 不兼容语法重新引入（回归保护 / CI 门禁）。

只检测会导致 py2 下无法运行的问题，分两类:

硬错误(计入失败退出码):
    F001  from __future__ import annotations      (py2 编译期报 future feature 不存在)
    F002  f-string                                (py2 语法不认识 f"")
    F003  变量类型注解  x: T = ...                (py2 语法不认识 AnnAssign)
    F004  函数/返回类型注解                       (py2 语法不认识 : 注解)
    F005  无参 super()                            (py2 运行期 TypeError)
    F008  async / await                           (py2 语法不认识)

软警告(默认不计入失败，--strict 时计入):
    W001  importlib.reload      -> 应用 imp.reload(跨版本兼容导入)
    W002  subprocess.run        -> 应用 Popen + communicate
    W003  os.makedirs(exist_ok) -> 应 try/except OSError
    W004  open(encoding=)       -> 应用 io.open
    W005  import queue(裸)      -> 应 try/except 兼容导入 Queue

作用域(关键):
    只有"被 DCC 进程内 Python 解释器 import 的模块"才需要 py2 兼容。
    setup/、cli/、dcc_names.py、__main__.py 明确运行在系统 py3，默认排除，
    否则会把它们的 f-string / 注解误报。可用 --exclude 追加。

用法:
    python check_py2_compat.py [paths ...] [--exclude name ...] [-w] [--strict]
不传 paths 时默认扫描 packages/dcc-bridge/src/dcc_bridge。
"""

import argparse
import ast
import os
import sys


# 默认排除: 明确运行在系统 py3 的模块，不受 py2 约束
DEFAULT_EXCLUDES = ["setup", "cli", "dcc_names.py", "__main__.py"]


# 运行时软警告匹配规则
RUNTIME_HINTS = {
    "W001": "importlib.reload 在 py2 不存在，应使用 imp.reload（或跨版本兼容导入）",
    "W002": "subprocess.run 在 py2 不存在，应使用 subprocess.Popen + communicate",
    "W003": "os.makedirs(exist_ok=True) 在 py2 不支持，应 try/except OSError",
    "W004": "open(encoding=) 在 py2 不支持，应使用 io.open",
    "W005": "py2 模块名为 Queue，应 try/except 兼容导入",
}


class Finding(object):
    def __init__(self, rule, message, lineno):
        self.rule = rule
        self.message = message
        self.lineno = lineno

    def __str__(self):
        return "[{0}] line {1}: {2}".format(self.rule, self.lineno, self.message)


def _is_super_no_args(node):
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Name) or func.id != "super":
        return False
    return len(node.args) == 0 and len(node.keywords) == 0


def _annotation_nodes(func):
    """收集一个函数的所有注解节点(参数注解 + 返回注解)"""
    nodes = []
    args = func.args
    for a in args.args:
        if a.annotation is not None:
            nodes.append(a.annotation)
    for a in getattr(args, "kwonlyargs", []):
        if a.annotation is not None:
            nodes.append(a.annotation)
    if getattr(args, "vararg", None) is not None and args.vararg.annotation is not None:
        nodes.append(args.vararg.annotation)
    if getattr(args, "kwarg", None) is not None and args.kwarg.annotation is not None:
        nodes.append(args.kwarg.annotation)
    if func.returns is not None:
        nodes.append(func.returns)
    return nodes


def _check_runtime(node, findings):
    """运行期差异的软警告(名称匹配)"""
    # W001 importlib.reload
    if isinstance(node, ast.ImportFrom) and node.module == "importlib":
        for alias in node.names:
            if alias.name == "reload":
                findings.append(Finding("W001", RUNTIME_HINTS["W001"], node.lineno))
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        if node.value.id == "importlib" and node.attr == "reload":
            findings.append(Finding("W001", RUNTIME_HINTS["W001"], node.lineno))
    # W002 subprocess.run
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        if node.value.id == "subprocess" and node.attr == "run":
            findings.append(Finding("W002", RUNTIME_HINTS["W002"], node.lineno))
    if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
        if any(a.name == "run" for a in node.names):
            findings.append(Finding("W002", RUNTIME_HINTS["W002"], node.lineno))
    # W003 os.makedirs(exist_ok=)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
            if node.func.attr == "makedirs":
                if any(kw.arg == "exist_ok" for kw in node.keywords):
                    findings.append(Finding("W003", RUNTIME_HINTS["W003"], node.lineno))
    # W004 open(encoding=)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "open":
            if any(kw.arg == "encoding" for kw in node.keywords):
                findings.append(Finding("W004", RUNTIME_HINTS["W004"], node.lineno))
    # W005 import queue(裸)
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == "queue":
                findings.append(Finding("W005", RUNTIME_HINTS["W005"], node.lineno))


def scan_source(source, filename, check_runtime=False):
    findings = []
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        msg = "无法解析(可能本身含 py3-only 语法): {0}".format(e)
        findings.append(Finding("SYNTAX", msg, e.lineno or 0))
        return findings

    for node in ast.walk(tree):
        # F001 from __future__ import annotations
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            for alias in node.names:
                if alias.name == "annotations":
                    findings.append(Finding("F001", "from __future__ import annotations 在 py2 编译期报错", node.lineno))
        # F002 f-string
        if isinstance(node, ast.JoinedStr):
            findings.append(Finding("F002", "f-string 在 py2 不支持", node.lineno))
        # F003 变量注解
        if isinstance(node, ast.AnnAssign):
            findings.append(Finding("F003", "变量类型注解 x: T = ... 在 py2 不支持", node.lineno))
        # F004 函数/返回类型注解(一个函数只报一次)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _annotation_nodes(node):
                findings.append(Finding("F004", "函数/返回类型注解在 py2 不支持", node.lineno))
        # F005 无参 super()
        if _is_super_no_args(node):
            findings.append(Finding("F005", "无参 super() 在 py2 运行期 TypeError，应使用 super(Cls, self)", node.lineno))
        # F008 async / await
        if isinstance(node, ast.AsyncFunctionDef):
            findings.append(Finding("F008", "async def 在 py2 不支持", node.lineno))
        if isinstance(node, ast.Await):
            findings.append(Finding("F008", "await 表达式在 py2 不支持", node.lineno))

        if check_runtime:
            _check_runtime(node, findings)

    return findings


def _should_exclude(rel_path, excludes):
    parts = rel_path.split(os.sep)
    for ex in excludes:
        if ex in parts:
            return True
        if os.path.basename(rel_path) == ex:
            return True
    return False


def scan_file(filepath, repo_root, excludes, check_runtime):
    rel = os.path.relpath(filepath, repo_root)
    if _should_exclude(rel, excludes):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except (IOError, OSError) as e:
        return [Finding("READ", "无法读取文件: {0}".format(e), 0)]
    return scan_source(source, filepath, check_runtime=check_runtime)


def scan_targets(targets, excludes, check_runtime=False):
    """
    扫描给定的文件/目录列表，返回 {相对路径: [Finding]} 仅含非空项。

    targets:        list[str] 文件或目录路径
    excludes:       list[str] 需排除的路径片段或文件名
    check_runtime:  bool      是否启用运行期软警告
    """
    repo_root = os.getcwd()
    result = {}
    for target in targets:
        if os.path.isfile(target):
            files = [target]
        else:
            files = []
            for root, _dirs, names in os.walk(target):
                for name in names:
                    if name.endswith(".py"):
                        files.append(os.path.join(root, name))
        for fp in files:
            findings = scan_file(fp, repo_root, excludes, check_runtime)
            if findings:
                rel = os.path.relpath(fp, repo_root)
                result[rel] = findings
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Py2 兼容性静态扫描器")
    parser.add_argument("paths", nargs="*", help="要扫描的文件/目录，缺省为 dcc_bridge 包")
    parser.add_argument("--exclude", nargs="*", default=[], help="追加排除的路径片段/文件名")
    parser.add_argument("-w", "--warn-runtime", action="store_true", help="启用运行期差异软警告")
    parser.add_argument("--strict", action="store_true", help="软警告也计入失败退出码")
    args = parser.parse_args(argv)

    excludes = list(DEFAULT_EXCLUDES) + list(args.exclude)

    if args.paths:
        targets = args.paths
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(script_dir)
        default_target = os.path.join(repo_root, "packages", "dcc-bridge", "src", "dcc_bridge")
        targets = [default_target]

    findings_by_file = scan_targets(targets, excludes, check_runtime=args.warn_runtime)

    hard_rules = ("F", "SYNTAX", "READ")
    hard_count = 0
    warn_count = 0
    for rel, findings in sorted(findings_by_file.items()):
        print("== {0} ==".format(rel))
        for fnd in findings:
            print("  {0}".format(fnd))
            if fnd.rule.startswith(hard_rules):
                hard_count += 1
            else:
                warn_count += 1

    print("-" * 40)
    print("硬错误: {0}  软警告: {1}".format(hard_count, warn_count))

    if hard_count > 0:
        return 1
    if args.strict and warn_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
