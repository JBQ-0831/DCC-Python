# Change Log

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