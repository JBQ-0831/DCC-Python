# DCC Python (Visual Studio Code)

通用 Python DCC 开发工具，支持 Maya、3ds Max、Substance Painter 等具备 Python 脚本能力的 DCC 软件。

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

`DCC Python: Attach Debugger` 在 DCC 中启动 debugpy 服务，并将 VS Code 附加到该服务。

### 重载模块

`DCC Python: Reload Modules` 无需重启 DCC 即可重载工作区中的 Python 模块。

### Dashboard

`DCC Python: Open Dashboard` 打开资源管理器面板，列出所有运行中的 DCC 实例，可一键选择目标、配置 Maya / 3ds Max 自启动脚本。

## 配置

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `dcc-python.server.host` | DCC 服务地址 | `127.0.0.1` |
| `dcc-python.server.port` | DCC 服务端口 | `7002` |
| `dcc-python.execute.entryPoint` | 入口点脚本路径 | `""` |
| `dcc-python.debug.port` | debugpy 端口 | `7012` |
| `dcc-python.debug.pipIndexUrl` | 可选 pip 源 | `""` |

## 开发

```bash
cd packages/vscode-extension
npm install
npm run compile
```
