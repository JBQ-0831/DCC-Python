# DCC Python 工具 py2 兼容改造 —— 闭环总结

> 日期：2026-07-31 ｜ 负责人：阿杰（DCC Python 工具开发）｜ 汇报对象：蒋哥

## 一、结论先行

面向 Maya / 3ds Max / Substance Painter·Designer / Houdini / Blender 等**仅支持 Python 2.7** 的 DCC 软件，本次把 `dcc-bridge` 调试桥接工具的 py2 兼容改造**全部落地、零回归、可交付**。

四大原始需求逐条对齐：

| # | 需求 | 落地情况 |
|---|------|----------|
| ① | TCP 服务 py 代码兼容 py2 | ✅ protocol / adapters(6子类) / server / start / discovery / execute / reload / debug 全部改为 py2 兼容写法（无 f-string、无类型注解、无无参 super、无 async） |
| ② | 注入 DCC 的自启动脚本兼容 py2 | ✅ `setup/base.py` 生成的启动脚本字符串纯 py2 兼容（f-string 仅用于"生成"阶段，结果字符串无残留） |
| ③ | setup/unsetup/cleanup 按 DCC Python 版本门控 | ✅ `setup/base.py` 的 `_get_python_major_version` + `setup()`/`unsetup()` 门控：py3+ 才装卸 debugpy，py2 只注入/清理脚本 |
| ④ | VSCode attach debugger 时检测目标 py 版本，低于 3 弹提示 | ✅ `tcp-driver.ping()` 透传 `result.python_version` → `attach.ts` 主版本 < 3 时 `showErrorMessage` 弹右下角提示并中止 |

## 二、任务清单（T1–T10，全部 completed）

- **T1** 改造 `protocol.py` 兼容 py2
- **T2** 改造 `adapters/`（__init__ + base + 6 个 DCC 子类）
- **T3** 改造 `server.py`（ping 响应携带 `python_version`）
- **T4** 改造 `start.py` 与 `discovery.py`
- **T5** 改造 `execute.py` 与 `reload.py`
- **T6** 改造 `debug.py` 兼容 py2
- **T7** `setup/base.py` 增加 Python 版本检查与门控
- **T8** VSCode 端 attach 增加 Python 版本检测（ts 端 `IDCCDriver.ping()` + `attach.ts` 门控弹窗，tsc 通过）
- **T9** 静态 py2 兼容性扫描脚本 `tools/check_py2_compat.py`（AST 分析 F001–F008 / W001–W005），作 CI 门禁
- **T10** py3 回归测试与验证（`test_py2_compat.py` + `test_setup_py2_gate.py`，并修复 `test_server.py` 遗留 import bug）

## 三、测试结果（分段验证 280 passed，全绿）

WorkBuddy 沙箱默认 120s 超时 + safe-delete 噪音，全目录一次性跑会被杀进程，故分段执行：

| 批次 | 范围 | 结果 |
|------|------|------|
| 核心 4 文件 | test_server / test_houdini / test_py2_compat / test_setup_py2_gate | **53 passed** |
| test_maya | Maya 适配器（mock 路径） | **59 passed** |
| 其余 5 文件 | blender / blender_adapter / designer / max / painter | **168 passed** |
| **合计** | 280 collected | **280 passed，零失败** |

> 所有 DCC 真机测试在沙箱均走 mock/adapter 路径，无需真实 DCC 宿主即可跑绿；依赖真实宿主的 host-dependent 用例仍建议在 DCC 内用 `dcc-bridge-cli` 复核。

## 四、架构铁律（已固化）

- **只有被 DCC 进程内 Python `import` 的模块需 py2 兼容**：`dcc_bridge` 包根 + `adapters/*`。
- **跑系统 py3、不受 py2 约束**：`setup/` `cli/` `dcc_names.py` `__main__.py`（这些在用户机器/CI 上以 py3 运行）。
- 扫描脚本默认排除上述 py3 模块，避免误报。

## 五、沙箱 pytest 注意事项（抓手）

1. **必须 `python -B` 禁字节码缓存**：WorkBuddy 沙箱 junction + `.pyc` 视图错位，`import` 走旧 `.pyc` 而 `open(__file__)` 走新 `.py`，会制造"源码有方法、import 无方法"的假象（`-B` 跑全过）。用户本机真实目录不受影响。
2. **全目录跑注意超时**：280 测试需 5~10 分钟，超 120s 会被工具杀；建议分段或延长 timeout。
3. **safe-delete 噪音可忽略**：pytest 清理临时目录触发钩子打印 JSON 到 stderr，不影响测试结果，重定向 stdout 即可干净查看。

## 六、后续动作（拉通建议）

- 真机 DCC（Maya / Max / Substance / Blender / Houdini）内用 `dcc-bridge-cli` 跑 host-dependent 用例，做最终端到端确认。
- 提交 PR 前，CI 串入 `tools/check_py2_compat.py` 作为 py2 兼容性门禁，防止后续提交引入 py3-only 语法。
- 可选：把"py2 兼容改造 + 沙箱 pytest 注意事项"沉淀为项目 skill，避免下次重复踩坑。
