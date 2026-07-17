# DCC Python ToolKit (Visual Studio Code)

通用 Python DCC 开发工具，支持 Maya、3ds Max、Substance Painter、Substance Designer 等具备 Python 脚本能力的 DCC 软件。

## 依赖

本插件要求安装 `dcc-bridge` Python 包：

```bash
pip install dcc-bridge
```

插件首次激活时会检测该包是否已安装，并提示安装命令。

## 功能

### 执行代码

在 VS Code 中按 `Ctrl + Enter` 将选中代码发送到 DCC 执行；未选中时执行整个文件。

### 附加调试器

`DCC Python ToolKit: Attach Debugger` 在 DCC 中启动 debugpy 服务，并将 VS Code 附加到该服务。

### 重载模块

`DCC Python ToolKit: Reload Modules` 无需重启 DCC 即可重载工作区中的 Python 模块。

### Dashboard

`DCC Python ToolKit: Open Dashboard` 打开资源管理器面板，列出所有运行中的 DCC 实例：

- **Select Instance**：选择当前要连接的 DCC 实例，后续 `Execute`、`Reload Modules`、`Attach Debugger` 等命令均针对该实例。
- **4 个 Setup 按钮**：一键注入 Maya / 3ds Max / Substance Painter / Substance Designer 的自启动脚本。
- 选中实例后可通过右键菜单移除对应 DCC 的自动启动。

## 配置

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `dcc-python-toolkit.pythonPath` | 指定 Python 解释器路径，用于检测 `dcc-bridge` 包；留空则自动检测 | `""` |
| `dcc-python-toolkit.server.host` | DCC 服务地址 | `127.0.0.1` |
| `dcc-python-toolkit.server.port` | DCC 服务端口 | `7002` |
| `dcc-python-toolkit.execute.entryPoint` | 入口点脚本路径 | `""` |
| `dcc-python-toolkit.debug.port` | debugpy 端口 | `7012` |
| `dcc-python-toolkit.debug.pipIndexUrl` | 可选 pip 源 | `""` |

## 开发

```bash
cd packages/vscode-extension
npm install
npm run compile
```

## 许可证

本项目采用 [PolyForm Noncommercial License 1.0.0](../../LICENSE) 授权，仅供非商业用途使用。详见根目录 `LICENSE` 文件。
