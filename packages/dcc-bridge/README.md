# dcc-bridge

DCC Python 桥接核心包，提供 DCC 端 TCP 服务端、通用 TCP 客户端、`dcc` CLI、DCC 适配器、代码执行、模块热重载和调试集成。

## 安装

```bash
pip install dcc-bridge
```

安装后自动获得 `dcc` 全局命令。

开发模式：

```bash
uv tool install -e packages/dcc-bridge
```

## 快速开始

```bash
# 1. 注入自启动脚本并安装 debugpy（以 3ds Max 为例）
dcc setup 3dsmax

# 若网络较慢，可使用国内镜像源加速
dcc setup 3dsmax --pip-index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 打开 DCC，服务自动启动（debugpy 已就绪）

# 3. 验证连接
dcc status
dcc ping

# 4. 执行代码
dcc run code "print('hello from DCC')"
```

## `dcc` 命令详细用法

### 命令总览

```
dcc [--version] {run, setup, unsetup, status, ping} ...
```

| 子命令 | 功能 |
|---|---|
| `run` | 在 DCC 中执行 Python 代码或文件 |
| `setup` | 注入 DCC 自启动脚本并安装 debugpy（配置一次，永久生效） |
| `unsetup` | 移除 DCC 自启动脚本 |
| `status` | 查看桥接状态（实例列表 + 可选 ping） |
| `ping` | 测试 DCC 桥接服务是否可达 |
| `cleanup` | 清理所有 dcc-bridge 数据和自启动脚本（卸载前使用） |

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
| `--dcc-type` | str | 自动发现 | 指定目标 DCC 类型（`maya`、`3dsmax`、`substance_painter`、`substance_designer` 等） |
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

在 DCC 的启动目录中写入 `dcc_bridge_startup.py`，DCC 打开后自动启动桥接服务。同时自动为每个 DCC 版本安装 debugpy 调试模块，安装失败仅输出警告，不影响脚本注入。

不指定 `dcc_type` 时，自动为 Maya、3ds Max、Substance Painter、Substance Designer 全部执行注入。

#### 语法

```
dcc setup [<dcc_type>] [--version <版本号>] [--pip-index-url <镜像源>]
```

#### 参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `dcc_type` | 否 | DCC 类型：`maya`、`3dsmax`、`substance_painter`、`substance_designer`。不指定时注入所有已支持的 DCC |
| `--version` | 否 | 指定版本号。不指定时自动从注册表发现并注入所有已安装版本 |
| `--pip-index-url` | 否 | pip 镜像源 URL，用于加速 debugpy 安装（如 `https://pypi.tuna.tsinghua.edu.cn/simple`） |

#### 示例

```bash
# 注入所有已支持的 DCC（Maya + 3ds Max + SP + SD），自动发现版本并安装 debugpy
dcc setup

# 使用国内镜像源加速所有 DCC 的 debugpy 安装
dcc setup --pip-index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 注入 3ds Max（自动发现所有已安装版本，并安装 debugpy）
dcc setup 3dsmax

# 使用国内镜像源加速
dcc setup 3dsmax --pip-index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 注入指定版本的 Maya
dcc setup maya --version 2024

# 注入所有已安装的 Maya
dcc setup maya

# 注入 Substance Painter / Substance Designer
dcc setup substance_painter
dcc setup substance_designer
```

#### 注入位置

| DCC | 注入路径 | 额外操作 |
|---|---|---|
| Maya | `~/maya/<version>/scripts/dcc_bridge_startup.py` | 在 `userSetup.py` 中追加 `import dcc_bridge_startup` |
| 3ds Max | `~/AppData/Local/Autodesk/3dsMax/<year> - 64bit/ENU/scripts/startup/dcc_bridge_startup.py` | 无（Max 自动加载 startup 目录） |
| Substance Painter | 应用脚本目录 | 自动启动入口注入 |
| Substance Designer | 应用脚本目录 | 自动启动入口注入 |

#### 版本发现机制

通过读取 Windows 注册表自动发现已安装版本：

| DCC | 注册表路径 | 版本来源 |
|---|---|---|
| Maya | `HKLM\SOFTWARE\Autodesk\Maya\<version>` | 子键名（如 `2022`、`2024`） |
| 3ds Max | `HKLM\SOFTWARE\Autodesk\3dsMax\<internal_version>` | `Installdir` 值中的年份（如 `2019`、`2024`） |
| Substance Painter | 注册表/安装路径 | 自动发现 |
| Substance Designer | 注册表/安装路径 | 自动发现 |

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

# 移除 Substance Painter / Substance Designer 自启动脚本
dcc unsetup substance_painter
dcc unsetup substance_designer
```

---

### `dcc status` — 查看桥接状态

扫描 `~/.dcc-bridge/instances/` 目录，列出所有正在运行的 DCC 桥接服务，并可对指定实例执行 ping 测试。

#### 语法

```
dcc status [--port <端口>] [--dcc-type <类型>] [--version <版本号>] [--plain]
```

#### 示例

```bash
# 查看所有实例状态
dcc status

# 对指定端口执行 ping
dcc status --port 7002

# 对指定 DCC 类型执行 ping
dcc status --dcc-type maya

# 对指定版本执行 ping
dcc status --dcc-type maya --version 2024

# 纯文本输出
dcc status --plain
```

#### 输出格式

**JSON 模式（默认）：**

```json
{
  "instances": [
    {
      "pid": 12345,
      "dcc_type": "3dsmax",
      "dcc_version": "2024",
      "host": "127.0.0.1",
      "port": 7002,
      "started_at": "2026-07-15T10:30:00",
      "python_path": "C:\\Program Files\\Autodesk\\3ds Max 2024\\python\\python.exe"
    }
  ],
  "count": 1,
  "ping": {
    "dcc_type": "3dsmax",
    "python_path": "C:\\Program Files\\Autodesk\\3ds Max 2024\\python\\python.exe"
  }
}
```

未指定 `ping` 目标时，`ping` 字段不出现；ping 失败时返回 `ping_error`。

**纯文本模式（`--plain`）：**

```
Running DCC instances: 1
  3dsmax:7002 v2024
Ping: OK - {'dcc_type': '3dsmax', 'python_path': '...'}
```

---

### `dcc ping` — 测试连接

向 DCC 桥接服务发送 ping 请求，验证服务是否可达并获取基础信息。

#### 语法

```
dcc ping [--port <端口>] [--dcc-type <类型>] [--version <版本号>] [--plain]
```

#### 示例

```bash
# 自动发现并 ping
dcc ping

# 指定端口
dcc ping --port 7002

# 指定 DCC 类型
dcc ping --dcc-type maya

# 指定版本
dcc ping --dcc-type maya --version 2024

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

### `dcc cleanup` — 清理数据与脚本

卸载 dcc-bridge 前使用，执行两项清理操作：

1. 删除 `~/.dcc-bridge` 用户数据目录（包含所有发现文件）
2. 对所有已安装的 DCC 执行 unsetup，移除自启动脚本

#### 语法

```
dcc cleanup [--yes]
```

#### 参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `--yes`, `-y` | 否 | 跳过确认提示，直接执行清理 |

#### 示例

```bash
# 交互式清理（会显示确认提示）
dcc cleanup

# 跳过确认，直接清理
dcc cleanup --yes
```

---

## 目标解析机制

当不指定 `--port` 时，CLI 通过 `~/.dcc-bridge/instances/` 下的发现文件自动解析目标：

1. 若指定 `--dcc-type`，只匹配该类型的实例
2. 若指定 `--version`，进一步按版本筛选
3. 若只找到一个实例，自动连接
4. 若找到多个实例，报错并提示用 `--port` 或 `--dcc-type` 指定
5. 若未找到任何实例，报错并提示先启动 DCC

---

## 服务发现与端口分配

DCC 端 TCP 服务启动后会自动在 `~/.dcc-bridge/instances/{dcc_type}-{pid}.json` 写入发现文件，CLI 与 VS Code 插件通过读取这些文件零配置发现运行中的实例。

- 发现文件命名：`{dcc_type}-{pid}.json`
- 默认起始端口：`7002`，多实例时自动递增，避免端口冲突
- 惰性清理：`list_instances` 会检查 PID 是否存活，已退出的 DCC 进程对应文件会被自动删除

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
| Substance Painter | 支持 | 注册表/安装路径 | 自动启动入口注入 |
| Substance Designer | 支持 | 注册表/安装路径 | 自动启动入口注入 |

---

## 调试集成说明

`dcc_bridge.debug.start_debugpy_server` 在启动 debugpy 服务前会调用当前 DCC 适配器的 `configure_debugpy(python_path)` 方法，完成针对各 DCC 的解释器配置。

`SubstanceDesignerAdapter` 在条用 `debugpy.configure` 之前增加了 `os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"`，以避免debugpy无法启动侦听模式，因为 SD 内置 Python 是打包冻结版（frozen modules），debugpy 默认校验源码文件一致性，冻结内置库会触发断点失效警告，
有两种解决思路：关闭冻结模块 / 跳过文件校验。
这里选择在脚本最顶部添加环境变量，提前关闭校验，从而屏蔽警告。

---

## 许可证

本项目采用 [PolyForm Noncommercial License 1.0.0](../../LICENSE) 授权，仅供非商业用途使用。详见根目录 `LICENSE` 文件。
