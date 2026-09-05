#!/usr/bin/env python3
"""不依赖 pytest 的快速验证脚本，用于在 WSL 等未安装 pytest 的环境验证核心功能。"""

from __future__ import annotations
import os
import shutil
import tempfile
from pathlib import Path

from src import (
    ToolRegistry, SkillLibrary, MCPConnector, ToolStats,
    MockToolRegistry, MockSkillLibrary,
    PermissionLevel,
)


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}")
    if not condition:
        raise AssertionError(name)


def main() -> None:
    print("=" * 60)
    print("分组四合并版 — 快速验证 (无需 pytest)")
    print("=" * 60)

    # 1. ToolRegistry
    print("\n[1] ToolRegistry")
    reg = ToolRegistry()
    check("默认工具已注册", reg.has("copy_file") and reg.has("run_command"))

    result = reg.call("run_command", {"cmd": "echo hello"}, PermissionLevel.ADMIN)
    check("admin 可执行命令", result.success and "hello" in result.result)

    result = reg.call("run_command", {"cmd": "echo hello"}, PermissionLevel.USER)
    check("user 无法执行 admin 命令", not result.success and "权限不足" in result.error)

    result = reg.call("run_command", {"cmd": "rm -rf /"}, PermissionLevel.ADMIN)
    check("危险命令被拦截", not result.success and "拒绝执行" in result.error)

    # 2. 文件操作
    print("\n[2] 文件操作")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "a.txt")
        dest = os.path.join(tmp, "b.txt")
        Path(src).write_text("hello")
        result = reg.call("copy_file", {"src": src, "dest": dest})
        check("复制文件", result.success and Path(dest).exists())

    # 3. SkillLibrary
    print("\n[3] SkillLibrary")
    skills = SkillLibrary()
    with tempfile.TemporaryDirectory() as tmp:
        Path(os.path.join(tmp, "x.pdf")).touch()
        Path(os.path.join(tmp, "y.jpg")).touch()
        result = skills.call_skill("organize_downloads", {"path": tmp})
        check("整理目录", result.success and result.result["total_moved"] == 2)

    result = skills.call_skill("disk_usage")
    check("磁盘使用", result.success and result.result["total_gb"] > 0)

    # 4. MCPConnector
    print("\n[4] MCPConnector")
    mcp = MCPConnector()
    mcp_reg = ToolRegistry()
    mcp.register_mock_tools(mcp_reg)
    check("MCP Mock 工具已注册", mcp_reg.has("mcp_search"))

    result = mcp_reg.call("mcp_search", {"query": "test"})
    check("MCP Mock 搜索", result.success and "test" in result.result)

    rpc = mcp.mock_jsonrpc_call(mcp_reg, "mcp_weather", {"city": "北京"})
    check("JSON-RPC 2.0 格式", rpc.get("jsonrpc") == "2.0" and "北京" in rpc["result"])

    # 5. Stats
    print("\n[5] ToolStats")
    stats = ToolStats()
    reg2 = ToolRegistry(stats=stats)
    reg2.call("list_directory", {"path": "."}, PermissionLevel.PUBLIC)
    reg2.call("list_directory", {"path": "."}, PermissionLevel.PUBLIC)
    check("统计集成", stats.total_calls() == 2)

    # 6. Mock
    print("\n[6] Mock 实现")
    mock_reg = MockToolRegistry()
    check("Mock 工具存在", mock_reg.has("copy_file"))
    result = mock_reg.call("copy_file", {"src": "/a", "dest": "/b"})
    check("Mock 调用", result.success and "[Mock]" in result.result)

    print("\n" + "=" * 60)
    print("所有快速验证通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
