"""
CLI 共享工具函数
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

from ..client import DCCClientError
from ..protocol import Response


def parse_response(response: Response) -> Dict[str, Any]:
    """把服务端 Response 对象转换为统一的结果字典"""
    if response.error:
        return {
            "success": False,
            "output": [],
            "error": response.error.get("message", "Unknown error"),
            "traceback": response.error.get("traceback"),
        }

    result = response.result or {}
    return {
        "success": result.get("success", False),
        "output": result.get("output", []),
        "error": None,
        "traceback": None,
    }


def print_result(result: Dict[str, Any], plain: bool = False) -> None:
    """输出执行结果"""
    if plain:
        if result["output"]:
            print("\n".join(result["output"]))
        if result["error"]:
            print("ERROR: {}".format(result["error"]), file=sys.stderr)
            if result["traceback"]:
                print(result["traceback"], file=sys.stderr)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def get_exit_code(result: Dict[str, Any]) -> int:
    """根据结果返回进程退出码"""
    if result.get("success"):
        return 0
    return 2 if result.get("error") else 1


def print_client_error(error: DCCClientError, plain: bool = False) -> int:
    """打印客户端连接错误并返回退出码"""
    result = {
        "success": False,
        "output": [],
        "error": str(error),
        "traceback": None,
    }
    print_result(result, plain=plain)
    return get_exit_code(result)
