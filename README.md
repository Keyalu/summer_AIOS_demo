# Linux Agentic OS — 分组四：工具注册与操作系统技能

> **模块名称**: Tools + OS Skills (工具注册表 + 操作系统技能库)
>
> **基于框架**: UFO (User-Friendly Orchestrator) 智能操作系统
>
> **分组**: 第四组

---

## 项目简介

本模块是 Linux Agentic OS 的**工具层**，负责两件核心事情：

1. **ToolRegistry（工具注册表）** — 管理所有可用工具的注册、调用、权限控制和安全检查
2. **SkillLibrary（技能库）** — 将多个基础工具编排组合，形成高级的"一键操作"能力

### 通俗比喻

| 组件 | 比喻 | 具体作用 |
|------|------|---------|
| **ToolRegistry** | 瑞士军刀 | 每个工具（刀片/剪刀/开瓶器）独立注册、按需取用 |
| **SkillLibrary** | 一键宏/快捷指令 | "整理桌面" = 建文件夹 + 分类移动文件（多步变一步） |
| **MCP Connector** | USB接口 | 接入外部AI服务（搜索/天气/翻译），统一协议格式 |
| **Stats** | 记账本 | 记录每次工具调用的参数、结果、耗时、成功率 |
| **权限系统** | 门禁卡 | PUBLIC只能看 / USER能操作文件 / ADMIN能执行命令 |

---

## 快速开始（3步运行）

```bash
cd linux-agentic-os-group4

# 方式1：自动演示（推荐先试这个）
python main.py

# 方式2：快速验证（无需 pytest）
python quick_check.py

# 方式3：完整测试套件
python -m pytest tests/test_all.py -v
```

详细运行指南请查看 [RUN_GUIDE.md](./RUN_GUIDE.md)。

### 可视化操作台（GUI）

```bash
python gui/server.py        # 打开 http://127.0.0.1:8765
```

四个页签：**工具台**（schema 自动生成参数表单，选权限发起真实调用）、**技能台**、
**统计看板**（实时成功/失败/耗时）、**MCP·JSON-RPC**（报文级调试）。
调用会经过与生产一致的权限闸门/黑名单/保护路径；服务只绑定 127.0.0.1。

### 可视化产物

- `assets/charts/` — 5 张图（性能对比、流水线、权限、安全、命令流转），SVG+PNG 双格式
- `assets/dashboard.html` — 审计看板（单文件离线可用，组5 可直接消费）
- 再生成脚本：`tools/gen_charts.py`、`tools/gen_dashboard.py`（纯标准库）

---

## 项目结构

```
linux-agentic-os-group4/
│
├── README.md                    # 本文件 — 项目总说明
├── 快速开始.md                   # 5分钟上手指南
├── RUN_GUIDE.md                 # 详细运行手册（Windows + WSL）
├── main.py                      # 自动演示入口（8步演示全流程）
├── quick_check.py               # 无需pytest的快速验证脚本
├── pytest.ini                   # 测试配置
│
├── src/                         # ★ 核心源码
│   ├── __init__.py              # 包入口，导出所有公开类
│   ├── interfaces.py            # 抽象接口 + 数据类型定义
│   ├── tool_registry.py         # 工具注册表（真实实现）
│   ├── default_tools.py         # 8个默认OS工具实现
│   ├── skill_library.py         # OS技能库（8个预置技能）
│   ├── mcp_connector.py         # MCP协议连接器（Mock实现）
│   ├── stats.py                 # 调用统计持久化模块
│   ├── stats_buffered.py        # 高压优化统计（缓冲落盘177×，可无缝替换ToolStats）
│   ├── batch_executor.py        # 高压批处理执行器（Worker池+背压+限流+熔断+三档预设）
│   ├── mock_registry.py         # Mock注册表（给其他组并行开发用）
│   ├── mock_skills.py           # Mock技能库
│   └── real_tools.py            # 真实行为工具（open_url浏览器 + send_email邮件，可选注册）
│
├── gui/                         # ★ GUI 响应模块（本地网页操作台）
│   ├── server.py                # 纯标准库 HTTP 服务（工具/技能/统计/MCP 四组 API）
│   └── index.html               # 前端单页（无任何 CDN 依赖，离线可用）
│
├── tools/                       # 可视化生成脚本（纯标准库）
│   ├── gen_charts.py            # 生成 5 张 SVG 图表 → assets/charts/
│   └── gen_dashboard.py         # 模拟会话 + 生成审计看板 → assets/dashboard.html
│
├── assets/                      # 可视化产物（图表 PNG/SVG、审计看板、截图）
│
├── tests/                       # 完整测试套件
│   ├── test_all.py              # 31个测试（覆盖全部功能）
│   ├── test_highpressure.py     # 24个高压特性测试（分页/背压/缓冲/预分组/限流/熔断/并行）
│   ├── test_integration.py      # 11个端到端集成测试（模拟组3 Agent 调用回路）
│   └── test_integration_group5.py # 6个审计接入测试（模拟组5 Coordinator 纯JSON消费）
│
├── docs/                        # 三周交付文档
│   ├── week1/                   # 第1周：调研+定义+Mock
│   │   ├── 01-MCP协议调研报告.md    # MCP规范、JSON-RPC 2.0
│   │   ├── 02-接口定义文档.md        # 所有抽象类完整签名
│   │   ├── 03-Mock实现说明.md        # Mock原理和使用方法
│   │   └── test_week1.py           # 第1周专用测试(24个)
│   │
│   ├── week2/                   # 第2周：真实实现+测试验证
│   │   ├── 00-进度检查讲解指南.md    # 汇报话术和Q&A预案
│   │   ├── 01-真实功能实现报告.md    # 8工具+8技能实现细节
│   │   ├── 02-核心代码详解.md        # 6个源码文件逐行拆解
│   │   ├── 03-测试验证说明.md        # 20个test_week2测试解读
│   │   └── test_week2.py           # 第2周专用测试(20个)
│   │
│   └── week3/                   # 第3周：极端场景加固+收尾（★新增）
│       ├── 01-极端场景与安全加固报告.md  # 9类风险点审计+修复方案
│       ├── 02-组间集成指南.md          # 给组3的最终接口契约
│       ├── 03-高压请求压测与解决方案.md # 10场景压测+7套优化方案全部实装(★高压)
│       ├── 04-组3联调行动方案.md        # 三阶段联调 playbook(★联调)
│       └── test_week3.py             # 第3周极端场景测试(26个)
│
├── stress/                      # 高压压测（★新增）
│   ├── benchmark_stress.py      # 压测脚本：10场景+2组A/B对比
│   └── results.json             # 真实压测数据
│
└── presentation/                # 汇报讲解材料
    ├── 进度检查讲解脚本.md          # 完整口头汇报逐字稿
    ├── 验证原理详解.md              # 三种验证方式工作原理
    ├── 测试代码机理详解.md          # 6个案例逐行追踪测试因果链
    └── 命令流转路线详解.md          # 命令在5个文件间的完整流转图
```

---

## 核心数据一览

| 维度 | 数量 | 说明 |
|------|------|------|
| **默认工具 (Tools)** | 8 个 | copy/move/delete/create/list/read/write/run_command |
| **预置技能 (Skills)** | 8 个 | organize_downloads/backup/find_duplicates/cleanup_temp/find_large_files/system_check/disk_usage/find_files |
| **MCP Mock 工具** | 3 个 | search/weather/translate (JSON-RPC 2.0 格式) |
| **权限级别** | 3 级 | PUBLIC(0) → USER(1) → ADMIN(2) |
| **安全机制** | 4 层 | 权限检查 + 命令黑名单(空白归一化) + 受保护路径全入口拦截 + 参数预检 |
| **测试总数** | **153 个** | week1(24) + week2(20) + week3(26) + 完整项目(31) + 高压(24) + 组3集成(11) + 组5审计(6) + 真实工具(11) |
| **支持平台** | 2 个 | Windows + WSL Ubuntu（双平台全量复验通过） |
| **高压能力** | 万文件列目录 **2146×** / 缓冲落盘 **177×** / 查重 **13.8×** / 限流熔断 / 技能并行 | 见 docs/week3/03 与 stress/ |

---

## 架构设计

```
┌─────────────────────────────────────────────────────┐
│                  调用者 (main.py / Agent)            │
├──────────┬──────────┬──────────┬────────────────────┤
│          │          │          │                    │
│  ToolReg │ SkillLib │ MCPConn  │   Stats            │
│  istry   │  rary    │  ector   │                    │
│          │          │          │                    │
│ ┌──────┐ │ ┌──────┐ │ ┌──────┐│ ┌────────────────┐ │
│ │权限检查│→│ │编排逻辑│→│ │协议转换│←─┤ 计数器+持久化 │ │
│ │函数调度│ │ │直接OS │ │ │Mock存根│ │ JSON原子写入  │ │
│ │统计触发│ │ │操作   │ │ │      │ │                │ │
│ └──┬───┘ │ └──┬───┘ │ └──┬───┘ │ └────────────────┘ │
└─────│────┴─────│──────┴────│────┴────────────────────┘
      │          │           │
      ▼          ▼           ▼
┌─────────────────────────────────────────────────────┐
│            default_tools.py (8个工具实现)             │
│  安全黑名单 → subprocess/pathlib/shutil → OS内核     │
└─────────────────────────────────────────────────────┘
                          ↑
                  interfaces.py (数据契约)
        ToolResult / PermissionLevel / CallRecord / ToolSchema
```

---

## 关键设计决策

### 1. 为什么有 interfaces.py？

定义了抽象基类（ABC）作为**契约**：
- `IToolRegistry` — 注册表的通用接口
- `ISkillLibrary` — 技能库的通用接口
- `IToolStats` — 统计模块的通用接口

**好处**：真实实现和 Mock 实现**共用同一套接口签名**，可以无缝切换。

### 2. 三级权限体系为什么设计成数值比较？

```python
class PermissionLevel(Enum):
    PUBLIC = ("公开", 0)
    USER   = ("用户", 1)
    ADMIN  = ("管理员", 2)

    def rank(self) -> int:
        return self.value[1]
```

使用 `rank()` 返回整数后，只需一个 `<` 比较：
```python
if user_level.rank() < required_perm.rank():  # 拒绝
```

这比 if-elif 列举每种组合简洁得多，且容易扩展新级别。

### 3. 为什么返回值统一为 ToolResult？

```python
@dataclass
class ToolResult:
    success: bool
    result: Any = None
    error: str | None = None
```

无论成功还是失败，调用者只需要检查 `success` 字段：
- 成功 → 读 `.result`
- 失败 → 读 `.error`

不用 try-except，不用判断返回类型。

### 4. 安全机制优先级如何？

```
用户请求 → 工具存在? → 权限足够? → 安全检查通过? → 执行!
   ✗ fail     ✓        ✗ fail       ✗ fail            ✓ exec
```

**安全检查在执行之前、权限之后**——即使你有 ADMIN 权限，也不能执行 `rm -rf /`。
就像酒店老板也不能烧掉自己的酒店。

### 5. Week 3 安全加固亮点（详见 docs/week3/）

| 攻击/极端输入 | 加固前 | 加固后 |
|--------------|--------|--------|
| `rm  -rf /`（双空格绕过黑名单） | 放行执行 ❌ | 空白归一化后拦截 ✅ |
| 向 `/etc`、`C:\Windows` 写/读/复制/移动 | 无检查 ❌ | 全入口拒绝 ✅ |
| 读取 10GB 大文件 | 内存耗尽 ❌ | 10MB 上限拒绝 ✅ |
| 重复注册 MCP Mock 工具 | 崩溃 ❌ | 幂等 ✅ |
| 技能重名 `_dup` 碰撞 | 覆盖丢文件 ❌ | 递增命名 ✅ |
| 统计模块崩溃 | 连累工具调用 ❌ | 静默容错 ✅ |
| 缺必需参数 | 运行时才报错 ⚠️ | 调用前 schema 预检 ✅ |

---

## 文档阅读路线

### 我是组员，要讲解/汇报

1. 先读 `presentation/进度检查讲解脚本.md`（5分钟上手话术）
2. 再看 `presentation/命令流转路线详解.md`（被问到细节时用）
3. 最后跑一遍 `python main.py`（熟悉演示流程）

### 我要接手开发

1. 看 `docs/week2/01-真实功能实现报告.md`（了解全部功能）
2. 读 `src/interfaces.py`（理解数据契约）
3. 看 `src/tool_registry.py`（理解核心调度逻辑）
4. 跑 `python -m pytest tests/test_all.py -v`（确认环境OK）

### 我想了解概况

1. 看本 README（你现在在这里 ✅）
2. 再看 `快速开始.md`（通俗比喻版入门）

---

## 开发环境要求

- Python 3.10+
- pytest（用于运行完整测试套件）
- 无其他第三方依赖（仅使用 Python 标准库）

## 许可证

本项目为课程项目成果，仅供学习交流使用。
