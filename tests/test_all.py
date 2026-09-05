"""分组四 工具注册与 OS 技能模块 — 合并版集成测试。"""

from __future__ import annotations
import os
import tempfile
from pathlib import Path

import pytest

from src import (
    ToolRegistry, SkillLibrary, MCPConnector, ToolStats,
    MockToolRegistry, MockSkillLibrary,
    PermissionLevel,
)


# ============================================================
# ToolRegistry 测试
# ============================================================

class TestToolRegistry:
    def setup_method(self):
        self.registry = ToolRegistry()

    def test_default_tools_registered(self):
        assert self.registry.has("copy_file")
        assert self.registry.has("move_file")
        assert self.registry.has("run_command")
        assert self.registry.has("read_file")
        assert self.registry.has("write_file")
        assert self.registry.has("list_directory")
        assert self.registry.has("delete_file")
        assert self.registry.has("create_folder")

    def test_register_custom_tool(self):
        def my_echo(msg: str) -> dict:
            return {"success": True, "result": f"ECHO: {msg}"}

        self.registry.register("echo", my_echo)
        assert self.registry.has("echo")
        result = self.registry.call("echo", {"msg": "hello"})
        assert result.success is True
        assert result.result == "ECHO: hello"

    def test_register_duplicate_raises(self):
        with pytest.raises(ValueError, match="已注册"):
            self.registry.register("copy_file", lambda: None)

    def test_unregister(self):
        assert self.registry.unregister("copy_file") is True
        assert not self.registry.has("copy_file")
        assert self.registry.unregister("copy_file") is False

    def test_call_nonexistent_tool(self):
        result = self.registry.call("nonexistent_tool", {})
        assert result.success is False
        assert "未注册" in result.error

    def test_permission_admin_required(self):
        # user 不能调用 run_command
        result = self.registry.call("run_command", {"cmd": "echo hi"}, PermissionLevel.USER)
        assert result.success is False
        assert "权限不足" in result.error

        # admin 可以
        result = self.registry.call("run_command", {"cmd": "echo hello"}, PermissionLevel.ADMIN)
        assert result.success is True
        assert "hello" in result.result

    def test_public_permission(self):
        result = self.registry.call("list_directory", {"path": "."}, PermissionLevel.PUBLIC)
        assert result.success is True

    # ---- 文件操作 ----

    def test_write_and_read_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.txt")
            content = "Hello 分组四!"
            r = self.registry.call("write_file", {"path": path, "content": content})
            assert r.success is True

            r = self.registry.call("read_file", {"path": path})
            assert r.success is True
            assert r.result == content

    def test_create_and_list_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "subdir")
            r = self.registry.call("create_folder", {"path": sub})
            assert r.success is True
            assert os.path.isdir(sub)

            r = self.registry.call("list_directory", {"path": tmp})
            assert r.success is True
            names = [item["name"] for item in r.result["entries"]]
            assert "subdir" in names

    def test_copy_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.txt")
            dest = os.path.join(tmp, "dest.txt")
            with open(src, "w") as f:
                f.write("original")
            r = self.registry.call("copy_file", {"src": src, "dest": dest})
            assert r.success is True
            assert os.path.exists(dest)
            with open(dest) as f:
                assert f.read() == "original"

    def test_move_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.txt")
            dest = os.path.join(tmp, "moved.txt")
            with open(src, "w") as f:
                f.write("move me")
            r = self.registry.call("move_file", {"src": src, "dest": dest})
            assert r.success is True
            assert not os.path.exists(src)
            assert os.path.exists(dest)

    def test_delete_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "delete_me.txt")
            with open(path, "w") as f:
                f.write("delete me")
            r = self.registry.call("delete_file", {"path": path})
            assert r.success is True
            assert not os.path.exists(path)

    def test_call_with_wrong_params(self):
        r = self.registry.call("copy_file", {"wrong_param": "value"})
        assert r.success is False
        assert "参数错误" in r.error

    def test_dangerous_command_blocked(self):
        r = self.registry.call(
            "run_command",
            {"cmd": "rm -rf /"},
            PermissionLevel.ADMIN,
        )
        assert r.success is False
        assert "拒绝执行" in r.error

    # ---- 统计 ----

    def test_stats_integration(self):
        stats = ToolStats()
        reg = ToolRegistry(stats=stats)
        reg.call("list_directory", {"path": "."})
        reg.call("list_directory", {"path": "."})
        assert stats.total_calls() == 2
        report = stats.report()
        assert report["list_directory"]["calls"] == 2
        assert report["list_directory"]["success"] == 2


# ============================================================
# SkillLibrary 测试
# ============================================================

class TestSkillLibrary:
    def setup_method(self):
        self.skills = SkillLibrary()

    def test_list_skills(self):
        names = [s.name for s in self.skills.list_skills()]
        assert "organize_downloads" in names
        assert "backup_directory" in names
        assert "find_duplicate_files" in names

    def test_organize_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(os.path.join(tmp, "a.pdf")).touch()
            Path(os.path.join(tmp, "b.jpg")).touch()
            Path(os.path.join(tmp, "c.mp3")).touch()

            r = self.skills.call_skill("organize_downloads", {"path": tmp})
            assert r.success is True
            assert r.result["total_moved"] == 3
            assert os.path.isdir(os.path.join(tmp, "文档"))
            assert os.path.isdir(os.path.join(tmp, "图片"))
            assert os.path.isdir(os.path.join(tmp, "音频"))

    def test_organize_nonexistent_dir(self):
        r = self.skills.call_skill("organize_downloads", {"path": "/nonexistent/path"})
        assert r.success is False

    def test_backup_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(os.path.join(tmp, "data.txt")).write_text("important")
            r = self.skills.call_skill("backup_directory", {"src": tmp})
            assert r.success is True
            assert "已备份" in r.result

    def test_find_duplicate_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(os.path.join(tmp, "a.txt")).write_text("duplicate content")
            Path(os.path.join(tmp, "b.txt")).write_text("duplicate content")
            Path(os.path.join(tmp, "c.txt")).write_text("unique")

            r = self.skills.call_skill("find_duplicate_files", {"path": tmp})
            assert r.success is True
            assert r.result["duplicate_groups"] >= 1

    def test_find_large_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            big = os.path.join(tmp, "big.dat")
            with open(big, "wb") as f:
                f.write(b"\x00" * (50 * 1024 * 1024))
            r = self.skills.call_skill("find_large_files", {"path": tmp, "min_size_mb": 10})
            assert r.success is True
            assert len(r.result["files"]) >= 1
            assert r.result["files"][0]["size_mb"] >= 10

    def test_system_check(self):
        r = self.skills.call_skill("system_check")
        assert r.success is True
        assert "disk" in r.result
        assert "memory" in r.result

    def test_disk_usage(self):
        r = self.skills.call_skill("disk_usage")
        assert r.success is True
        assert r.result["total_gb"] > 0


# ============================================================
# MCPConnector 测试
# ============================================================

class TestMCPConnector:
    def setup_method(self):
        self.mcp = MCPConnector()
        self.registry = ToolRegistry()

    def test_register_mock_tools(self):
        self.mcp.register_mock_tools(self.registry)
        assert self.registry.has("mcp_search")
        assert self.registry.has("mcp_weather")
        assert self.registry.has("mcp_translate")

    def test_mock_search(self):
        self.mcp.register_mock_tools(self.registry)
        r = self.registry.call("mcp_search", {"query": "test query"})
        assert r.success is True
        assert "test query" in r.result

    def test_jsonrpc_format(self):
        self.mcp.register_mock_tools(self.registry)
        r = self.mcp.mock_jsonrpc_call(self.registry, "mcp_weather", {"city": "上海"})
        assert r["jsonrpc"] == "2.0"
        assert r["id"] is not None
        assert r["error"] is None
        assert "上海" in r["result"]

    def test_connect_server(self):
        r = self.mcp.connect_server("test-server", {"command": "python"})
        assert r["success"] is True
        assert len(self.mcp.list_servers()) == 1

    def test_connect_real_mcp_placeholder(self):
        r = self.mcp.connect_real_mcp("npx", ["-y", "server"])
        assert r["success"] is False
        assert "尚未实现" in r["error"]


# ============================================================
# Mock 测试
# ============================================================

class TestMockImplementations:
    def test_mock_registry(self):
        reg = MockToolRegistry()
        assert reg.has("copy_file")
        r = reg.call("copy_file", {"src": "/a", "dest": "/b"})
        assert r.success is True
        assert "[Mock]" in r.result

    def test_mock_skills(self):
        skills = MockSkillLibrary()
        r = skills.call_skill("organize_downloads")
        assert r.success is True
        assert r.result["status"] == "[Mock] 模拟执行成功"


# ============================================================
# 集成测试
# ============================================================

class TestIntegration:
    def test_full_data_flow(self):
        stats = ToolStats()
        registry = ToolRegistry(stats=stats)
        skills = SkillLibrary(registry=registry)
        mcp = MCPConnector()
        mcp.register_mock_tools(registry)

        # 1. OS skill 调用
        r1 = skills.call_skill("disk_usage")
        assert r1.success is True

        # 2. MCP 搜索
        r2 = registry.call("mcp_search", {"query": "Python 最佳实践"})
        assert r2.success is True

        # 3. 文件写入 + 读取
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            content = '{"project": "Agentic OS", "group": 4}'
            registry.call("write_file", {"path": path, "content": content})
            r3 = registry.call("read_file", {"path": path})
            assert r3.success is True
            assert "Agentic OS" in r3.result

        # 4. 统计验证
        assert stats.total_calls() > 0
        assert stats.success_rate() == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
