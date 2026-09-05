"""
demo_io.py — 分组四 Tools + OS Skills 输入输出全链路演示

一条命令看懂：Agent（组3）的一次调用，如何经过
  输入 → 注册表检查（存在性/权限/schema） → 工具执行 → 统计记录 → 统一输出 ToolResult

运行方式：
    python demo_io.py          # Windows
    /usr/bin/python3 demo_io.py  # WSL / Linux

全程在系统临时目录沙箱内运行，不碰真实文件。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Windows 控制台中文输出保护
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.tool_registry import ToolRegistry
from src.skill_library import SkillLibrary
from src.stats import ToolStats
from src.interfaces import PermissionLevel


# ============================================================
# 演示排版工具
# ============================================================

def banner(no: int, title: str) -> None:
    print()
    print("=" * 62)
    print(f"  演示{no}  {title}")
    print("=" * 62)


def show_input(name: str, params: dict, level: str = "user") -> None:
    print()
    print("[输入] Agent 发起调用")
    print(json.dumps(
        {"tool": name, "params": params, "caller_level": level},
        ensure_ascii=False, indent=2,
    ))


def stage(n: int, text: str) -> None:
    print(f"  Stage {n} | {text}")


def show_output(result, source: str = "Registry") -> None:
    print()
    print(f"[输出] {source}返回的 ToolResult")
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))


def sandbox_dir() -> Path:
    """在临时目录里造几个文件，供演示读取，避免碰真实数据。"""
    d = Path(tempfile.mkdtemp(prefix="demo_io_"))
    (d / "report.txt").write_text("季度报告内容", encoding="utf-8")
    (d / "data.csv").write_text("id,name\n1,alice\n", encoding="utf-8")
    (d / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
    (d / "notes.md").write_text("# 笔记", encoding="utf-8")
    return d


# ============================================================
# 初始化：组3拿到包后 5 分钟内的标准接入方式
# ============================================================

def build_stack():
    stats = ToolStats()
    registry = ToolRegistry(stats=stats)      # 真实注册表（内置8个OS工具）
    skills = SkillLibrary(registry=registry)  # 技能库（8个OS技能）
    return stats, registry, skills


# ============================================================
# 演示 1：正常调用 — list_directory（PUBLIC 权限）
# ============================================================

def demo1(registry) -> None:
    banner(1, "正常调用：list_directory（一路绿灯）")
    target = sandbox_dir()

    show_input("list_directory", {"path": str(target), "limit": 2}, "public")

    print()
    print("[过程] registry.call('list_directory', params) 内部依次发生：")
    stage(1, "存在性检查 —— 'list_directory' 已注册 ✓")
    stage(2, "权限检查 —— 工具要求 public，调用者是 public，放行 ✓")
    stage(3, "schema 预检 —— path/offset/limit 均为可选参数，无缺失 ✓")
    stage(4, "执行工具函数 —— os.scandir 扫描目录（Week3 分页版）")
    stage(5, "记录统计 —— stats.record(耗时, 成功)")

    result = registry.call("list_directory", {"path": str(target), "limit": 2},
                           user_level=PermissionLevel.PUBLIC)
    show_output(result)
    print(">>> 关键点：无论成功失败，组3拿到的永远是 {success, result/error} 三件套")


# ============================================================
# 演示 2：权限拦截 — run_command 需要 ADMIN
# ============================================================

def demo2(registry) -> None:
    banner(2, "权限拦截：run_command 需要 ADMIN，普通用户被拒")
    show_input("run_command", {"cmd": "rm -rf /tmp/demo"}, "user")

    print()
    print("[过程]")
    stage(1, "存在性检查 —— 已注册 ✓")
    stage(2, "权限检查 —— 工具要求 admin，调用者是 user → 拦截 ✗")
    stage(3, "(未执行) 工具函数根本不会被调用 —— 危险命令到不了 shell")

    result = registry.call("run_command", {"cmd": "rm -rf /tmp/demo"})  # 默认 user
    show_output(result)
    print(">>> 关键点：拦截发生在执行之前，异常永远不抛出，只返回 fail")


# ============================================================
# 演示 3：参数预检 — write_file 缺少必需参数
# ============================================================

def demo3(registry) -> None:
    banner(3, "参数预检：write_file 少传 content，提前报错")
    show_input("write_file", {"path": "C:/tmp/out.txt"}, "user")

    print()
    print("[过程]")
    stage(1, "存在性检查 —— 已注册 ✓")
    stage(2, "权限检查 —— user 级工具，放行 ✓")
    stage(3, "schema 预检 —— 缺少必需参数 content → 拦截 ✗")
    stage(4, "(未执行)")

    result = registry.call("write_file", {"path": "C:/tmp/out.txt"})
    show_output(result)
    print(">>> 关键点：错误在进工具函数之前就被抓住，Agent 能立刻自纠正")


# ============================================================
# 演示 4：技能（Skill）— system_check，一层编排多层工具
# ============================================================

def demo4(skills) -> None:
    banner(4, "技能调用：system_check —— Skill = 多个 Tool 的编排")
    print()
    print("[输入] Agent 发起调用")
    print(json.dumps(
        {"skill": "system_check", "params": {}, "caller_level": "user"},
        ensure_ascii=False, indent=2,
    ))

    print()
    print("[过程]")
    stage(1, "Agent 调 skills.call_skill('system_check')")
    stage(2, "技能内部编排：读磁盘 → 读内存 → 数进程 → 拼主机名")
    stage(3, "注意：技能调用不经过 Registry，不产生重复统计（Week3 契约）")

    result = skills.call_skill("system_check")
    show_output(result, source="SkillLibrary")
    print(">>> 关键点：Skill 是'组合拳'——一次输入，多个底层动作，一个统一输出")
    print(">>> 说明：Windows 下 memory/process_count 显示不可用是预期行为——")
    print("    这两个数据源是 Linux 的 /proc 文件系统，在 WSL/Ubuntu 演示时会显示真实值，")
    print("    这本身就是跨平台降级设计的活例子：取不到就如实上报，不假装成功。")


# ============================================================
# 演示 5：统计报表 — 前面 4 次调用的沉淀
# ============================================================

def demo5(stats) -> None:
    banner(5, "统计沉淀：刚才 4 次调用全被记下来了")
    print()
    print("[输出] stats.report()")
    print(json.dumps(stats.report(), ensure_ascii=False, indent=2))
    print(f"\n总调用次数: {stats.total_calls()}")
    print(">>> 关键点：Agent 可以据此做自省——哪个工具失败率高就少用它")


# ============================================================
# 主流程
# ============================================================

def main() -> None:
    print("*" * 62)
    print("*  分组四 · Tools + OS Skills · 输入输出全链路演示")
    print("*  运行约 10 秒，全程在临时目录沙箱内，不碰真实文件")
    print("*" * 62)

    stats, registry, skills = build_stack()

    demo1(registry)
    demo2(registry)
    demo3(registry)
    demo4(skills)
    demo5(stats)

    print()
    print("=" * 62)
    print("演示结束。一句话总结：")
    print("  输入是 (工具名, 参数, 调用者身份)，")
    print("  输出永远是 {success, result/error}，")
    print("  中间三道闸门（存在性/权限/schema）保证坏输入进不了工具。")
    print("=" * 62)


if __name__ == "__main__":
    main()
