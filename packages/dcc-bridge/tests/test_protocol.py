# -*- coding: utf-8 -*-
"""
protocol.py 单元测试

回归(桥本身): 验证 encode_message 在 payload 含非 ASCII 字节(str in py2 /
bytes in py3)时不会因 json.dumps(ensure_ascii=False) 用 ASCII 解码而崩溃,
从而确保真实错误(如含中文源码的 SyntaxError traceback)能正常序列化发回 VSCode,
而不是被 'ascii' codec can't decode ... 掩盖。

测试刻意用 .encode("utf-8") 的 bytes 值来模拟 py2 下 traceback.format_exc()
返回的 str(字节)——这是触发原 bug 的真实形态。
"""

from dcc_bridge.protocol import Response, decode_message, encode_message

_CHINESE_SRC = u"tool1.clicked.connect(lambda :print(u'\u70b9\u51fb\u4e86\u6d4b\u8bd5\u6309\u94ae1'))"


class TestEncodeMessageNonAscii:
    def test_bytes_with_chinese_traceback_does_not_raise(self):
        # 模拟 py2 下 traceback.format_exc() 返回的 str(bytes),内含中文源码
        payload = {
            "id": "1",
            "error": {
                "message": "invalid syntax (<string>, line 2)",
                "traceback": _CHINESE_SRC.encode("utf-8"),
            },
        }
        # 修复前这里会抛 UnicodeDecodeError(py2) / TypeError(py3),响应发不出去
        data = encode_message(payload)
        assert isinstance(data, bytes)

    def test_non_ascii_payload_round_trips(self):
        payload = {
            "id": "1",
            "error": {
                "message": "invalid syntax (<string>, line 2)",
                "traceback": _CHINESE_SRC.encode("utf-8"),
            },
        }
        data = encode_message(payload)
        resp = decode_message(data)
        assert resp.error["traceback"] == _CHINESE_SRC
        assert resp.error["message"] == "invalid syntax (<string>, line 2)"

    def test_response_failure_with_chinese_round_trips(self):
        # 端到端:Response.failure 构造的含中文 traceback 的响应能正常编码并还原
        chinese_trace = (
            u"  File '<string>', line 2\n    " + _CHINESE_SRC + u"\nSyntaxError: invalid syntax"
        )
        resp = Response.failure(id="1", message="invalid syntax", traceback=chinese_trace)
        data = encode_message(resp)
        decoded = decode_message(data)
        assert decoded.error["traceback"] == chinese_trace
        assert decoded.error["message"] == "invalid syntax"
