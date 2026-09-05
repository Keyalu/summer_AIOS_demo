# 运行指令手册

> 本文档提供 **linux-agentic-os-group4** 项目在 **Windows** 和 **WSL Ubuntu** 双平台下的完整运行指令。

---

## 目录

1. [环境准备](#环境准备)
2. [快速开始（3种方式）](#快速开始3种方式)
3. [运行测试详解](#运行测试详解)
4. [各平台详细说明](#各平台详细说明)
5. [进度检查演示路线](#进度检查演示路线)
6. [常见问题排查](#常见问题排查)
7. [高级用法](#高级用法)

---

## 环境准备

### Windows (推荐)

```bash
cd linux-agentic-os-group4
python --version          # 应显示 Python 3.10+
python -m pytest --version  # 如需运行测试套件
```

### WSL Ubuntu

```bash
cd /path/to/linux-agentic-os-group4
/usr/bin/python3 --version    # 系统Python（推荐）

# 注意：如果终端显示 (base) 表示激活了 conda/miniforge
# 此时的 python3 可能缺少 pytest，解决方案：
#   方案A：conda deactivate（退出conda环境）
#   方案B：/usr/bin/python3 -m pytest ...（使用系统Python完整路径）
```

---

## 快速开始（3种方式）

### 方式一：自动演示（最简单，无需依赖）

```bash
# Windows
cd linux-agentic-os-group4
python main.py

# WSL Ubuntu
cd linux-agentic-os-group4
python3 main.py
```

**预期输出**：8步演示 —— 工具列表、权限验证、文件操作、OS技能整理、备份、MCP Mock、JSON-RPC格式、统计报告。

---

### 方式二：快速验证（无 pytest 依赖）

```bash
# Windows
python quick_check.py

# WSL Ubuntu
/usr/bin/python3 quick_check.py
```

**预期输出**：12项核心功能检查，每项显示 `[PASS]` 或 `[FAIL]`。

---

### 方式三：完整测试套件（需要 pytest）

#### 运行全部31个测试

```bash
# Windows
python -m pytest tests/test_all.py -v

# WSL Ubuntu
/usr/bin/python3 -m pytest tests/test_all.py -v
```

#### 按周次分别运行

```bash
# 第1周测试（24个）
python -m pytest docs/week1/test_week1.py -v

# 第2周测试（20个）
python -m pytest docs/week2/test_week2.py -v
```

#### 按模块单独运行

```bash
# 只测 ToolRegistry
python -m pytest tests/test_all.py::TestToolRegistry -v

# 只测 SkillLibrary
python -m pytest tests/test_all.py::TestSkillLibrary -v

# 只测安全机制
python -m pytest tests/test_all.py::TestSecurity -v
```

---

## 运行测试详解

### 测试输出解读

```
==================== test session starts =====================
platform win32 -- Python 3.13, pytest-8.x.x
rootdir: ...\linux-agentic-os-group4
collected 31 items

tests/test_all.py::TestToolRegistry::test_default_tools_registered PASSED  [  3%]
tests/test_all.py::TestToolRegistry::test_call_tool PASSED             [  6%]
...
tests/test_all.py::TestIntegration::test_full_workflow PASSED         [100%]

==================== 31 passed in 0.xx s ====================
```

| 关键信息 | 含义 |
|---------|------|
| `PASSED` | 测试通过 ✅ |
| `FAILED` | 测试失败 ❌（会显示具体错误和堆栈） |
| `31 passed` | 全部通过 |
| `0.xx s` | 总耗时 |

### 常用 pytest 参数

```bash
-v              # 详细输出每个测试的结果
--lf            # 只运行上次失败的测试
-k "权限"       # 只运行名称包含"权限"的测试
-s              # 显示 print 输出（调试用）
--tb=short      # 简短的错误追踪
--maxfail=3     # 失败3个后停止
```

---

## 各平台详细说明

### Windows 完整流程

```powershell
# Step 1: 打开 PowerShell 或 CMD
# Step 2: 进入项目目录
cd C:\你的路径\linux-agentic-os-group4

# Step 3: 运行演示
python main.py

# Step 4: 快速验证
python quick_check.py

# Step 5: 完整测试
python -m pytest tests/test_all.py -v
```

### WSL Ubuntu 完整流程

```bash
# Step 1: 启动 WSL
wsl

# Step 2: 检查Python环境（重要！）
which python3
# 如果输出 /root/miniforge3/bin/python3 → 需要注意

# Step 3a: 如果是 miniforge 环境（有 (base) 前缀）
conda deactivate                    # 退出 conda
which python3                       # 应该显示 /usr/bin/python3

# Step 3b: 或者直接用系统Python完整路径（一步到位）
alias py=/usr/bin/python3

# Step 4: 进入项目目录
cd /mnt/c/你的路径/linux-agentic-os-group4

# Step 5: 运行演示
py main.py                          # 或 python3 main.py（已deactivate）

# Step 6: 运行测试
py -m pytest tests/test_all.py -v  # 或 /usr/bin/python3 -m pytest ...

# Step 7: 快速验证
py quick_check.py
```

---

## 进度检查演示路线

### 5分钟现场演示（推荐）

```bash
# 【第1分钟】运行自动演示 — 展示全貌
python main.py

# 【第2-3分钟】快速验证 — 核心功能正常
python quick_check.py

# 【第4-5分钟】完整测试 — 质量保障
python -m pytest tests/test_all.py -v
```

### 配合讲解话术

| 步骤 | 命令 | 讲解要点 |
|------|------|---------|
| 1 | `python main.py` | "这是自动演示，展示工具注册、权限控制、OS技能编排等8大功能" |
| 2 | `python quick_check.py` | "快速验证脚本无需pytest，检验12项核心能力" |
| 3 | `pytest tests/ -v` | "125个自动化测试覆盖全部模块，双平台通过" |
| 4 | （打开源码） | "src/ 目录下9个文件实现全部逻辑，纯标准库无第三方依赖" |

---

## 常见问题排查

### Q1: `ModuleNotFoundError: No module named 'src'`

**原因**：不在项目根目录下运行。

**解决**：
```bash
cd linux-agentic-os-group4    # 必须进入项目根目录
ls                            # 应看到 src/, tests/, main.py
python main.py
```

---

### Q2: `No module named 'pytest'`

**原因**：当前Python环境没有安装 pytest。

**解决**：
```bash
# Windows
pip install pytest

# WSL（使用系统Python pip）
/usr/bin/python3 -m pip install pytest --user

# 或者跳过测试，只用 quick_check.py
python quick_check.py        # 不需要 pytest！
```

---

### Q3: WSL 中 `python3` 版本不对或找不到模块

**原因**：conda/miniforge 的 python3 覆盖了系统版本。

**解决**：
```bash
# 方法1：退出 conda（推荐）
conda deactivate
python3 --version            # 应显示系统Python版本

# 方法2：始终用完整路径
/usr/bin/python3 main.py
/usr/bin/python3 -m pytest tests/test_all.py -v
```

---

### Q4: 中文乱码

**原因**：终端编码不是 UTF-8。

**解决**：
```bash
# Windows CMD/PowerShell
chcp 65001

# WSL（通常默认UTF-8，如遇问题）
export LANG=en_US.UTF-8
```

---

### Q5: 权限错误 (Permission denied)

**原因**：WSL 中文件权限问题。

**解决**：
```bash
# 赋予执行权限
chmod -R +x *.py src/ tests/ docs/

# 或显式调用解释器（推荐）
python3 main.py               # 不要 ./main.py
```

---

### Q6: 部分测试跨平台差异失败

**原因**：Windows 和 Linux 文件系统行为不同。

**处理**：
```bash
# 查看具体失败信息
python -m pytest tests/test_all.py -v --tb=short

# 大部分已做跨平台兼容处理
# 极少数差异属于正常现象，不影响核心功能验证
```

---

## 高级用法

### Python 交互式环境

```bash
python
```

```python
>>> from src import ToolRegistry, SkillLibrary, PermissionLevel, ToolStats

# 创建带统计功能的注册表
stats = ToolStats()
registry = ToolRegistry(stats=stats)

# 列出所有工具
for t in registry.list_tools():
    print(f"  [{t.permission.value}] {t.name}: {t.description}")

# 调用工具
r = registry.call("list_directory", {"path": "."}, PermissionLevel.PUBLIC)
print(r.to_dict())

# 使用技能库
skills = SkillLibrary(registry=registry)
r = skills.call_skill("disk_usage")
print(f"磁盘: {r.result['used_gb']}GB / {r.result['total_gb']}GB ({r.result['percent']}%)")

# 查看调用统计
print(stats.report())
print(f"总调用: {stats.total_calls()}, 成功率: {stats.success_rate():.1%}")
```

### 作为模块被其他项目导入

```python
import sys
sys.path.append("path/to/linux-agentic-os-group4")

from src import (
    ToolRegistry,           # 真实注册表
    SkillLibrary,           # 技能库
    MCPConnector,           # MCP连接器
    ToolStats,              # 统计模块
    PermissionLevel,        # 权限枚举
    ToolResult,             # 统一返回值
    IToolRegistry,          # 抽象接口
)

# 生产环境用真实实现
prod = ToolRegistry(stats=ToolStats())

# 测试环境用Mock（不执行真实操作）
from src import MockToolRegistry
test = MockToolRegistry()

# 两者接口完全相同，可无缝切换！
```

---

## 项目文件清单

| 路径 | 用途 | 如何使用 |
|------|------|---------|
| `main.py` | 自动演示入口 | `python main.py` |
| `quick_check.py` | 无需pytest的验证 | `python quick_check.py` |
| `tests/test_all.py` | 31个完整测试 | `pytest tests/test_all.py -v` |
| `docs/week1/test_week1.py` | 第1周24个测试 | `pytest docs/week1/test_week1.py -v` |
| `docs/week2/test_week2.py` | 第2周20个测试 | `pytest docs/week2/test_week2.py -v` |
| `src/` | 9个核心源码文件 | 作为模块 `from src import ...` |
| `README.md` | 项目总说明 | 阅读 |
| `快速开始.md` | 5分钟上手指南 | 阅读 |
| `本文档` | 完整运行手册 | 正在阅读 ✅ |
| `presentation/` | 4份汇报讲解材料 | 进度检查前阅读 |

---

## 最简命令速查卡

```bash
# === Windows ===
cd linux-agentic-os-group4
python main.py                              # 演示
python quick_check.py                       # 快速验证
python -m pytest tests/test_all.py -v       # 完整测试(31个)

# === WSL Ubuntu ===
cd /path/to/linux-agentic-os-group4
conda deactivate                            # （推荐先执行）
python3 main.py                             # 演示
/usr/bin/python3 quick_check.py             # 快速验证
/usr/bin/python3 -m pytest tests/test_all.py -v  # 完整测试

# === 一键全跑（进度检查用） ===
python main.py && python quick_check.py && python -m pytest tests/test_all.py -v
```

---

*文档更新时间：2026年7月17日*
*适用版本：linux-agentic-os-group4 v1.0*
