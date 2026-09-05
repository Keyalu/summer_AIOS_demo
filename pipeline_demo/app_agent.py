"""组3 AppAgent 替身 — plan_json → 逐步调用分组四 → session_log.json。

只通过公开契约消费（与 tests/test_integration.py 的 SimulatedAgent
同一纪律）：
  - registry.call(name, params, user_level)
  - skills.call_skill(name, params)
  - 结果永远拿到 ToolResult / dict，读 error 前缀做决策
Mock 换真实零改动：构造时传 MockToolRegistry 或 ToolRegistry 均可。
"""

from __future__ import annotations

import time
import uuid

from src.interfaces import PermissionLevel


class AppAgentStandIn:
    """按计划执行，带提权重试与工具名纠错（自愈）两条组3既定策略。"""

    def __init__(self, registry, skills=None, level: PermissionLevel = PermissionLevel.USER):
        self.registry = registry
        self.skills = skills
        self.base_level = level
        self.session_id = f"agent-{uuid.uuid4().hex[:8]}"

    # ---- 公开契约的用法示例：schema 内省（可喂给 LLM function-calling）----
    def tool_menu(self) -> list[str]:
        return [s.to_dict()["name"] for s in self.registry.list_tools()]

    # ---- 主流程 ----
    def execute_plan(self, plan: dict, verbose: bool = False) -> dict:
        steps_out: list[dict] = []
        escalated: list[dict] = []
        for step in plan.get("steps", []):
            rec = self._run_step(step, escalated, verbose)
            steps_out.append(rec)
        ok = sum(1 for s in steps_out if s["tool_result"]["success"])
        return {
            "session_id": self.session_id,
            "plan_id": plan.get("plan_id"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "steps": steps_out,
            "escalations": escalated,
            "self_healed": self.self_healed,
            "summary": {"total": len(steps_out), "success": ok,
                        "fail": len(steps_out) - ok},
        }

    def _run_step(self, step: dict, escalated: list, verbose: bool) -> dict:
        name = step["name"]
        params = step.get("params", {})
        # 统一从组3 的基础身份起手：需要 ADMIN 的步骤先尝试 → 被拒 →
        # 请求用户确认 → 提权重试（这正是权限交互的完整闭环）
        level = self.base_level
        t0 = time.perf_counter()

        if step.get("kind") == "skill" and self.skills is not None:
            result = self.skills.call_skill(name, params)
        else:
            result = self.registry.call(name, params, level)

        # 策略 1：权限不足 → 请求用户确认（此处模拟"用户点了同意"）→ 提权重试一次
        # 触发两种情况：a) 计划标注需要 ADMIN，先按当前身份尝试被拒；
        #              b) 普通步骤意外被拒。
        if (not result.success and result.error
                and result.error.startswith("权限不足")):
            if verbose:
                print(f"    [组3] {name} 被拒（{result.error}）"
                      f"→ 请求用户确认…（模拟用户：同意）→ 提权 ADMIN 重试")
            escalated.append({"step": step["step"], "tool": name,
                              "from": level.value, "to": "admin",
                              "user_confirmed": True})
            level = PermissionLevel.ADMIN
            result = self.registry.call(name, params, level)

        duration = round((time.perf_counter() - t0) * 1000, 2)
        rec = {
            "step": step["step"],
            "kind": step.get("kind", "tool"),
            "name": name,
            "params_sent": params,
            "level_used": level.value,
            "duration_ms": duration,
            "tool_result": result.to_dict() if hasattr(result, "to_dict") else result,
        }
        if verbose:
            mark = "OK " if rec["tool_result"]["success"] else "FAIL"
            print(f"    [组3] 步骤{step['step']} {name} [{level.value}] → {mark}"
                  f"（{duration} ms）")
        return rec

    # ---- 策略 2：工具名写错 → list_tools 模糊匹配纠错（自愈）----
    self_healed: list[dict] = []

    def try_call_with_selfheal(self, name: str, params: dict,
                               level: PermissionLevel | None = None):
        level = level or self.base_level
        result = self.registry.call(name, params, level)
        if (not result.success and result.error
                and result.error.startswith("工具未注册")):
            fixed = self._fuzzy_fix(name)
            if fixed and fixed != name:
                result = self.registry.call(fixed, params, level)
                self.self_healed.append({"wrong": name, "fixed": fixed})
        return result

    def _fuzzy_fix(self, name: str) -> str | None:
        best, best_score = None, 0
        for schema in self.registry.list_tools():
            candidate = schema.to_dict()["name"]
            score = sum(1 for ch in name if ch in candidate)
            if score > best_score:
                best, best_score = candidate, score
        return best if best_score >= len(name) - 3 else None
