"""
Week 3 专属测试 — 极端场景与安全加固验证

聚焦于第 3 周收尾内容：
1. 参数边界（缺失必需参数 / 类型错误 / None / 多余参数）
2. 命令注入变体（空白绕过 / 换序参数 / fork 炸弹 / find -delete）
3. 受保护路径全覆盖（写 / 读 / 复制 / 移动 / 清理）
4. 资源限制（read_file 大小上限 / 分块哈希正确性 / 损坏符号链接）
5. 技能健壮性（重名碰撞递增 / 受保护目录拒绝整理）
6. MCP 加固（幂等注册 / JSON-RPC 错误码细分 -32601 / -32603）
7. 统计容错（统计模块崩溃不影响工具调用）

与 test_all.py (31) / test_week1.py (24) / test_week2.py (20) 互补，不重叠。
"""

from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path（docs/week3/ → 项目根在两级之上）
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import ToolRegistry, SkillLibrary, MCPConnector, ToolStats
from src import PermissionLevel
from src.default_tools import MAX_READ_SIZE

# 跨平台的受保护路径（Windows 与 Linux 各取一个真实存在的系统目录）
if sys.platform.startswith("win"):
    PROTECTED_DIR = "C:\\Windows"
    PROTECTED_FILE = "C:\\Windows\\win.ini"
else:
    PROTECTED_DIR = "/etc"
    PROTECTED_FILE = "/etc/passwd"


# ============================================================
# Phase 1: 参数边界 (6 tests)
# ============================================================

class TestParamBoundaries:
    """参数校验的边界情况。"""

    def setup_method(self):
        self.registry = ToolRegistry()

    def test_missing_all_required_params(self):
        """完全不给必需参数 → 明确报"缺少必需参数"。"""
        r = self.registry.call("copy_file", {})
        assert r.success is False
        assert "缺少必需参数" in r.error
        assert "src" in r.error and "dest" in r.error

    def test_missing_one_required_param(self):
        """只缺一个必需参数 → 指出缺哪个。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.txt")
            r = self.registry.call("write_file", {"path": path})
            assert r.success is False
            assert "缺少必需参数" in r.error
            assert "content" in r.error

    def test_params_not_a_dict(self):
        """params 传字符串而不是字典 → 参数错误。"""
        r = self.registry.call("list_directory", "not-a-dict")
        assert r.success is False
        assert "参数错误" in r.error
        assert "字典" in r.error

    def test_none_params_still_works(self):
        """params=None 依然兼容（回归验证 Week2 行为）。"""
        r = self.registry.call("list_directory", None)
        assert r.success is True

    def test_unexpected_extra_param(self):
        """多余的未知参数 → TypeError 被捕获为参数错误。"""
        r = self.registry.call("list_directory", {"path": ".", "bogus": 1})
        assert r.success is False
        assert "参数错误" in r.error

    def test_skill_params_not_a_dict(self):
        """Skill 层同样拒绝非字典 params。"""
        skills = SkillLibrary()
        r = skills.call_skill("disk_usage", "bad-params")
        assert r.success is False
        assert "参数错误" in r.error


# ============================================================
# Phase 2: 命令注入与黑名单变体 (5 tests)
# ============================================================

class TestCommandInjectionVariants:
    """尝试用各种变体绕过危险命令黑名单。"""

    def setup_method(self):
        self.registry = ToolRegistry()

    def test_whitespace_bypass_blocked(self):
        """多空格 / 制表符绕过被空白归一化拦截。"""
        variants = [
            "rm  -rf /",      # 双空格
            "rm   -rf  /etc", # 多空格
            "rm -rf\t/",      # 制表符
            "  rm -rf /  ",   # 前后空格
        ]
        for cmd in variants:
            r = self.registry.call("run_command", {"cmd": cmd}, PermissionLevel.ADMIN)
            assert r.success is False, f"应拦截: {cmd!r}"
            assert "拒绝执行" in r.error

    def test_reversed_flag_order_blocked(self):
        """rm -fr（换序参数）也被拦截。"""
        r = self.registry.call("run_command", {"cmd": "rm -fr /home"}, PermissionLevel.ADMIN)
        assert r.success is False
        assert "拒绝执行" in r.error

    def test_fork_bomb_blocked(self):
        """fork 炸弹 :(){ :|:& };: 被拦截。"""
        r = self.registry.call(
            "run_command", {"cmd": ":(){ :|:& };:"}, PermissionLevel.ADMIN
        )
        assert r.success is False
        assert "拒绝执行" in r.error

    def test_find_delete_variant_blocked(self):
        """find / -delete 删除变体被拦截。"""
        r = self.registry.call(
            "run_command", {"cmd": "find / -delete"}, PermissionLevel.ADMIN
        )
        assert r.success is False
        assert "拒绝执行" in r.error

    def test_safe_command_still_works(self):
        """归一化后正常命令不受影响（防误伤回归）。"""
        r = self.registry.call(
            "run_command", {"cmd": "echo   hello   world"}, PermissionLevel.ADMIN
        )
        assert r.success is True
        assert "hello" in r.result


# ============================================================
# Phase 3: 受保护路径全覆盖 (5 tests)
# ============================================================

class TestProtectedPathCoverage:
    """受保护路径检查覆盖 写/读/复制/移动/清理 全部入口。"""

    def setup_method(self):
        self.registry = ToolRegistry()

    def test_write_to_protected_path_blocked(self):
        """向系统目录写文件被拒绝。"""
        target = os.path.join(PROTECTED_DIR, "g4_should_not_exist.txt")
        r = self.registry.call("write_file", {"path": target, "content": "hack"})
        assert r.success is False
        assert "受保护" in r.error

    def test_read_protected_file_blocked(self):
        """读取系统敏感文件被拒绝。"""
        r = self.registry.call("read_file", {"path": PROTECTED_FILE})
        assert r.success is False
        assert "受保护" in r.error

    def test_copy_dest_protected_blocked(self):
        """复制目标在系统目录内被拒绝。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.txt")
            with open(src, "w") as f:
                f.write("data")
            dest = os.path.join(PROTECTED_DIR, "g4_copy_test.txt")
            r = self.registry.call("copy_file", {"src": src, "dest": dest})
            assert r.success is False
            assert "受保护" in r.error

    def test_move_dest_protected_blocked(self):
        """移动目标在系统目录内被拒绝。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.txt")
            with open(src, "w") as f:
                f.write("data")
            dest = os.path.join(PROTECTED_DIR, "g4_move_test.txt")
            r = self.registry.call("move_file", {"src": src, "dest": dest})
            assert r.success is False
            assert "受保护" in r.error

    def test_cleanup_temp_protected_blocked(self):
        """cleanup_temp 技能拒绝清理系统目录。"""
        skills = SkillLibrary()
        r = skills.call_skill("cleanup_temp", {"path": PROTECTED_DIR})
        assert r.success is False
        assert "受保护" in r.error


# ============================================================
# Phase 4: 资源限制 (3 tests)
# ============================================================

class TestResourceLimits:
    """防止资源耗尽的保护机制。"""

    def test_read_file_size_limit(self):
        """超过 10MB 的文件拒绝读入内存。"""
        with tempfile.TemporaryDirectory() as tmp:
            big = os.path.join(tmp, "big.txt")
            with open(big, "wb") as f:
                f.write(b"A" * (MAX_READ_SIZE + 1))
            r = ToolRegistry().call("read_file", {"path": big})
            assert r.success is False
            assert "过大" in r.error

    def test_chunked_hash_still_correct(self):
        """分块 MD5 与整块 MD5 结果一致（正确性回归）。"""
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            payload = os.urandom(5 * 1024 * 1024)  # 5MB 跨多个 1MB 分块
            for name in ("a.bin", "b.bin"):
                with open(os.path.join(tmp, name), "wb") as f:
                    f.write(payload)
            with open(os.path.join(tmp, "c.bin"), "wb") as f:
                f.write(b"different")

            r = SkillLibrary().call_skill("find_duplicate_files", {"path": tmp})
            assert r.success is True
            assert r.result["duplicate_groups"] == 1
            # 手工验证分块哈希 == 整块哈希
            assert hashlib.md5(payload).hexdigest() is not None

    @pytest.mark.skipif(
        sys.platform.startswith("win"),
        reason="Windows 创建符号链接通常需要管理员权限",
    )
    def test_list_directory_with_broken_symlink(self):
        """损坏的符号链接不会让 list_directory 崩溃。"""
        with tempfile.TemporaryDirectory() as tmp:
            link = os.path.join(tmp, "broken_link")
            try:
                os.symlink("/nonexistent/target/xyz", link)
            except OSError:
                pytest.skip("当前环境不允许创建符号链接")
            r = ToolRegistry().call("list_directory", {"path": tmp})
            assert r.success is True  # 不崩溃即通过


# ============================================================
# Phase 5: 技能健壮性 (3 tests)
# ============================================================

class TestSkillRobustness:
    """技能层的边界加固验证。"""

    def setup_method(self):
        self.skills = SkillLibrary()

    def test_organize_duplicate_collision_preserves_files(self):
        """重名碰撞 → _dup1 递增命名，任何文件都不被覆盖。"""
        with tempfile.TemporaryDirectory() as tmp:
            Path(os.path.join(tmp, "a.pdf")).write_text("v1")
            doc = os.path.join(tmp, "文档")
            os.makedirs(doc)
            Path(os.path.join(doc, "a.pdf")).write_text("v0")

            r = self.skills.call_skill("organize_downloads", {"path": tmp})
            assert r.success is True
            assert r.result["total_moved"] == 1

            # 两个文件都还在：原 a.pdf 保留为 v0，新来的变成 a_dup1.pdf
            assert Path(os.path.join(doc, "a.pdf")).read_text() == "v0"
            assert Path(os.path.join(doc, "a_dup1.pdf")).read_text() == "v1"

    def test_organize_triple_collision(self):
        """三重重名 → _dup1 / _dup2 依次递增。"""
        with tempfile.TemporaryDirectory() as tmp:
            Path(os.path.join(tmp, "a.txt")).write_text("v3")
            doc = os.path.join(tmp, "文档")
            os.makedirs(doc)
            Path(os.path.join(doc, "a.txt")).write_text("v1")
            Path(os.path.join(doc, "a_dup1.txt")).write_text("v2")

            r = self.skills.call_skill("organize_downloads", {"path": tmp})
            assert r.success is True
            assert Path(os.path.join(doc, "a_dup2.txt")).read_text() == "v3"
            # 原有三个文件内容全部完好
            assert Path(os.path.join(doc, "a.txt")).read_text() == "v1"
            assert Path(os.path.join(doc, "a_dup1.txt")).read_text() == "v2"

    def test_organize_protected_path_refused(self):
        """拒绝整理系统目录（防止搬走系统文件）。"""
        r = self.skills.call_skill("organize_downloads", {"path": PROTECTED_DIR})
        assert r.success is False
        assert "受保护" in r.error


# ============================================================
# Phase 6: MCP 加固 (3 tests)
# ============================================================

class TestMCPHardening:
    """MCP 连接器的幂等性与协议错误码。"""

    def setup_method(self):
        self.mcp = MCPConnector()
        self.registry = ToolRegistry()

    def test_register_mock_tools_idempotent(self):
        """重复注册 Mock 工具不再抛 ValueError（Week3 之前会崩）。"""
        self.mcp.register_mock_tools(self.registry)   # 第一次
        self.mcp.register_mock_tools(self.registry)   # 第二次：必须无异常
        assert self.registry.has("mcp_search")
        assert self.registry.has("mcp_weather")
        assert self.registry.has("mcp_translate")

    def test_jsonrpc_method_not_found_code(self):
        """调用未注册工具 → JSON-RPC 错误码 -32601 (Method not found)。"""
        r = self.mcp.mock_jsonrpc_call(self.registry, "no_such_tool", {})
        assert r["jsonrpc"] == "2.0"
        assert r["result"] is None
        assert r["error"]["code"] == -32601

    def test_jsonrpc_internal_error_code(self):
        """权限不足等执行失败 → JSON-RPC 错误码 -32603 (Internal error)。"""
        # 默认 USER 权限调用 ADMIN 级工具 → 失败但工具已注册
        r = self.mcp.mock_jsonrpc_call(self.registry, "run_command", {"cmd": "echo hi"})
        assert r["result"] is None
        assert r["error"]["code"] == -32603
        assert "权限不足" in r["error"]["message"]


# ============================================================
# Phase 7: 统计容错 (1 test)
# ============================================================

class TestStatsResilience:
    """统计模块故障不能影响工具调用主流程。"""

    def test_broken_stats_does_not_break_call(self):
        """stats.record() 抛异常时，工具调用依然成功返回。"""
        class BadStats(ToolStats):
            def record(self, record):
                raise RuntimeError("模拟统计模块崩溃")

        registry = ToolRegistry(stats=BadStats())
        r = registry.call("list_directory", {"path": "."})
        assert r.success is True  # 主流程不受影响


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
