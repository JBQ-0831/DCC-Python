# DCC Python / DCC Bridge

Monorepo for DCC Python development tools.

本仓库包含两个包：

- [`packages/dcc-bridge`](packages/dcc-bridge) — Python 核心包，提供 DCC 端 TCP 服务、通用 TCP 客户端、`dcc` CLI、DCC 适配器、代码执行、模块热重载与调试集成。
- [`packages/vscode-extension`](packages/vscode-extension) — VS Code 插件，提供编辑器命令、状态面板和调试适配器入口。

## 快速开始

### AI / CLI 使用

```bash
pip install dcc-bridge

# 配置 Maya / 3ds Max 自启动
dcc setup maya --version 2024
dcc setup 3dsmax

# 打开 DCC 后，直接执行代码或文件
dcc list
dcc run code "print('hello')"
dcc run file /path/to/script.py
```

### VS Code 插件使用

1. 安装 `dcc-bridge` Python 包（见上）。
2. 在 VS Code 中加载 `packages/vscode-extension`。
3. 使用 `DCC Python: Open Dashboard` 查看运行中的 DCC 实例并选择目标。
4. 按 `Ctrl + Enter` 执行代码，`Ctrl + Shift + P` 搜索 `DCC Python` 查看更多命令。

## 已测试的 DCC

- Maya
- 3ds Max
- Substance Painter（保留接口）

## 架构

```
vscode-maya-python/
├── packages/
│   ├── dcc-bridge/          # Python 核心包（可独立发布到 PyPI）
│   └── vscode-extension/    # VS Code 插件
├── media/                   # 演示素材
└── test/                    # 遗留的 DCC 测试脚本
```

核心设计：

- `dcc-bridge` 不依赖 VS Code，DCC 端服务与 CLI 共用同一套协议与适配器。
- VS Code 插件通过 TCP 直连 DCC，不再作为 CLI 中转。
- DCC 服务启动后自动写入发现文件，CLI 与插件可零配置发现运行中的实例。
