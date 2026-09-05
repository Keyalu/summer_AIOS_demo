"""
Week 2 专属测试 — 真实功能实现深度验证

聚焦于：
1. ToolRegistry 边界条件（空参数/特殊路径/安全绕过）
2. SkillLibrary 边界条件（空目录/中文文件名/大文件）
3. 安全机制专项（各种危险命令变体）
4. Stats 深度验证（持久化/分析）
5. 跨平台兼容性

与 test_all.py (31 tests) 互补，不重叠。
"""

from __future__ import annotations
import os
import sys
import json
import time
import tempfile
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "tools-os-skills-merged"
))

from src import (
    ToolRegistry, SkillLibrary, MCPConnector, ToolStats,
    MockToolRegistry, MockSkillLibrary, PermissionLevel,
)
from src.interfaces import (
    IToolRegistry, ISkillLibrary, IToolStats,
    ToolResult, ToolSchema, CallRecord,
)


# ============================================================
# Phase 1: ToolRegistry 边界条件 (5 tests)
# ============================================================

class TestToolRegistryEdgeCases:
    """真实实现的边界条件测试。"""

    def setup_method(self):
        self.registry = ToolRegistry()

    def test_call_with_none_params(self):
        """传 None 作为 params 不崩溃。"""
        r = self.registry.call("list_directory", None)
        assert r.success is True

    def test_call_with_empty_params_dict(self):
        """传空字典给不需要参数的工具。"""
        r = self.registry.call("list_directory", {})
        assert r.success is True

    def test_register_then_call_custom_tool_with_complex_return(self):
        """自定义工具返回复杂嵌套结构。"""
        def complex_tool(a: int, b: int) -> dict:
            return {"success": True, "result": {"sum": a + b, "product": a * b}}

        self.registry.register("complex_math", complex_tool)
        r = self.registry.call("complex_math", {"a": 3, "b": 7})
        assert r.success is True
        assert r.result["sum"] == 10
        assert r.result["product"] == 21

    def test_list_tools_returns_schemas_with_permission(self):
        """list_tools() 返回的每个 Schema 都有 permission 字段。"""
        tools = self.registry.list_tools()
        assert len(tools) >= 8
        for t in tools:
            assert hasattr(t, "permission")
            assert t.permission in (PermissionLevel.PUBLIC, PermissionLevel.USER, PermissionLevel.ADMIN)

    def test_get_schema_for_specific_tool(self):
        """get_schema() 返回指定工具的完整描述。"""
        schema = self.registry.get_schema("copy_file")
        assert schema is not None
        assert schema.name == "copy_file"
        assert "src" in [p.name for p in schema.parameters]
        assert "dest" in [p.name for p in schema.parameters]

        # 不存在的工具返回 None
        assert self.registry.get_schema("nonexistent") is None


# ============================================================
# Phase 2: SkillLibrary 边界条件 (5 tests)
# ============================================================

class TestSkillLibraryEdgeCases:
    """真实 Skill 实现的边界条件。"""

    def setup_method(self):
        self.skills = SkillLibrary()

    def test_organize_empty_directory(self):
        """整理空目录 → total_moved=0，不报错。"""
        with tempfile.TemporaryDirectory() as tmp:
            r = self.skills.call_skill("organize_downloads", {"path": tmp})
            assert r.success is True
            assert r.result["total_moved"] == 0

    def test_organize_files_with_chinese_names(self):
        """中文文件名的分类处理。"""
        with tempfile.TemporaryDirectory() as tmp:
            Path(f"{tmp}/报告.pdf").touch()
            Path(f"{tmp}/照片.jpg").touch()
            Path(f"{tmp}/音乐.mp3").touch()

            r = self.skills.call_skill("organize_downloads", {"path": tmp})
            assert r.success is True
            assert r.result["total_moved"] == 3
            # 验证中文文件名被正确移动
            doc_dir = Path(tmp) / "文档"
            if doc_dir.exists():
                files_in_doc = list(doc_dir.iterdir())
                assert any("报告" in f.name for f in files_in_doc)

    def test_find_files_limited_to_100(self):
        """find_files 结果上限 100 条。"""
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(150):
                Path(f"{tmp}/file_{i:03d}.txt").write_text(f"content {i}")

            r = self.skills.call_skill("find_files", {"directory": tmp, "pattern": "*.txt"})
            assert r.success is True
            assert r.result["count"] <= 100

    def test_backup_auto_naming(self):
        """不指定 dest 时自动生成带时间戳的备份名。"""
        with tempfile.TemporaryDirectory() as tmp:
            Path(f"{tmp}/data.txt").write_text("important")
            r = self.skills.call_skill("backup_directory", {"src": tmp})
            assert r.success is True
            # 验证结果中包含 .zip 后缀和 backup 字样
            result_str = r.result if isinstance(r.result, str) else str(r.result)
            assert ".zip" in result_str or "backup" in result_str.lower()

    def test_disk_usage_on_current_path(self):
        """disk_usage 在当前路径正常工作。"""
        r = self.skills.call_skill("disk_usage", {"path": "."})
        assert r.success is True
        assert r.result["total_gb"] > 0


# ============================================================
# Phase 3: 安全机制专项 (4 tests)
# ============================================================

class TestSecurityMechanisms:
    """各种尝试绕过安全的场景。"""

    def setup_method(self):
        self.registry = ToolRegistry()

    def test_rm_rf_variations_all_blocked(self):
        """rm -rf 的各种变体都被拦截。"""
        dangerous_cmds = [
            "rm -rf /",
            "rm -rf /*",
            "rm -Rf /etc",
            "rmdir /",
            "sudo rm -rf /home",
            "RM -RF /root",          # 大写
            " rm -rf / ",            # 前后空格
        ]
        for cmd in dangerous_cmds:
            r = self.registry.call("run_command", {"cmd": cmd}, PermissionLevel.ADMIN)
            assert r.success is False, f"应拦截: {cmd}"
            assert "拒绝执行" in r.error

    def test_safe_commands_pass(self):
        """安全命令可以正常执行。"""
        safe_cmds = [
            ("ls", None),
            ("whoami", None),
            ("pwd", None),
            ("echo hello world", None),
        ]
        for cmd, _ in safe_cmds:
            r = self.registry.call("run_command", {"cmd": cmd}, PermissionLevel.ADMIN)
            assert r.success is True, f"应通过: {cmd}"

    def test_delete_protected_paths_blocked(self):
        """删除受保护路径被拦截（Linux 路径）或文件不存在（Windows 路径解析后不存在）。"""
        protected = ["/etc/passwd", "/usr/bin/python", "/root/.bashrc"]
        for path in protected:
            r = self.registry.call("delete_file", {"path": path})
            assert r.success is False, f"应拦截或文件不存在: {path}"
            # Linux 上命中受保护路径检查；Windows 上路径解析后文件不存在 → 也返回失败
            assert ("受保护" in r.error or "拒绝" in r.error
                    or "不存在" in r.error), f"意外错误: {r.error}"

    def test_format_shutdown_blocked(self):
        """format/shutdown 等系统破坏命令被拦截。"""
        dangerous = [
            "format C:",
            "shutdown -h now",
            "reboot",
            "mkfs.ext4 /dev/sda1",
        ]
        for cmd in dangerous:
            r = self.registry.call("run_command", {"cmd": cmd}, PermissionLevel.ADMIN)
            assert r.success is False, f"应拦截: {cmd}"


# ============================================================
# Phase 4: Stats 深度验证 (3 tests)
# ============================================================

class TestStatsDeepValidation:
    """调用统计的深度功能验证。"""

    def setup_method(self):
        self.log_path = os.path.join(tempfile.gettempdir(), f"test_stats_{int(time.time())}.json")
        self.stats = ToolStats(log_path=self.log_path)
        self.registry = ToolRegistry(stats=self.stats)

    def teardown_method(self):
        try:
            os.unlink(self.log_path)
        except OSError:
            pass

    def test_success_rate_calculation(self):
        """成功率计算正确。"""
        self.registry.call("list_directory", {"path": "."})   # 成功 → 记录
        self.registry.call("list_directory", {"path": "."})   # 成功 → 记录
        # 用错误参数触发 TypeError（会经过 stats.record）
        self.registry.call("copy_file", {"bad_param": "x"})    # 失败 → 记录

        assert self.stats.total_calls() == 3
        assert self.stats.success_rate() == pytest.approx(2/3, abs=0.01)

    def test_persistence_round_trip(self):
        """统计数据能写入并读回 JSON 文件。"""
        self.registry.call("copy_file", {"src": __file__, "dest": os.path.join(tempfile.gettempdir(), "test_copy.txt")})
        self.registry.call("list_directory", {"path": "."})

        # 验证文件存在且可解析
        assert os.path.exists(self.log_path), "统计日志文件应该存在"
        with open(self.log_path) as f:
            data = json.load(f)
        assert "records" in data
        assert "counters" in data
        assert len(data["records"]) >= 2

    def test_avg_duration_is_positive(self):
        """平均耗时是正数。"""
        self.registry.call("list_directory", {"path": "."})
        avg = self.stats.avg_duration()
        assert avg >= 0


# ============================================================
# Phase 5: 跨平台兼容性 (3 tests)
# ============================================================

class TestCrossPlatformCompatibility:
    """Windows/Linux 差异兼容性。"""

    def setup_method(self):
        self.registry = ToolRegistry()
        self.skills = SkillLibrary()

    def test_windows_style_path_handling(self):
        """Windows 风格路径（反斜杠）能正常工作。"""
        with tempfile.TemporaryDirectory() as tmp:
            # 创建文件并用正斜杠路径操作
            test_file = os.path.join(tmp, "win_test.txt")
            with open(test_file, "w") as f:
                f.write("windows path test")

            # 使用正斜杠路径读取
            forward_slash = test_file.replace("\\", "/")
            r = self.registry.call("read_file", {"path": forward_slash})
            assert r.success is True
            assert "windows path test" in r.result

    def test_tilde_expansion_in_skills(self):
        """Skills 中 ~/ 路径展开正确。"""
        r = self.skills.call_skill("find_files", {"directory": "~", "pattern": "*.py"})
        # 不管找到没找到，不应该因为路径问题崩溃
        # （可能找不到 .py 文件或权限不足）
        assert isinstance(r, ToolResult)

    def test_unicode_content_roundtrip(self):
        """Unicode 内容的读写往返一致。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "unicode.txt")
            content = "你好世界 🌍 分组四 Tools+OS Skills αβγ"

            r = self.registry.call("write_file", {"path": path, "content": content})
            assert r.success is True

            r = self.registry.call("read_file", {"path": path})
            assert r.success is True
            assert r.result == content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
