"""run_demo.py — 五组全链路演示编排器（唯一入口）。

用户话语 → 组1 解析 → 组2 规划 → 组3 执行（真实组4 在中间）→ 组5 审计。
所有中间产物（intent/plan/schemas/session_log/stats/audit_report）
落盘到 pipeline_demo/out/，与真实组间交互"只传 JSON"的方式一致。

运行：python pipeline_demo/run_demo.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

from pipeline_demo import (                       # noqa: E402
    HostAgentStandIn, TaskPlannerStandIn, AppAgentStandIn, CoordinatorStandIn,
)
from src.tool_registry import ToolRegistry        # noqa: E402  组4 真实模块
from src.skill_library import SkillLibrary        # noqa: E402
from src.mcp_connector import MCPConnector        # noqa: E402
from src.stats import ToolStats                   # noqa: E402
from src.interfaces import PermissionLevel        # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

USER_TEXT = ("帮我把「demo_task」文件夹里的文件整理一下，"
             "顺便看看有没有重复文件，最后备个份")


def _banner(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def _save(out: str, name: str, obj) -> str:
    path = os.path.join(out, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def prepare_sandbox(out: str = OUT) -> str:
    """造一个有重复文件、多类型的沙箱目录，让整理/查重有东西可干。"""
    sandbox = os.path.join(out, "demo_task")
    shutil.rmtree(sandbox, ignore_errors=True)
    os.makedirs(os.path.join(sandbox, "附件"), exist_ok=True)
    files = {
        "报告.docx": "A" * 300, "报告副本.docx": "A" * 300,      # 一对重复
        "照片.jpg": "B" * 800, "notes.md": "# 笔记\n内容",       # 不同内容
        "script.py": "print('hi')", "data.csv": "x,y\n1,2",
    }
    for name, content in files.items():
        with open(os.path.join(sandbox, name), "w", encoding="utf-8") as f:
            f.write(content)
    with open(os.path.join(sandbox, "附件", "报告.docx"), "w", encoding="utf-8") as f:
        f.write("A" * 300)                                       # 与根目录一对重复
    return sandbox


def run_pipeline(user_text: str | None = None, out: str = OUT,
                 verbose: bool = False) -> dict:
    """跑通 组1→组2→组3(真实组4)→组5，返回全部中间产物。

    供 run_demo.main() 控制台演出（verbose=True），也供 GUI 服务器
    /api/pipeline 调用（verbose=False，产物直接随响应返回）。
    """
    user_text = user_text or USER_TEXT
    os.makedirs(out, exist_ok=True)
    sandbox = prepare_sandbox(out)
    P = (lambda s: print(s)) if verbose else (lambda s: None)

    # ---------------- 组1 HostAgent ----------------
    P(f"\n[组1] HostAgent — 解析意图")
    intent = HostAgentStandIn().parse(user_text, default_target=sandbox)
    P(f"  intent_id: {intent['intent_id']}  置信度: {intent['confidence']}")
    for g in intent["goals"]:
        P(f"  • {g['action']:<18} {g['description']}")
    _save(out, "intent.json", intent)

    # ---------------- 组2 TaskPlanner ----------------
    P(f"\n[组2] TaskPlanner — 规划步骤")
    plan = TaskPlannerStandIn().plan(intent)
    for s in plan["steps"]:
        admin = "（需 ADMIN）" if s["requires_admin"] else ""
        P(f"  步骤{s['step']}: [{s['kind']}] {s['name']} {admin} — {s['description']}")
    _save(out, "plan.json", plan)

    # ---------------- 组4 模块栈（真实）+ 组3 执行 ----------------
    P(f"\n[组3] AppAgent — 执行计划（组4 真实模块在中间）")
    stats_path = os.path.join(out, "stats.json")
    if os.path.exists(stats_path):
        os.remove(stats_path)
    stats = ToolStats(log_path=stats_path)
    registry = ToolRegistry(stats=stats)
    skills = SkillLibrary(registry=registry)
    MCPConnector().register_mock_tools(registry)      # 幂等，演示 MCP 注入

    agent = AppAgentStandIn(registry, skills, level=PermissionLevel.USER)
    P(f"  组3 开机自检：工具菜单 = {len(agent.tool_menu())} 个"
      f"（8 OS 工具 + 8 技能 + 3 MCP Mock 中的工具部分）")

    # 中立快照：把工具 schema 导出为纯 JSON，供组5 校验用
    _save(out, "schemas.json", [s.to_dict() for s in registry.list_tools()])

    session = agent.execute_plan(plan, verbose=verbose)
    session_path = _save(out, "session_log.json", session)

    # 组3 边界演示：工具名写错 → error 前缀 → list_tools 纠错
    P("  —— 边界演示：工具名写错的 self-heal ——")
    r = agent.try_call_with_selfheal("list_directorry", {"path": sandbox})
    P(f"    list_directorry → {'成功纠错为 ' + agent.self_healed[-1]['fixed'] if agent.self_healed else '未触发'}"
      f" | success={r.success}")

    # ---------------- 组5 Coordinator ----------------
    P(f"\n[组5] Coordinator — 纯 JSON 审计（不 import 组4 任何代码）")
    coordinator = CoordinatorStandIn(os.path.join(out, "schemas.json"))

    # 抽查：结构校验 + 参数校验
    sample = session["steps"][0]["tool_result"]
    struct_errs = coordinator.check_result(sample)
    param_errs = coordinator.check_params("copy_file", {"src": "a"})  # 故意缺 dest
    P(f"  抽查 ToolResult 结构：{'通过' if not struct_errs else struct_errs}")
    P(f"  抽查参数校验（copy_file 缺 dest）：{param_errs}")

    report = coordinator.ingest_audit(stats_path, session_path)
    _save(out, "audit_report.json", report)
    t = report["totals"]
    P(f"  审计口径：总调用 {t['calls']}｜成功 {t['success']}｜失败 {t['fail']}"
      f"｜成功率 {t['success_rate']}%")
    if report["failures_by_prefix"]:
        P(f"  失败分类：{report['failures_by_prefix']}")
    c = report["consistency"]
    P(f"  账目一致性：组3 工具步骤（成 {c['agent_tool_steps']['ok']}"
      f"/败 {c['agent_tool_steps']['fail']}）+ 技能步骤 {c['agent_skill_steps']['count']} 个"
      f"（{', '.join(c['agent_skill_steps']['names'])}，按契约不留痕）"
      f" vs stats.json 实际 {c['stats_observed_calls']} 条 → "
      f"{'一致' if c['consistent'] else '不一致'}")

    all_ok = (report["verdict"] == "PASS"
              and session["summary"]["fail"] == 0
              and bool(agent.self_healed))
    return {
        "ok": all_ok,
        "user_text": user_text,
        "intent": intent,
        "plan": plan,
        "session": session,
        "audit_report": report,
        "stats_summary": {"calls": t["calls"], "success": t["success"],
                          "fail": t["fail"], "rate": t["success_rate"]},
    }


def main() -> int:
    _banner("用户话语")
    print(f"  「{USER_TEXT}」")
    result = run_pipeline(USER_TEXT, verbose=True)

    _banner("全链路演示结果")
    print(f"  组1 意图 → 组2 计划 → 组3 执行 → 组4 真实工具 → 组5 审计")
    print(f"  审计结论：{result['audit_report']['verdict']}｜组3 步骤全成："
          f"{result['session']['summary']['fail'] == 0}｜自愈演示："
          f"{bool(result['session'].get('self_healed'))}")
    print(f"  产物目录：pipeline_demo{os.sep}out{os.sep}"
          f"（intent / plan / schemas / session_log / stats / audit_report）")
    print(f"\n  {'✅ 全链路跑通 — 这就是项目最终运行的样子' if result['ok'] else '❌ 存在失败步骤，见上方日志'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
