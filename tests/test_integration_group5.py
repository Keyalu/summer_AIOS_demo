"""
test_integration_group5.py — 模拟组 5（Coordinator/Security/RAG）的审计接入测试

组 5 在流水线里"审计并存储"各组输出（见《01-MCP协议调研报告》数据流）。
与组 3 不同：组 5 **不 import 我们的类**，只消费纯 JSON——
这里的 SimulatedCoordinator 刻意只用 json.loads / dict 操作，
等价于组 5 的 check_json 接入的最小验证。

覆盖场景：
1. ToolResult JSON 结构校验（success/result 与 success/error 互斥）
2. 用 inputSchema 校验调用参数（check_json 的参数合法性近似）
3. 解析 stats.json 审计日志（records + counters + updated 三段结构）
4. 审计时间线（明细记录含 time 时间戳，可按序重放）
5. 安全审计（权限不足/危险命令的 fail 事件在日志中可追）
6. 工具能力清单内省（RAG：从 inputSchema 生成工具知识条目）
"""

import json
import tempfile
from pathlib import Path

import pytest

from src import BufferedToolStats, PermissionLevel, SkillLibrary, ToolRegistry


class SimulatedCoordinator:
    """模拟组 5 的 Coordinator —— 只吃 JSON，不 import 分组四的任何类。

    模拟三个动作：
    - check_result: 校验 ToolResult JSON 的结构
    - check_params: 用 inputSchema 校验调用参数
    - ingest_audit: 吸收一份 stats.json 审计日志
    """

    @staticmethod
    def check_result(raw: str) -> dict:
        d = json.loads(raw)
        assert isinstance(d, dict) and "success" in d, "缺少 success 字段"
        if d["success"]:
            assert "result" in d, "成功结果必须带 result"
            assert "error" not in d, "成功结果不应带 error"
        else:
            assert "error" in d, "失败结果必须带 error"
            assert "result" not in d, "失败结果不应带 result"
        return d

    @staticmethod
    def check_params(schema_dict: dict, params: dict) -> list[str]:
        """用 MCP inputSchema 校验参数，返回缺失的必需字段列表。"""
        required = schema_dict["inputSchema"].get("required", [])
        return [k for k in required if k not in params]

    @staticmethod
    def ingest_audit(raw: str) -> dict:
        d = json.loads(raw)
        assert "records" in d and "counters" in d, "审计日志缺 records/counters"
        for rec in d["records"]:
            assert "time" in rec and "tool" in rec and "success" in rec
        return d

    @staticmethod
    def security_events(audit: dict) -> list[dict]:
        """Security 视角：从审计日志里捞出失败事件。"""
        return [r for r in audit["records"] if not r["success"]]

    @staticmethod
    def knowledge_entries(tool_schemas: list[dict]) -> list[dict]:
        """RAG 视角：把工具清单转成知识库条目。"""
        return [
            {
                "name": s["name"],
                "description": s["description"],
                "permission": s["permission"],
                "params": list(s["inputSchema"]["properties"].keys()),
            }
            for s in tool_schemas
        ]


# ============================================================
# 测试
# ============================================================

class TestGroup5Integration:
    """组 5 纯 JSON 消费方式的端到端验证。"""

    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="g5_audit_"))
        self.stats = BufferedToolStats(log_path=str(self.tmp / "stats.json"))
        self.registry = ToolRegistry(stats=self.stats)
        self.skills = SkillLibrary(registry=self.registry)

    # ---- 1. ToolResult JSON 结构 ----

    def test_01_result_json_structure(self):
        """成功与失败的 ToolResult JSON 都能通过 check_result 校验。"""
        ok = self.registry.call("list_directory", {"path": str(self.tmp)})
        fail = self.registry.call("write_file", {"path": "x.txt"})  # 缺 content

        coord = SimulatedCoordinator()
        d_ok = coord.check_result(json.dumps(ok.to_dict(), ensure_ascii=False))
        d_fail = coord.check_result(json.dumps(fail.to_dict(), ensure_ascii=False))

        assert d_ok["success"] is True
        assert d_fail["success"] is False
        assert "缺少必需参数" in d_fail["error"]

    # ---- 2. inputSchema 校验调用参数 ----

    def test_02_check_params_with_inputschema(self):
        """组 5 的 check_json 可以用我们的 inputSchema 验组 3 的参数。"""
        schema = next(s for s in self.registry.list_tools() if s.name == "write_file")
        sd = schema.to_dict()

        missing = SimulatedCoordinator.check_params(sd, {"path": "x.txt"})
        assert missing == ["content"]

        assert SimulatedCoordinator.check_params(sd, {"path": "x", "content": "hi"}) == []

    # ---- 3. stats.json 审计日志结构 ----

    def test_03_audit_log_structure(self):
        """stats.json 含 records/counters/updated，明细字段齐全。"""
        self.registry.call("list_directory", {"path": str(self.tmp)})
        self.registry.call("write_file", {"path": "x.txt"})  # 失败
        self.stats.flush()

        audit = SimulatedCoordinator.ingest_audit(
            (self.tmp / "stats.json").read_text(encoding="utf-8")
        )
        assert audit["counters"]["list_directory"]["success"] == 1
        assert audit["counters"]["write_file"]["fail"] == 1
        assert audit["updated"]

    # ---- 4. 审计时间线 ----

    def test_04_audit_timeline_replay(self):
        """明细记录带时间戳且有序，组 5 可重放整个任务过程。"""
        self.registry.call("list_directory", {"path": str(self.tmp)})
        self.registry.call("list_directory", {"path": str(self.tmp)})
        self.stats.flush()

        audit = SimulatedCoordinator.ingest_audit(
            (self.tmp / "stats.json").read_text(encoding="utf-8")
        )
        times = [r["time"] for r in audit["records"] if r["tool"] == "list_directory"]
        assert len(times) == 2 and times == sorted(times)

    # ---- 5. 安全审计事件 ----

    def test_05_security_events_visible(self):
        """失败事件可审计（参数错误/执行异常）。

        契约注意：权限拦截发生在统计记录之前（调度层拒绝、不产生调用记录，
        与组 3 的 test_integration 固化的契约一致），所以权限事件不进审计日志。
        组 5 的 Security 如需权限拦截事件，走"推模式 callback"（见行动方案）。
        """
        self.registry.call("write_file", {"path": "x.txt"})          # 参数错误 → 入统计
        r = self.registry.call("run_command", {"cmd": "rm -rf /"})   # 权限拦截 → 不入统计
        self.stats.flush()

        assert not r.success  # 拦截确实发生了

        audit = SimulatedCoordinator.ingest_audit(
            (self.tmp / "stats.json").read_text(encoding="utf-8")
        )
        events = SimulatedCoordinator.security_events(audit)
        assert len(events) == 1
        assert events[0]["tool"] == "write_file"
        assert "缺少必需参数" in events[0]["error"]
        # 契约行为：权限拦截不留调用记录（联调时要向组 5 明确说明）
        assert all(ev["tool"] != "run_command" for ev in events)

    # ---- 6. RAG 工具知识条目 ----

    def test_06_rag_knowledge_entries(self):
        """组 5 的 RAG 能从纯 JSON 工具清单构建知识条目。"""
        schemas = [s.to_dict() for s in self.registry.list_tools()]
        entries = SimulatedCoordinator.knowledge_entries(schemas)

        assert len(entries) == len(schemas) >= 8
        by_name = {e["name"]: e for e in entries}
        assert by_name["run_command"]["permission"] == "admin"
        assert "cmd" in by_name["run_command"]["params"]
