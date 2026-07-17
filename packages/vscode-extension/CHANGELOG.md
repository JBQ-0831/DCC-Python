# Change Log

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