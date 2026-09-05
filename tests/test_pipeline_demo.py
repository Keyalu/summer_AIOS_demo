"""pipeline_demo（组3/组5 联调替身）的契约测试。

验证三件事：
1. 组1/组2 替身产出的 intent/plan 是合法 JSON 结构且动作可追溯；
2. 组3 替身在 Mock 与真实实现上行为一致（Mock 换真实零改动）；
3. 组5 替身只吃 JSON 就能完成审计并核验账目一致性。
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pipeline_demo import (  # noqa: E402
    HostAgentStandIn, TaskPlannerStandIn, AppAgentStandIn, CoordinatorStandIn,
)
from src.tool_registry import ToolRegistry  # noqa: E402
from src.mock_registry import MockToolRegistry  # noqa: E402
from src.skill_library import SkillLibrary  # noqa: E402
from src.stats import ToolStats  # noqa: E402
from src.interfaces import PermissionLevel  # noqa: E402

U = PermissionLevel.USER


def _sandbox() -> str:
    d = tempfile.mkdtemp(prefix="pipe_")
    with open(os.path.join(d, "a.txt"), "w", encoding="utf-8") as f:
        f.write("hello")
    return d


# ---------------- 组1 / 组2 ----------------

def test_intent_shape_and_goal_extraction():
    intent = HostAgentStandIn().parse("帮我整理一下顺便查重，最后备个份", _sandbox())
    assert intent["intent_id"] and intent["confidence"] > 0.5
    actions = [g["action"] for g in intent["goals"]]
    assert actions == ["organize", "find_duplicates", "backup"]


def test_plan_shape_and_admin_step():
    intent = HostAgentStandIn().parse("整理一下", _sandbox())
    plan = TaskPlannerStandIn().plan(intent)
    assert plan["based_on"] == intent["intent_id"]
    assert plan["steps"], "计划不能为空"
    assert plan["steps"][-1]["requires_admin"] is True  # 收尾命令演示提权


# ---------------- 组3：Mock 换真实，行为一致 ----------------

def _run_plan_on(registry) -> dict:
    from src.mock_skills import MockSkillLibrary
    registry_is_mock = isinstance(registry, MockToolRegistry)
    skills = MockSkillLibrary() if registry_is_mock else SkillLibrary(registry=registry)
    intent = HostAgentStandIn().parse("整理一下", _sandbox())
    plan = TaskPlannerStandIn().plan(intent)
    return AppAgentStandIn(registry, skills, level=U).execute_plan(plan)


def test_agent_real_vs_mock_same_contract():
    real = _run_plan_on(ToolRegistry())
    mock = _run_plan_on(MockToolRegistry())
    # 同一计划 → 相同步骤数、相同键结构；差异只在返回值内容（真实 vs [Mock]）
    assert real["summary"]["total"] == mock["summary"]["total"] > 0
    assert set(real["steps"][0].keys()) == set(mock["steps"][0].keys())
    assert mock["steps"][0]["tool_result"]["success"] is True  # Mock 也返回 ToolResult 形状


def test_escalation_flow_recorded():
    registry = ToolRegistry()
    intent = HostAgentStandIn().parse("整理一下", _sandbox())
    plan = TaskPlannerStandIn().plan(intent)
    agent = AppAgentStandIn(registry, SkillLibrary(registry=registry), level=U)
    session = agent.execute_plan(plan)
    assert session["summary"]["fail"] == 0
    assert any(e["to"] == "admin" and e["user_confirmed"]
               for e in session["escalations"])  # 提权流真实发生了
    admin_step = [s for s in session["steps"] if s["name"] == "run_command"][0]
    assert admin_step["level_used"] == "admin" and admin_step["tool_result"]["success"]


def test_selfheal_on_typo():
    agent = AppAgentStandIn(ToolRegistry(), level=U)
    r = agent.try_call_with_selfheal("list_directorry", {"path": _sandbox()})
    assert r.success and agent.self_healed[-1]["fixed"] == "list_directory"


# ---------------- 组5：只吃 JSON ----------------

def test_coordinator_pure_json_audit(tmp_path):
    stats_path = os.path.join(tmp_path, "stats.json")
    log_path = os.path.join(tmp_path, "session_log.json")
    schemas_path = os.path.join(tmp_path, "schemas.json")

    stats = ToolStats(log_path=stats_path)
    registry = ToolRegistry(stats=stats)
    registry.call("list_directory", {"path": _sandbox()}, U)
    registry.call("run_command", {"cmd": "echo ok"}, PermissionLevel.ADMIN)
    with open(schemas_path, "w", encoding="utf-8") as f:
        json.dump([s.to_dict() for s in registry.list_tools()], f, ensure_ascii=False)
    session = {"summary": {"total": 2, "success": 2, "fail": 0},
               "steps": [{"kind": "tool", "name": "list_directory",
                          "tool_result": {"success": True, "result": []}},
                         {"kind": "tool", "name": "run_command",
                          "tool_result": {"success": True, "result": "ok"}}]}
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False)

    c = CoordinatorStandIn(schemas_path)
    assert c.check_params("copy_file", {"src": "a"}) == ["缺少必需参数 dest"]
    assert c.check_result({"success": False}) == ["失败结果必须带 error"]

    report = c.ingest_audit(stats_path, log_path)
    assert report["verdict"] == "PASS"
    assert report["totals"]["calls"] >= 2
    assert report["consistency"]["consistent"] is True
