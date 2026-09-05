"""
test_integration.py — 模拟组 3（AppAgent）的端到端集成测试

目的：在真正的组 3 接入之前，先用"假想 Agent"走通完整调用回路，
提前暴露契约层面的问题。这里的 SimulatedAgent 只使用
《02-组间集成指南.md》中发布的公开契约——组 3 能用的，测试就能过。

覆盖场景：
1. Agent 整理下载目录（list → organize → 验证）完整任务回路
2. 权限提权流（USER 被拒 → ADMIN 放行）
3. 错误自愈（工具名写错 → 读 error 前缀 → list_tools 纠正）
4. Schema 内省驱动（Agent 从 list_tools 动态构建工具菜单）
5. Mock 无缝替换（同一份 Agent 代码，Mock/真实实现都能跑）
6. 统计闭环（任务结束后 Agent 读取成功率做汇报）
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from src import (
    MCPConnector, MockSkillLibrary, MockToolRegistry, PermissionLevel,
    SkillLibrary, ToolRegistry, ToolStats,
)


class SimulatedAgent:
    """模拟组 3 的 AppAgent——只通过公开契约消费分组四模块。

    这是组 3 真实代码的最小近似：接收自然语言意图（这里简化为
    结构化的"计划"），逐步调用工具，检查每一步结果，失败时按
    error 前缀决策。
    """

    def __init__(self, registry, skills=None, level=PermissionLevel.USER):
        self.registry = registry
        self.skills = skills
        self.level = level
        self.log: list[str] = []

    def do(self, tool: str, params: dict | None = None):
        """调用一个工具并记录结果。"""
        r = self.registry.call(tool, params or {}, self.level)
        self.log.append(f"{tool} → {'OK' if r.success else 'FAIL: ' + (r.error or '')}")
        return r

    def escalate_and_retry(self, tool: str, params: dict | None = None):
        """权限不足时模拟"请求用户确认后提权"。"""
        r = self.registry.call(tool, params or {}, self.level)
        if not r.success and r.error and r.error.startswith("权限不足"):
            self.log.append("请求用户确认 → 提权 ADMIN")
            old = self.level
            self.level = PermissionLevel.ADMIN
            r = self.registry.call(tool, params or {}, self.level)
            self.level = old
        return r

    def find_tool(self, keyword: str) -> str | None:
        """工具名不确定时，从 list_tools 里模糊匹配（组 3 纠错路径）。"""
        for schema in self.registry.list_tools():
            if keyword in schema.name:
                return schema.name
        return None

    def tool_menu(self) -> list[str]:
        """Schema 内省：动态构建可用工具清单（可喂给 LLM function-calling）。"""
        return [s.to_dict()["name"] for s in self.registry.list_tools()]


# ==============================================================
# 1. 完整任务回路：整理下载目录
# ==============================================================
class TestAgentOrganizeFlow:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="itg_dl_"))
        (self.tmp / "报告.pdf").write_text("pdf")
        (self.tmp / "照片.png").write_bytes(b"\x89PNG")
        (self.tmp / "歌.mp3").write_bytes(b"ID3")
        (self.tmp / "脚本.py").write_text("print(1)")

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_task_loop(self):
        """Agent 完成任务：查看目录 → 整理 → 验证结果。"""
        agent = SimulatedAgent(ToolRegistry(), SkillLibrary())

        # Step 1: Agent 先了解环境（PUBLIC 工具，USER 级别也能调）
        r = agent.do("list_directory", {"path": str(self.tmp)})
        assert r.success and r.result["count"] == 4

        # Step 2: Agent 调用技能完成整理
        r = agent.skills.call_skill("organize_downloads", {"path": str(self.tmp)})
        assert r.success and r.result["total_moved"] == 4

        # Step 3: Agent 验证成果
        r = agent.do("list_directory", {"path": str(self.tmp / "文档")})
        assert r.success and r.result["count"] == 1
        assert (self.tmp / "文档" / "报告.pdf").exists()
        assert (self.tmp / "图片" / "照片.png").exists()
        assert (self.tmp / "代码" / "脚本.py").exists()

        # 全程有审计日志（agent.do 记录 Registry 调用，共 2 次；
        # 技能调用走 skills.call_skill，不经 agent.do，组 3 集成时应注意）
        assert len(agent.log) == 2


# ==============================================================
# 2. 权限提权流
# ==============================================================
class TestAgentPermissionFlow:
    def test_escalation_on_denied(self):
        """USER 执行命令被拒 → Agent 提权 ADMIN 重试 → 成功。"""
        agent = SimulatedAgent(ToolRegistry())

        r = agent.do("run_command", {"cmd": "echo hello"})
        assert not r.success and "权限不足" in r.error

        r = agent.escalate_and_retry("run_command", {"cmd": "echo hello"})
        assert r.success and "hello" in r.result
        assert any("提权" in entry for entry in agent.log)

    def test_escalation_still_blocked_by_blacklist(self):
        """即使提权到 ADMIN，危险命令依然被安全层拦截（组 3 必须知道这点）。"""
        agent = SimulatedAgent(ToolRegistry())
        r = agent.escalate_and_retry("run_command", {"cmd": "rm -rf /"})
        assert not r.success and "拒绝执行" in r.error


# ==============================================================
# 3. 错误自愈
# ==============================================================
class TestAgentErrorRecovery:
    def test_recovers_from_wrong_tool_name(self):
        """工具名写错 → error 前缀"工具未注册" → list_tools 找到正确名字重试。"""
        agent = SimulatedAgent(ToolRegistry())

        r = agent.do("list_dir", {"path": "~"})        # 组 3 记错了名字
        assert not r.success and r.error.startswith("工具未注册")

        # Agent 的自愈逻辑：按前缀判断可恢复，模糊搜索正确工具名
        correct = agent.find_tool("list")
        assert correct == "list_directory"
        r = agent.do(correct, {"path": "~"})
        assert r.success

    def test_param_error_is_actionable(self):
        """缺必需参数 → error 前缀"参数错误"并指明缺哪个，Agent 可补参重试。"""
        agent = SimulatedAgent(ToolRegistry())
        r = agent.do("copy_file", {"src": "/tmp/a.txt"})
        assert not r.success and r.error.startswith("参数错误")
        assert "dest" in r.error                       # 明确指出缺 dest


# ==============================================================
# 4. Schema 内省驱动
# ==============================================================
class TestSchemaDrivenAgent:
    def test_menu_contains_all_default_tools(self):
        """Agent 启动时内省工具菜单：8 个默认工具全在。"""
        agent = SimulatedAgent(ToolRegistry())
        menu = agent.tool_menu()
        assert len(menu) == 8
        for name in ("copy_file", "move_file", "delete_file", "create_folder",
                     "list_directory", "read_file", "write_file", "run_command"):
            assert name in menu

    def test_schema_compatible_with_function_calling(self):
        """schema.to_dict() 提供 LLM function-calling 所需的字段。"""
        for s in ToolRegistry().list_tools():
            d = s.to_dict()
            assert d["name"] and d["description"]
            assert "inputSchema" in d
            assert "required" in d["inputSchema"]


# ==============================================================
# 5. Mock 无缝替换（组 3 并行开发的关键承诺）
# ==============================================================
class TestMockSwap:
    def _agent_flow(self, registry, skills):
        """同一段 Agent 业务代码，分别跑在真实实现和 Mock 上。"""
        agent = SimulatedAgent(registry, skills)
        names = agent.tool_menu()
        assert len(names) >= 1
        r = agent.do(names[0], {})
        return agent, r

    def test_same_code_runs_on_real_and_mock(self):
        real_agent, real_r = self._agent_flow(ToolRegistry(), SkillLibrary())
        mock_agent, mock_r = self._agent_flow(MockToolRegistry(), MockSkillLibrary())

        # 两侧都走完流程不崩溃；Mock 结果带 [Mock] 标记可供组 3 识别
        assert mock_r.success
        assert "Mock" in str(mock_r.result) or "mock" in str(mock_r.result).lower()


# ==============================================================
# 6. 统计闭环
# ==============================================================
class TestStatsLoop:
    def test_agent_reports_success_rate(self):
        """任务结束后 Agent 从统计模块读取成功率，向用户汇报。"""
        stats = ToolStats()
        registry = ToolRegistry(stats=stats)
        agent = SimulatedAgent(registry)

        agent.do("list_directory", {"path": "~"})          # 成功
        agent.do("list_directory", {"path": "~"})          # 成功
        agent.do("list_directory", {"path": "/no/such/dir"})  # 执行但失败（有记录）

        # 注意：未注册工具的调用在调度层就被拒，不进入执行统计（契约行为）
        assert stats.total_calls() == 3
        overall = stats.tool_stats("list_directory")
        assert overall["success"] == 2
        rate = stats.success_rate("list_directory")
        assert rate == pytest.approx(2 / 3)


# ==============================================================
# 7. MCP 通道冒烟（组 3 若走 JSON-RPC 协议）
# ==============================================================
class TestMCPChannel:
    def test_jsonrpc_roundtrip(self):
        registry = ToolRegistry()
        mcp = MCPConnector()
        mcp.register_mock_tools(registry)

        resp = mcp.mock_jsonrpc_call(registry, "mcp_search", {"query": "UFO"})
        assert resp["jsonrpc"] == "2.0" and resp["error"] is None
        assert resp["result"] is not None and "id" in resp

        resp = mcp.mock_jsonrpc_call(registry, "mcp_no_such", {})
        assert resp["error"]["code"] == -32601            # 方法不存在

    def test_register_mock_tools_idempotent_for_integration(self):
        """组 3 集成时可能重复初始化——必须幂等不崩。"""
        registry = ToolRegistry()
        mcp = MCPConnector()
        mcp.register_mock_tools(registry)
        mcp.register_mock_tools(registry)                 # 第二次也不炸
        assert registry.has("mcp_search")
