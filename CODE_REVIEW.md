# 代码审查标准与流程（DCC Python ToolKit）

> 目的：用一套**可落地、有门禁、贴合本仓库双栈实际**的审查机制，把"代码质量参差不齐"从根上治好。
> 适用范围：`packages/dcc-bridge`（Python 2.7/3 兼容，跑在 DCC 内部）、`packages/vscode-extension`（TypeScript 扩展）。
> 原则：建设性、教人而非批人；结论先行、证据说话（引用行号）；**🔴 Blocker 不过绝不合并**。

---

## 1. 角色与职责

| 角色 | 职责 |
|---|---|
| **Author**（提交者） | 开发前先按本清单自检 → 本地跑通门禁脚本 → 提 PR 并写清「为什么改」 |
| **Reviewer**（≥1 人，复杂改动 ≥2 人） | 按 §5 清单逐项审查，打优先级标签（🔴/🟡/💭），给出可执行的修改建议 |
| **门禁（CI 自动）** | 硬卡：门禁不绿，PR 不可合入（见 §4） |

---

## 2. 审查流程（5 步闭环）

1. **自检**：Author 本地跑 §4 全部门禁脚本，全绿后再提 PR。
2. **提 PR**：带模板（变更摘要 + 动机 + 测试证明 + 风险点），禁止「fix bug」式空描述。
3. **指派 + 跑门禁**：指派 Reviewer；CI 自动跑门禁并贴结果。
4. **审查**：Reviewer 按 §5 清单逐项过；🔴 必须修、🟡 协商、💭 可选。
5. **合入**：门禁全绿 + 至少 1 个 Approve 后方可合入；合并后删除草稿分支。

> 验收铁律：**只改代码不自动提交**。涉及 `git commit`/`push` 必须蒋先生本机显式操作（沙箱 git ref 机制受限，AI 不代提交）。

---

## 3. 自动化门禁（强制，必须配 CI）

本仓库当前**缺少 PR 审查 CI**，这是质量失控的主因。门禁脚本如下，建议落地为 GitHub Actions `pr.yml`（模板见 §7 附录）。

### Python（`packages/dcc-bridge`）
```bash
cd packages/dcc-bridge
uv run python -m pytest tests/                                  # 全套单测（注意必须用 python -m，避免环境错位加载陈旧 dcc_bridge）
uv run python -m pytest tests/test_py2_compat.py tests/test_setup_py2_gate.py   # py2 兼容门禁，改适配器/execute 必跑
# 可选：pyflakes / black --check
```

### TypeScript（`packages/vscode-extension`）
```bash
cd packages/vscode-extension
npm run check-types   # tsc --noEmit，零报错
npm run lint          # eslint src
node esbuild.js       # 打包成功，dist/extension.js 刷新
```

> ⚠️ **py2 测试环境坑**（实测）：`uv run pytest` 可能加载到另一套 dcc_bridge，表现像没生效；一律用 `uv run python -m pytest`。整套 `tests/` 输出超长会被沙箱截断伪报 exit 1，改跑单个/少量测试文件看结论。

---

## 4. 审查清单（核心）

按优先级标注：`🔴 Blocker`（合入前清零） / `🟡 Suggestion`（应修，协商） / `💭 Nit`（可选）。

### 🔴 Blocker — Python / DCC 适配铁律（本项目实战踩坑沉淀）

- **py2.7 兼容禁忌**（仅作用于「被 DCC 内 `import` 的模块」：`dcc_bridge` 包根、`adapters/*_adapter.py`、`protocol`/`client`/`server`/`execute`/`discovery`/`start`/`compat` 等）：
  - 禁止：f-string、变量注解、`from __future__ import annotations`、无参 `super()`、`async`、f-string 内花括号转义。
  - 经典类必须 `class X(object)`；被 `import` 的模块写 `# coding: utf-8`；入口 `.py`（被 `exec`）**不写** `# coding`。
  - 改动后必须 `uv run python -m pytest tests/test_py2_compat.py` 走 py2 扫描 0 错 0 警。
- **DCC 适配器命名铁律**：`adapters/` 下模块一律 `<dcc>_adapter.py`（如 `maya_adapter.py`），**绝不能用 `maya.py`/`max.py`**——会被 DCC 内置同名顶层模块遮蔽，导致 `from maya import cmds` 失败（`cannot import name cmds`）。重命名用 `git mv` 保留历史。
- **Maya import 姿势**：`get_version()` 等一律 `import maya.cmds as cmds`，**不用** `from maya import cmds`（Maya 自启动上下文等价写法不等价）。
- **变量记忆机制不可破坏**：`execute.py` 的 `get_exec_globals()` 返回模块级共享字典 `__VsCodeVariables__`，跨执行复用（实现 VSCode 选中单行记住上次变量，对齐各 DCC 自带脚本编辑器单行行为）。重构只能动 `__package__` 等元数据键，**绝不清空用户变量 / 重建该字典**。
- **`__package__` 契约**：空串或非 str/非 None 一律 `pop`，**不能写 `""` 进 globals**（Maya 2018 内置 py2 魔改 import 把空串判为非法 → `ValueError: __package__ set to non-string`）。
- **双启动规避不可破坏**：主脚本放 `<script_dir>/dcc_bridge/` 隔离子目录；launcher/启动块**写死绝对路径**，`os.path.dirname(__file__)` 这类依赖 `__file__` 的写法**禁用**（Maya userSetup.py / Houdini uiready.py 被 `exec` 时不提供 `__file__` → `NameError`）。
- **安全 / 正确性**：TCP JSON-RPC 必须有鉴权；不拼命令/SQL；路径用安全 `join`；不引入循环 `import`；不破坏 `setup` 模块（py3 跑 `dcc setup` CLI，命名空间安全，可自由用 f-string/注解）。

### 🔴 Blocker — TypeScript / 扩展铁律

- **`TreeView.reveal` 契约**：注册的 `TreeDataProvider` **必须实现 `getParent(element)`**（扁平结构返回 `null`），否则运行期 `reveal` 抛 `Required registered TreeDataProvider to implement 'getParent'`。`tsc` 不强制，必须靠人工+运行期验收。
- **上下文命令脆弱性**：`list.focus` / `list.select` 是 VS Code **上下文命令**，仅在树有焦点时注册，缺失时必须静默吞错（try/catch 不重试不告警），不能当 `reveal` 失败记 warning。
- **类型/编译**：`npm run check-types`（`tsc --noEmit`）零报错；`node esbuild.js` 打包成功且 `dist/extension.js` 已刷新（改 TS 后必须重打包，否则 VSCode 跑旧产物）。
- **pythonPath 概念不混淆**：扩展配置 `dcc-python-toolkit.pythonPath`（给扩展自身找 dcc-bridge 用）≠ DCC 实例 `python_path`（实例解释器，透传进 `TCPDriver`），方向别搞反。

### 🟡 Suggestion（应修，协商）

- **输入校验**：`dcc status` JSON 解析容错、端口 `NaN` 防护、字段缺失兜底（本项目曾因端口类型不一致炸过）。
- **命名清晰**：`DashboardItem`/变量名表达意图；命令/方法名与行为一致。
- **测试覆盖**：重要路径补 pytest（如 py2 兼容回归、adapter 行为）；关键修复必须带回归测试（参考 `test_execute.py::TestPackageNonStringRegression`）。
- **性能**：避免 N+1、避免重复 `_loadInstances()`；Dashboard 3 秒 `refresh()` 不应触发多余连接。
- **代码重复**：跨 adapter 的通用逻辑抽到 `base_adapter.py`。

### 💭 Nit（可选）

- 风格：`black` / `eslint` 已管则忽略。
- **文档同步**：README 必须与功能一致（本项目曾因文档落后于代码被点名，纯靠代码实证归纳改动）。
- 替代方案探讨（仅建议，不阻塞合入）。

---

## 5. 优先级与处置 SLA

| 优先级 | 合入要求 | Reviewer 动作 |
|---|---|---|
| 🔴 Blocker | 合入前**必须清零** | 不 Approve，逐条指出修改点 |
| 🟡 Suggestion | 作者与 Reviewer 协商，重大功能建议修 | 留言建议，可后续跟进 |
| 💭 Nit | 可选 | 备注即可 |

---

## 6. 复盘机制

每迭代回顾「漏审导致的线上坑」，补进 §4 清单（本项目已有大量实战坑：py2 兼容、适配器遮蔽、变量记忆、`__file__` 缺失、`__package__` 空串、reveal/getParent/list 命令脆弱性——均应视为永久 Blocker 项，改对应模块时强制复核）。

---

## 7. 附录：PR 门禁 CI 模板（建议落地为 `.github/workflows/pr.yml`）

```yaml
name: PR Review Gate
on:
  pull_request:
    branches: [main, feat/py2-dcc-support]
jobs:
  python:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: packages/dcc-bridge
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --extra dev
      - run: uv run python -m pytest tests/ -q
      - run: uv run python -m pytest tests/test_py2_compat.py tests/test_setup_py2_gate.py -q
  extension:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: packages/vscode-extension
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-node@v6
        with: { node-version: 22 }
      - run: npm ci
      - run: npm run check-types
      - run: npm run lint
      - run: node esbuild.js
```

> 落地点：本模板为建议，是否启用由蒋先生拍板；启用后 PR 页即自动显示门禁红绿，质量失控从根上堵死。
