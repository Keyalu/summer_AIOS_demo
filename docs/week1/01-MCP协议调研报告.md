# MCP 协议调研报告

## 一、背景

### 1.1 项目背景

本课程项目目标是构建一套基于 UFO² 框架的 **Linux Agentic OS**（智能操作系统代理）。系统包含五个模块，分组四负责其中的"工具注册表与 OS 技能"模块，承担将 Linux 操作系统底层能力（文件系统、进程管理、Shell 命令等）以标准化方式暴露给上层 AI Agent 的核心任务。

### 1.2 为什么需要协议

在一个异构的 AI Agent 系统中，各组模块的交互需要一个统一的通信协议。如果各组自行设计接口格式，集成时将面临大量适配工作。为此，分组四的接口设计参考了 **MCP（Model Context Protocol）** 协议的设计思想。

---

## 二、核心概念

### 2.1 三大设计目标

| 目标 | 说明 | 在项目中的体现 |
|------|------|----------------|
| 标准化 | 所有工具的输入输出格式统一 | 所有工具返回统一的 `{success, result}` 结构 |
| 可发现 | Agent 可以动态查询有哪些工具可用 | `list_tools()` 返回所有工具的 schema |
| 安全性 | 对危险操作进行权限控制 | `PermissionLevel` 三级权限模型 |

### 2.2 核心交互模式

简化为四个关键操作：

| 操作 | 协议方法 | 项目实现 |
|------|----------|---------|
| 列出可用工具 | `tools/list` | `registry.list_tools()` |
| 调用工具 | `tools/call` | `registry.call("tool_name", params)` |
| 注册新工具 | 无标准方法 | `registry.register("name", func, schema)` |
| 查询工具详情 | 无标准方法 | `registry.get_schema("name")` |

### 2.3 传输层：JSON-RPC 2.0

采用 JSON-RPC 2.0 作为底层格式，原因：
- **语言无关**：任何语言都可以解析 JSON
- **请求/响应对称**：每个请求都有明确且有 ID 的响应
- **错误标准化**：失败时返回结构化的 error 对象

**请求格式：**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "copy_file",
    "arguments": {
      "src": "/tmp/a.txt",
      "dest": "/tmp/b.txt"
    }
  },
  "id": 1
}
```

**成功响应：**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "已复制: /tmp/a.txt → /tmp/b.txt"
      }
    ]
  },
  "id": 1
}
```

**错误响应：**

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "工具未注册: unknown_tool"
  },
  "id": 1
}
```

---

## 三、工具 Schema 设计

### 3.1 什么是工具 Schema

Schema 是每个工具的"使用说明书"——它描述了一个工具叫什么名字、做什么用、需要哪些参数、返回什么。在 MCP 协议中，工具 Schema 是 LLM 理解并选择正确工具的关键依据。

### 3.2 Schema 结构

```
ToolSchema
├── name: str                  # 工具唯一标识，如 "copy_file"
├── description: str           # 人类可读的功能描述
├── permission: str            # 权限级别：public | user | admin
└── parameters: list[ToolParam]
    ├── name: str              # 参数名，如 "src"
    ├── type: str              # 参数类型：string | number | boolean | object | array
    ├── description: str       # 参数说明
    ├── required: bool         # 是否必填
    └── default: any           # 默认值
```

### 3.3 设计原则

| 原则 | 说明 | 示例 |
|------|------|------|
| 自描述 | 每个工具附带完整 schema | `list_tools()` 返回所有工具的 name + description + parameters |
| 内聚性 | 一个工具只做一件事 | `copy_file` 只管复制，不管其他 |
| 正交性 | 工具之间可以组合 | `create_folder` + `write_file` = 创建带内容的文件 |
| 幂等性 | 多次调用 produce 相同效果 | `create_folder` 使用 `exist_ok=True` |

---

## 四、UFO² 框架中的位置

### 4.1 UFO² 原始架构

UFO²（Enhanced UI-Focused Agent）是由微软研究院提出的 Windows 操作系统 AI Agent 框架，核心架构包括：

| 组件 | 职责 |
|------|------|
| HostAgent | 理解用户自然语言输入，解析意图 |
| AppAgent | 执行具体应用操作（GUI 点击、API 调用） |
| Control Detection | 检测 UI 元素（视觉检测 + UIA 检测） |
| Knowledge Substrate | 基于 RAG 的经验知识库 |

### 4.2 Linux 版本的角色映射

本项目将 UFO² 的思想移植到 Linux 平台，五个分组对应 UFO² 中各组件：

| 分组 | 职责 | UFO² 对应组件 | 输入 | 输出 |
|------|------|--------------|------|------|
| 组1 | AI Shell + HostAgent | HostAgent | 用户自然语言 | intent_json |
| 组2 | TaskPlanner + ControlDetector | Control Detection | intent_json | plan_json |
| 组3 | AppAgent + Automator | AppAgent | plan_json | result_json |
| **组4** | **ToolRegistry + SkillLibrary** | **Tools** | **组3调用** | **tool_result_json** |
| 组5 | Coordinator + Security + RAG | Coordinator + Knowledge | 各组输出 | check_json |

### 4.3 分组四的角色抽象

分组四在整个系统中扮演的角色，高度类似于操作系统中的"系统调用层"：

| 对比维度 | 经典 OS 系统调用 | 分组四的 ToolRegistry |
|----------|-----------------|----------------------|
| 调用入口 | `syscall()` | `registry.call()` |
| 功能注册 | 内核编译时静态注册 | `registry.register()` 动态注册 |
| 参数传递 | CPU 寄存器 | `params dict` |
| 返回值 | 返回值 + errno | `ToolResult {success, result, error}` |
| 安全检查 | 内核态/用户态隔离 | `PermissionLevel` 权限模型 |
| 可扩展性 | 编译时固定 | 运行时动态注册新工具 |

---

## 五、接口设计

### 5.1 统一返回格式

任务书明确要求分组四的输出格式为：

```json
{"success": true, "result": "..."}
```

对应 `ToolResult` 数据结构：

```python
@dataclass
class ToolResult:
    success: bool              # 调用是否成功
    result: Any = None         # 成功时的返回值
    error: str | None = None   # 失败时的错误信息
```

### 5.2 工具注册表接口

```python
class IToolRegistry(ABC):
    register(name, func, schema)   # 注册工具
    unregister(name)               # 注销工具
    call(name, params, level)      # 调用工具（核心方法）
    list_tools()                   # 列出所有工具
    has(name)                      # 检查工具是否存在
```

### 5.3 OS 技能库接口

```python
class ISkillLibrary(ABC):
    register_skill(name, func, schema)   # 注册技能
    call_skill(name, params)             # 调用技能（核心方法）
    list_skills()                        # 列出所有技能
```

### 5.4 调用统计接口

```python
class IToolStats(ABC):
    record(record)       # 记录单次调用
    report()             # 返回统计报告
    total_calls()        # 总调用次数
```

### 5.5 权限模型

| 级别 | 值 | 可调用 | 示例工具 |
|------|-----|--------|---------|
| public | 0 | 只读工具 | `list_directory`, `read_file`, `get_system_info` |
| user | 1 | 普通操作 | `copy_file`, `move_file`, `delete_file` |
| admin | 2 | 高危操作 | `run_command` |

权限验证规则：`user_level.rank() >= required_level.rank()`

---

## 六、接口数据流

### 6.1 跨组协作

五组接口数据流如下：

```
用户输入 "整理下载文件夹"
  → 组1 HostAgent: 解析为 intent_json = {"intent": "整理", "target": "Downloads"}
  → 组2 TaskPlanner: 规划为 plan_json = {"steps": [{"action": "use_skill", "skill": "organize_downloads"}]}
  → 组3 AppAgent: 执行计划，在需要 OS 操作时调用组4
  → ★ 组4 SkillLibrary: 返回 tool_result_json = {"success": true, "result": {...}}
  → 组5 Coordinator: 审计并存储
```

### 6.2 Mock 模式的数据流

在开发期间，各组使用 Mock 实现进行独立开发：

```
组3 AppAgent
  │
  ▼
MockToolRegistry.call("copy_file", ...)
  │ 不执行真实文件操作
  ▼
ToolResult.ok("[Mock] copy_file 执行成功（模拟）— 参数: {...}")
  │
  ▼
组3 拿到模拟结果，继续开发下一步
```

Mock 最大的价值在于：**组3 不需要等组4 的真实实现完成**。只要接口不变，后续将 `MockToolRegistry` 换成 `ToolRegistry` 即可无缝切换。

---

## 七、涉技术要点

| 知识域 | 具体内容 | 在项目中的应用 |
|--------|---------|---------------|
| MCP 协议 | tools/list, tools/call, JSON-RPC 2.0 | ToolRegistry 接口风格参考 MCP |
| Python dataclass | `@dataclass` 自动生成构造器和字段 | ToolSchema, ToolResult, CallRecord |
| 抽象基类 | `ABC` + `@abstractmethod` | IToolRegistry, ISkillLibrary, IToolStats |
| 枚举类型 | `str, Enum` | ToolParamType, PermissionLevel |
| 类型注解 | `from __future__ import annotations` | 全项目使用类型注解 |
| Linux 文件系统 | inode, 目录结构, 权限模型 | copy_file, move_file 等工具 |
| 子进程 | `subprocess.run()` + 安全过滤 | run_command 工具 |
| pytest | fixture, parametrize, 断言 | 31 个单元测试 |

---

## 八、参考资料

| 资源 | 链接 |
|------|------|
| MCP 协议规范 | https://modelcontextprotocol.io/ |
| JSON-RPC 2.0 规范 | https://www.jsonrpc.org/specification |
| UFO: UI-Focused Agent | https://arxiv.org/abs/2402.07939 |
| UFO²: Enhanced UFO | https://arxiv.org/abs/2511.11332 |
| Python dataclass 文档 | https://docs.python.org/3/library/dataclasses.html |
| Python ABC 文档 | https://docs.python.org/3/library/abc.html |
| GNOME AT-SPI | https://accessibility.linuxfoundation.org/ |
