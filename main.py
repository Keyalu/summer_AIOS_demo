#!/usr/bin/env python3
"""分组四 合并版 演示入口。"""

from __future__ import annotations
import json
import shutil
import tempfile
from pathlib import Path

from src import ToolRegistry, SkillLibrary, MCPConnector, ToolStats, PermissionLevel


def demo() -> None:
    print("=" * 60)
    print("分组四：工具注册 + OS Skills（合并版演示）")
    print("=" * 60)

    stats = ToolStats()
    registry = ToolRegistry(stats=stats)
    skills = SkillLibrary(registry=registry)
    mcp = MCPConnector()
    mcp.register_mock_tools(registry)

    # 1. 列出已注册的工具
    print("\n[1] 已注册工具列表")
    for schema in registry.list_tools():
        print(f"  - {schema.name}: {schema.description}")

    # 2. 权限验证
    print("\n[2] 权限验证")
    r = registry.call("run_command", {"cmd": "echo hello"}, user_level=PermissionLevel.USER)
    print(f"  user 调用 run_command: {r.to_dict()}")
    r = registry.call("run_command", {"cmd": "echo hello"}, user_level=PermissionLevel.ADMIN)
    print(f"  admin 调用 run_command: {r.to_dict()}")

    # 3. 文件操作
    print("\n[3] 文件操作")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.txt"
        r = registry.call("write_file", {"path": str(path), "content": "Hello 分组四!"})
        print(f"  写入: {r.to_dict()}")
        r = registry.call("read_file", {"path": str(path)})
        print(f"  读取: {r.to_dict()}")

    # 4. OS Skill：整理目录
    print("\n[4] OS Skill：整理目录")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "a.pdf").write_bytes(b"pdf")
        (base / "b.png").write_bytes(b"png")
        (base / "c.mp3").write_bytes(b"mp3")
        (base / "d.py").write_text("print('hello')")
        r = skills.call_skill("organize_downloads", {"path": str(base)})
        print(f"  {r.to_dict()}")

    # 5. OS Skill：备份
    print("\n[5] OS Skill：目录备份")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "data.txt").write_text("important")
        r = skills.call_skill("backup_directory", {"src": str(base)})
        print(f"  {r.to_dict()}")

    # 6. MCP Mock
    print("\n[6] MCP Mock 工具")
    r = registry.call("mcp_search", {"query": "Linux Agent OS"})
    print(f"  {r.to_dict()}")
    r = registry.call("mcp_weather", {"city": "北京", "days": 3})
    print(f"  {r.to_dict()}")

    # 7. JSON-RPC 2.0 Mock 格式
    print("\n[7] JSON-RPC 2.0 Mock 格式")
    r = mcp.mock_jsonrpc_call(registry, "mcp_weather", {"city": "上海", "days": 1})
    print(f"  {json.dumps(r, indent=2, ensure_ascii=False)}")

    # 8. 统计
    print("\n[8] 调用统计")
    print(json.dumps(stats.report(), indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("演示结束")
    print("=" * 60)


if __name__ == "__main__":
    demo()
