"""
Week 1 单元验证：接口定义 + Mock 实现 + MCP 协议

验证三件事：
1. 接口定义是否完整（interfaces.py 中有没有所有要求的类）
2. Mock 实现是否可用（能否 import 并调用）
3. MCP JSON-RPC 2.0 Mock 格式是否正确
"""

from __future__ import annotations
import sys
import os

# 添加合并版项目的 src 目录到 Python 路径
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "tools-os-skills-merged"
))

import pytest
from src import (
    MockToolRegistry, MockSkillLibrary, MCPConnector, ToolRegistry,
    PermissionLevel,
)
from src.interfaces import (
    IToolRegistry, ISkillLibrary, IToolStats,
    ToolResult, ToolSchema, ToolParam, ToolParamType,
    CallRecord, PermissionLevel as PermEnum,
)


# ============================================================
# Phase 1: 接口定义验证
# ============================================================

class TestInterfaceDefinitions:
    """验证 interfaces.py 中的所有接口定义是否存在且结构正确。"""

    def test_itoolregistry_exists(self):
        """IToolRegistry 抽象接口存在。"""
        assert IToolRegistry is not None
        assert hasattr(IToolRegistry, "register")
        assert hasattr(IToolRegistry, "call")
        assert hasattr(IToolRegistry, "list_tools")
        assert hasattr(IToolRegistry, "unregister")
        assert hasattr(IToolRegistry, "has")

    def test_iskilllibrary_exists(self):
        """ISkillLibrary 抽象接口存在。"""
        assert ISkillLibrary is not None
        assert hasattr(ISkillLibrary, "register_skill")
        assert hasattr(ISkillLibrary, "call_skill")
        assert hasattr(ISkillLibrary, "list_skills")

    def test_itoolstats_exists(self):
        """IToolStats 统计接口存在。"""
        assert IToolStats is not None
        assert hasattr(IToolStats, "record")
        assert hasattr(IToolStats, "report")
        assert hasattr(IToolStats, "total_calls")

    def test_toolresult_structure(self):
        """ToolResult 统一返回格式正确。"""
        # 成功情况
        ok = ToolResult.ok("操作完成")
        assert ok.success is True
        assert ok.result == "操作完成"
        assert ok.error is None
        assert ok.to_dict() == {"success": True, "result": "操作完成"}

        # 失败情况
        fail = ToolResult.fail("文件不存在")
        assert fail.success is False
        assert fail.error == "文件不存在"
        assert fail.result is None
        assert fail.to_dict() == {"success": False, "error": "文件不存在"}

    def test_toolschema_structure(self):
        """ToolSchema 结构正确，可转 MCP inputSchema。"""
        schema = ToolSchema(
            name="copy_file",
            description="复制文件",
            parameters=[
                ToolParam("src", ToolParamType.STRING, "源路径"),
                ToolParam("dest", ToolParamType.STRING, "目标路径"),
            ],
        )
        assert schema.name == "copy_file"
        assert schema.description == "复制文件"
        assert len(schema.parameters) == 2

        d = schema.to_dict()
        assert d["name"] == "copy_file"
        assert "inputSchema" in d
        assert d["inputSchema"]["required"] == ["src", "dest"]

    def test_toolparam_default(self):
        """ToolParam 可选参数默认值。"""
        p = ToolParam("path", ToolParamType.STRING, "目录", required=False, default="~")
        assert p.required is False
        assert p.default == "~"

    def test_permission_level_enum(self):
        """PermissionLevel 三级权限值正确。"""
        assert PermissionLevel.PUBLIC == "public"
        assert PermissionLevel.USER == "user"
        assert PermissionLevel.ADMIN == "admin"
        assert PermissionLevel.PUBLIC.rank() == 0
        assert PermissionLevel.USER.rank() == 1
        assert PermissionLevel.ADMIN.rank() == 2

    def test_callrecord_fields(self):
        """CallRecord 数据类字段完整。"""
        r = CallRecord(tool_name="test", params={}, success=True, duration_ms=12.5)
        assert r.tool_name == "test"
        assert r.success is True
        assert r.duration_ms == 12.5
        assert r.error is None


# ============================================================
# Phase 2: Mock 实现验证
# ============================================================

class TestMockRegistry:
    """验证 MockToolRegistry 可用且接口签名正确。"""

    def setup_method(self):
        self.reg = MockToolRegistry()

    def test_default_mock_tools_registered(self):
        """8 个默认 Mock 工具已注册。"""
        for name in [
            "copy_file", "move_file", "delete_file", "create_folder",
            "list_directory", "run_command", "read_file", "write_file",
        ]:
            assert self.reg.has(name), f"缺少 Mock 工具: {name}"

    def test_mock_call_returns_mock_label(self):
        """Mock 调用返回带 [Mock] 标记的结果。"""
        result = self.reg.call("copy_file", {"src": "/a", "dest": "/b"})
        assert result.success is True
        assert "[Mock]" in result.result

    def test_mock_unregistered_tool(self):
        """Mock 未注册工具返回错误。"""
        result = self.reg.call("nonexistent", {})
        assert result.success is False
        assert "未注册" in result.error

    def test_mock_list_tools(self):
        """Mock 列出工具返回 schema 列表。"""
        tools = self.reg.list_tools()
        assert len(tools) >= 8
        names = [t.name for t in tools]
        assert "copy_file" in names


class TestMockSkills:
    """验证 MockSkillLibrary 可用。"""

    def setup_method(self):
        self.skills = MockSkillLibrary()

    def test_mock_skills_registered(self):
        """8 个 Mock 技能已注册。"""
        names = [s.name for s in self.skills.list_skills()]
        for skill in [
            "organize_downloads", "system_check", "find_files",
            "cleanup_temp", "backup_directory",
            "find_large_files", "find_duplicate_files", "disk_usage",
        ]:
            assert skill in names, f"缺少 Mock 技能: {skill}"

    def test_mock_skill_call(self):
        """Mock 技能调用返回模拟数据。"""
        result = self.skills.call_skill("organize_downloads", {"path": "/tmp"})
        assert result.success is True
        assert result.result["status"] == "[Mock] 模拟执行成功"
        assert "params" in result.result

    def test_mock_skill_unregistered(self):
        """Mock 技能未注册返回错误。"""
        result = self.skills.call_skill("nonexistent_skill")
        assert result.success is False
        assert "未注册" in result.error


# ============================================================
# Phase 3: MCP JSON-RPC 2.0 协议验证
# ============================================================

class TestMCPProtocol:
    """验证 MCP JSON-RPC 2.0 Mock 格式正确。"""

    def setup_method(self):
        self.mcp = MCPConnector()
        self.registry = ToolRegistry()

    def test_mock_tools_registered_to_registry(self):
        """MCP Mock 工具成功注册到真实 ToolRegistry。"""
        self.mcp.register_mock_tools(self.registry)
        assert self.registry.has("mcp_search")
        assert self.registry.has("mcp_weather")
        assert self.registry.has("mcp_translate")

    def test_mcp_mock_search(self):
        """MCP Mock 搜索返回相关结果。"""
        self.mcp.register_mock_tools(self.registry)
        result = self.registry.call("mcp_search", {"query": "Linux"})
        assert result.success is True
        assert "Linux" in result.result

    def test_jsonrpc_success_format(self):
        """JSON-RPC 2.0 成功响应格式正确。"""
        self.mcp.register_mock_tools(self.registry)
        r = self.mcp.mock_jsonrpc_call(self.registry, "mcp_weather", {"city": "上海"})

        assert r["jsonrpc"] == "2.0"
        assert "id" in r
        assert isinstance(r["id"], int)
        assert r["error"] is None
        assert "上海" in r["result"]

    def test_jsonrpc_error_format(self):
        """JSON-RPC 2.0 错误响应格式正确（Week3 细分错误码后，未注册工具返回 -32601）。"""
        r = self.mcp.mock_jsonrpc_call(self.registry, "nonexistent_tool", {})
        assert r["jsonrpc"] == "2.0"
        assert "id" in r
        assert r["result"] is None
        assert r["error"] is not None
        assert r["error"]["code"] == -32601  # Method not found（Week3 起与执行失败 -32603 区分）

    def test_mcp_server_management(self):
        """MCP Server 连接/断开/列表功能正常。"""
        r = self.mcp.connect_server("s1", {"command": "python"})
        assert r["success"] is True
        assert len(self.mcp.list_servers()) == 1

        r = self.mcp.disconnect_server("s1")
        assert r["success"] is True
        assert len(self.mcp.list_servers()) == 0

    def test_connect_real_mcp_placeholder(self):
        """真实 MCP 接入预留接口存在。"""
        r = self.mcp.connect_real_mcp("npx", ["-y", "server"])
        assert r["success"] is False
        assert "尚未实现" in r["error"]


# ============================================================
# Phase 4: 接口契约一致性
# ============================================================

class TestInterfaceConsistency:
    """验证 Mock 和真实实现遵循同一接口。"""

    def test_mock_registry_implements_interface(self):
        """MockToolRegistry 实现了 IToolRegistry 接口。"""
        mock = MockToolRegistry()
        assert isinstance(mock, IToolRegistry)

    def test_mock_skills_implements_interface(self):
        """MockSkillLibrary 实现了 ISkillLibrary 接口。"""
        mock = MockSkillLibrary()
        assert isinstance(mock, ISkillLibrary)

    def test_mock_and_real_same_signature(self):
        """Mock 和真实实现的 call() 签名一致。"""
        mock = MockToolRegistry()
        real = ToolRegistry()

        # 两者都有 call 方法，接受 name 和 params
        mr = mock.call("copy_file", {"src": "/a", "dest": "/b"})
        rr = real.call("list_directory", {"path": "."}, PermissionLevel.PUBLIC)

        # 返回值类型一致
        assert isinstance(mr, ToolResult)
        assert isinstance(rr, ToolResult)
        assert hasattr(mr, "success")
        assert hasattr(rr, "success")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
