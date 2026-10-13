# Change Log

## [1.3.3] - 2026-10-13

### 文档
- 插件 README：新增「环境要求」章节，明确最低 VS Code 版本为 1.106.0
- 插件 README：配置表补充 `environment.addWorkspaceToPath`
- 插件 README：开发章节补充 `package` / `vsix` / `vsix:dry` 打包命令
- dcc-bridge README：新增「py2 中文报错的正确姿势」，说明 `print` 语句在 py2 的 lambda 中不可用，以及真实错误被序列化错误掩盖时的排查思路
- 根 README：架构图目录名由过时的 `vscode-maya-python/` 更正为 `vscode-dcc-python/`

## [1.3.2] - 2026-10-13

### 修复
- **py2 中文执行失败时看不到真实错误**：`dcc_bridge.protocol` 新增 `_ensure_unicode`，在序列化前把 `traceback` 等字符串中的字节统一归一为 `unicode`。此前 py2 下 `json.dumps(ensure_ascii=False)` 遇到回溯中嵌着的中文源码字节会尝试用 ASCII 解码并崩溃（`UnicodeDecodeError`），导致响应发不出去，真实的 `SyntaxError` 被 `'ascii' codec can't decode` 完全掩盖。现可正常显示完整回溯与中文源码行。
- 服务端发送失败日志补充 `traceback.format_exc()`，避免二次崩溃再次掩盖原因。

### 变更
- **最低 VS Code 版本由 1.108.0 降至 1.106.0**，可在低版本 VS Code 中安装。
- 入口点文件选择改用 1.106 原生 API（`asRelativePath` + 字符串数组 QuickPick + `Uri.joinPath`），替换 `QuickPickItem.resourceUri` 与 `QuickPickOptions.prompt` 等更高版本专属调用。
- `dcc-bridge` 开发依赖新增 `ovsx`，用于 Open VSX 发布。
- `.vscodeignore` 排除 `.codebuddy` / `.workbuddy`，避免本地工作区记忆文件被打进安装包。

### 变更（发布流水线）
- VS Code 插件发布目标调整为 **VS Marketplace + Open VSX 双商店**，插件只构建一次、两商店复用同一产物，确保版本一致。
- CLI 仅发布到 PyPI 正式环境，废弃此前将 TestPyPI / Open VSX 视作测试通道的设计。

## [1.3.1] - 2026-07-29

### 修复
- dcc-bridge README.md：`dcc setup` 和 `dcc unsetup` 示例注释遗漏 Houdini 和 Blender
- vscode-extension README.md：配置表遗漏 `pip.indexUrl` 配置项说明

## [1.3.0] - 2026-07-29

### 变更
- dcc-bridge README.md 补全 Houdini 和 Blender 的注入位置、版本发现机制文档
- Houdini 适配器说明：使用 `hou.ui.addEventLoopCallback` + 队列轮询，不依赖 PySide，避免双 Qt 库 ABI 冲突崩溃

## [1.2.0] - 2026-07-21

### 新增
- 支持 Houdini 和 Blender 的 `dcc setup` / `dcc unsetup` 注入
- DCC Setup Manager WebView 面板：可视化 DCC 工具管理，支持独立 Setup/Unsetup 和批量操作
- 状态指示灯：绿色 ● 运行中 / 灰色 ○ 未检测到
- Dashboard 标题栏和命令面板入口 (`Ctrl+Shift+P` → `DCC Setup Manager`)

### 变更
- `dcc setup` 不指定 DCC 类型时自动为所有已支持的 DCC 执行注入
- `dcc setup --pip-index-url` 支持使用国内镜像源加速 debugpy 安装
- 清理命令 `dcc cleanup` 的完整文档
- Dashboard 移除 Open Dashboard 按钮和刷新节点
- Dashboard 的 setup 命令输出实时写入 `DCC Python ToolKit Log` 频道
- `runSetupCommand` 移除超时限制，避免网络慢时误报超时

## [1.1.0] - 2026-07-21

### 新增
- `dcc setup` 命令自动为每个 DCC 版本安装 debugpy，无需在 attach 时按需安装
- `debugpy.listen()` 复用机制：断开重连时复用已有监听，不再报端口占用
- 各 DCCSetup 子类实现 `get_python_path()` 方法，用于定位 Python 解释器

### 变更
- 移除 VS Code 扩展中的 `pipIndexUrl` 配置项，镜像源改为 `dcc setup --pip-index-url` 传入
- `attach.ts` 简化流程，移除 debugpy 安装检查，直接启动调试
- 未安装 debugpy 时提示用户运行 `dcc setup <dcc>`
- `debug.port` 配置项新增说明：端口绑定后不可动态更改，需重启 DCC

## [1.0.4] - 2026-07-21

### 变更
- 输出频道重命名：`DCC Python Log` → `DCC Python ToolKit Log`

## [1.0.3] - 2026-07-21

### 新增
- debugpy 端口被占用时弹出提示框，引导用户修改配置

### 变更
- 扩展重命名为 `dcc-python-toolkit`，显示名 `DCC Python ToolKit`
- `__init__.py` 版本号改为从 `pyproject.toml` 动态读取

## [1.0.0] - 2026-07-17

### 架构变更
- **CLI 与 VS Code 扩展完全分离**：AI 发送代码直接依赖 `dcc` CLI，无需安装 VS Code 扩展
- VS Code 扩展变为可选组件，仅用于人工调试场景（断点调试、交互式开发）
- 扩展通过 `python -m dcc_bridge` 方式调用 CLI，支持虚拟环境安装场景

### 新增
- 独立的 `dcc` CLI 工具，支持 `run`、`setup`、`unsetup`、`status`、`ping`、`cleanup` 命令
- DCC 桥接 TCP 服务端，支持从 7002 开始自动递增端口
- 多 DCC 支持：Maya（2020+）、3ds Max（2021+）、Substance Painter、Substance Designer
- 代码执行、模块热重载、debugpy 集成
- 英中双语 CLI 帮助文本和配置项描述

### 初始版本
- 首次发布，版本号从 2026.1.0 改为 1.0.0