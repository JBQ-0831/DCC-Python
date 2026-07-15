# dcc-bridge

DCC Python 桥接核心包，提供 DCC 端 TCP 服务端、通用 TCP 客户端、`dcc` CLI、DCC 适配器、代码执行、模块热重载和调试集成。

## 安装

```bash
pip install dcc-bridge
```

安装后自动获得 `dcc` 全局命令。

## 快速开始

```bash
# 1. 注入自启动脚本（以 3ds Max 为例）
dcc setup 3dsmax

# 2. 打开 DCC，服务自动启动

# 3. 验证连接
dcc list
dcc ping

# 4. 执行代码
dcc run code "print('hello from DCC')"
```

## `dcc` 命令详细用法

### 命令总览

```
dcc [--version] {run, setup, unsetup, list, status, ping} ...
```

| 子命令 | 功能 |
|---|---|
| `run` | 在 DCC 中执行 Python 代码或文件 |
| `setup` | 注入 DCC 自启动脚本（配置一次，永久生效） |
| `unsetup` | 移除 DCC 自启动脚本 |
| `list` | 列出当前运行中的 DCC 实例 |
| `status` | 查看桥接状态（实例列表 + 可选 ping） |
| `ping` | 测试 DCC 桥接服务是否可达 |

---

### `dcc run` — 执行代码

在 DCC 中执行 Python 代码，支持三种输入方式。

#### 语法

```
dcc run {file, code, stdin} [target] [选项]
```

#### 子命令

| 子命令 | 说明 | `target` 参数 |
|---|---|---|
| `file` | 执行本地 Python 文件 | 文件路径（必填） |
| `code` | 执行代码字符串 | Python 代码字符串（必填） |
| `stdin` | 从标准输入读取代码并执行 | 无需提供 |

#### 选项

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `--port` | int | 自动发现 | 指定目标 DCC 服务端口 |
| `--dcc-type` | str | 自动发现 | 指定目标 DCC 类型（`maya`、`3dsmax` 等） |
| `-r`, `--reload` | flag | 否 | 执行前先重载模块（`file` 重载文件所在目录，`code`/`stdin` 重载当前工作目录） |
| `--origin` | str | 自动生成 | 自定义 `exec_origin`，用于标识代码来源 |
| `--plain` | flag | 否 | 输出纯文本而非 JSON |
| `--json` | flag | 是 | 输出 JSON 格式（默认行为） |
| `--timeout` | float | 30.0 | 连接超时（秒） |

#### 示例

```bash
# 执行文件
dcc run file /path/to/script.py

# 执行代码字符串
dcc run code "print('hello')"

# 从管道执行
echo "print('hello')" | dcc run stdin

# 执行前先重载模块
dcc run file ./my_tool.py --reload

# 指定端口和超时
dcc run code "import pymxs; print(pymxs.rt.maxOps())" --port 7002 --timeout 10

# 指定 DCC 类型（多实例同时运行时）
dcc run code "print('maya')" --dcc-type maya

# 纯文本输出（只打印 stdout 内容）
dcc run code "print(1 + 2)" --plain
```

#### 输出格式

**JSON 模式（默认）：**

```json
{
  "success": true,
  "output": ["hello from DCC"],
  "error": null,
  "traceback": null
}
```

**纯文本模式（`--plain`）：**

```
hello from DCC
```

执行出错时：

```json
{
  "success": false,
  "output": [],
  "error": "NameError: name 'x' is not defined",
  "traceback": "Traceback (most recent call last):\n  ..."
}
```

#### 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 执行成功 |
| 1 | 未知错误 |
| 2 | 执行失败（DCC 端返回错误）或参数错误 |
| 3 | 文件未找到（仅 `file` 子命令） |

---

### `dcc setup` — 注入自启动脚本

在 DCC 的启动目录中写入 `dcc_bridge_startup.py`，DCC 打开后自动启动桥接服务。

#### 语法

```
dcc setup <dcc_type> [--version <版本号>]
```

#### 参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `dcc_type` | 是 | DCC 类型：`maya`、`3dsmax` |
| `--version` | 否 | 指定版本号。不指定时自动从注册表发现并注入所有已安装版本 |

#### 示例

```bash
# 注入 3ds Max（自动发现所有已安装版本）
dcc setup 3dsmax

# 注入指定版本的 Maya
dcc setup maya --version 2024

# 注入所有已安装的 Maya
dcc setup maya
```

#### 注入位置

| DCC | 注入路径 | 额外操作 |
|---|---|---|
| Maya | `~/maya/<version>/scripts/dcc_bridge_startup.py` | 在 `userSetup.py` 中追加 `import dcc_bridge_startup` |
| 3ds Max | `~/AppData/Local/Autodesk/3dsMax/<year> - 64bit/ENU/scripts/startup/dcc_bridge_startup.py` | 无（Max 自动加载 startup 目录） |

#### 版本发现机制

通过读取 Windows 注册表自动发现已安装版本：

| DCC | 注册表路径 | 版本来源 |
|---|---|---|
| Maya | `HKLM\SOFTWARE\Autodesk\Maya\<version>` | 子键名（如 `2022`、`2024`） |
| 3ds Max | `HKLM\SOFTWARE\Autodesk\3dsMax\<internal_version>` | `Installdir` 值中的年份（如 `2019`、`2024`） |

---

### `dcc unsetup` — 移除自启动脚本

移除 `dcc setup` 注入的脚本，恢复原始状态。

#### 语法

```
dcc unsetup <dcc_type> [--version <版本号>]
```

#### 示例

```bash
# 移除 3ds Max 自启动脚本
dcc unsetup 3dsmax

# 移除指定版本的 Maya
dcc unsetup maya --version 2024
```

---

### `dcc list` — 列出运行中的实例

扫描 `~/.dcc-bridge/instances/` 目录，列出所有正在运行的 DCC 桥接服务。

#### 语法

```
dcc list [--plain]
```

#### 示例

```bash
# JSON 输出（默认）
dcc list
```

```json
[
  {
    "dcc_type": "3dsmax",
    "port": 7002,
    "dcc_version": "2024",
    "pid": 12345,
    "host": "127.0.0.1",
    "started_at": "2026-07-15T10:30:00"
  }
]
```

```bash
# 纯文本输出
dcc list --plain
```

```
3dsmax:7002 v2024 pid=12345 started=2026-07-15T10:30:00
```

---

### `dcc status` — 查看桥接状态

列出运行中的实例，并可选对指定实例执行 ping 测试。

#### 语法

```
dcc status [--port <端口>] [--dcc-type <类型>] [--plain]
```

#### 示例

```bash
# 查看所有实例状态
dcc status

# 对指定端口执行 ping
dcc status --port 7002

# 对指定 DCC 类型执行 ping
dcc status --dcc-type maya
```

#### 输出格式

```json
{
  "instances": [...],
  "count": 1,
  "ping": {
    "dcc_type": "3dsmax",
    "python_path": "C:\\Program Files\\Autodesk\\3ds Max 2024\\python\\python.exe"
  }
}
```

---

### `dcc ping` — 测试连接

向 DCC 桥接服务发送 ping 请求，验证服务是否可达并获取基础信息。

#### 语法

```
dcc ping [--port <端口>] [--dcc-type <类型>] [--plain]
```

#### 示例

```bash
# 自动发现并 ping
dcc ping

# 指定端口
dcc ping --port 7002

# 指定 DCC 类型
dcc ping --dcc-type maya

# 纯文本输出
dcc ping --plain
```

#### 输出格式

**JSON（默认）：**

```json
{
  "success": true,
  "dcc_type": "3dsmax",
  "python_path": "C:\\Program Files\\Autodesk\\3ds Max 2024\\python\\python.exe"
}
```

**纯文本（`--plain`）：**

```
DCC bridge server is reachable.
DCC type: 3dsmax
Python path: C:\Program Files\Autodesk\3ds Max 2024\python\python.exe
```

---

## 目标解析机制

当不指定 `--port` 时，CLI 通过 `~/.dcc-bridge/instances/` 下的发现文件自动解析目标：

1. 若指定 `--dcc-type`，只匹配该类型的实例
2. 若只找到一个实例，自动连接
3. 若找到多个实例，报错并提示用 `--port` 或 `--dcc-type` 指定
4. 若未找到任何实例，报错并提示先启动 DCC

---

## 在 DCC 中手动启动服务

正常情况下 `dcc setup` 后 DCC 打开即自动启动服务。如需手动启动：

```python
from dcc_bridge.start import start_server
start_server(port=7002)
```

服务启动后会自动在 `~/.dcc-bridge/instances/` 写入发现文件，供 CLI 与 VS Code 插件识别。

---

## 作为 Python 包使用

```python
from dcc_bridge import DCCClient

# 直连指定端口
with DCCClient(port=7002) as client:
    result = client.execute_code("print('hello from DCC')")
    print(result.to_dict())

# 自动发现实例
from dcc_bridge.client import resolve_client
with resolve_client(dcc_type="maya") as client:
    client.execute_file("/path/to/script.py")
```

---

## 支持的 DCC

| DCC | 状态 | 版本发现 | 自启动注入 |
|---|---|---|---|
| Maya | 完整支持 | 注册表 | `userSetup.py` + `dcc_bridge_startup.py` |
| 3ds Max | 完整支持 | 注册表 | `scripts/startup/dcc_bridge_startup.py` |
| Substance Painter | 保留接口 | 硬编码路径 | 待实现 |
