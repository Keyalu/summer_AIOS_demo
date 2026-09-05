"""组5 Coordinator 替身 — 只吃 JSON 文件，不 import 分组四任何代码。

输入（全部是磁盘上的 JSON，与组5 真实消费方式一致）：
  - schemas.json     工具能力快照（MCP inputSchema 同构）
  - stats.json       调用统计（分组四 BufferedToolStats/ToolStats 落盘）
  - session_log.json 组3 的执行日志（含其自报的成败计数）

输出：audit_report.json —— 审计报告 + 账目一致性核验。
"""

from __future__ import annotations

import json
import time


class CoordinatorStandIn:
    """check_result / check_params / ingest_audit 三个动作 + 总审计。"""

    def __init__(self, schemas_path: str):
        with open(schemas_path, encoding="utf-8") as f:
            self._schemas = {s["name"]: s for s in json.load(f)}

    # ---- 动作 1：校验 ToolResult JSON 结构（读前缀即可自愈的基础）----
    def check_result(self, result_dict: dict) -> list[str]:
        errs = []
        if "success" not in result_dict:
            return ["缺少 success 字段"]
        if result_dict["success"]:
            if "result" not in result_dict:
                errs.append("成功结果必须带 result")
            if "error" in result_dict:
                errs.append("成功结果不应带 error")
        else:
            if "error" not in result_dict:
                errs.append("失败结果必须带 error")
            if "result" in result_dict:
                errs.append("失败结果不应带 result")
        return errs

    # ---- 动作 2：用 inputSchema 校验调用参数 ----
    def check_params(self, tool: str, params: dict) -> list[str]:
        schema = self._schemas.get(tool)
        if schema is None:
            return [f"schema 快照中没有 {tool}"]
        required = schema.get("inputSchema", {}).get("required", [])
        return [f"缺少必需参数 {k}" for k in required if k not in params]

    # ---- 动作 3：吸收 stats.json 并出审计报告 ----
    def ingest_audit(self, stats_path: str, session_log_path: str) -> dict:
        with open(stats_path, encoding="utf-8") as f:
            stats = json.load(f)
        with open(session_log_path, encoding="utf-8") as f:
            session = json.load(f)

        records = stats.get("records", [])
        counters = stats.get("counters", {})
        total = sum(c.get("calls", 0) for c in counters.values())
        ok = sum(c.get("success", 0) for c in counters.values())

        # 失败按 error 前缀分类（组3 读前缀自愈的镜像）
        by_prefix: dict[str, int] = {}
        for r in records:
            if not r.get("success"):
                prefix = (r.get("error") or "未知错误").split(":")[0].strip()
                by_prefix[prefix] = by_prefix.get(prefix, 0) + 1

        # 结构校验：每条记录的必要字段
        malformed = [i for i, r in enumerate(records)
                     if not all(k in r for k in ("time", "tool", "success", "duration_ms"))]

        # 账目一致性（按 docs/week3 集成指南的契约）：
        #   - 工具级调用 → 必然在 stats.json 留痕；
        #   - 技能级调用 → 直接操作文件系统、不经 Registry（指南 §4，设计如此），
        #     除非技能内部调用工具，否则不留痕 → 组5 只核"工具步骤"的账。
        steps = session.get("steps", [])
        agent_tool_ok = sum(1 for s in steps
                            if s.get("kind") == "tool" and s["tool_result"]["success"])
        agent_tool_fail = sum(1 for s in steps
                              if s.get("kind") == "tool" and not s["tool_result"]["success"])
        skill_steps = [s for s in steps if s.get("kind") == "skill"]
        consistent = total >= agent_tool_ok and (total - ok) >= agent_tool_fail

        report = {
            "report_id": f"audit-{time.strftime('%Y%m%d-%H%M%S')}",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "inputs": {"stats": stats_path, "session_log": session_log_path},
            "totals": {"calls": total, "success": ok, "fail": total - ok,
                       "success_rate": round(100 * ok / total, 1) if total else 0.0},
            "by_tool": {k: v for k, v in sorted(counters.items())},
            "failures_by_prefix": by_prefix,
            "schema_and_structure": {
                "schemas_loaded": len(self._schemas),
                "malformed_records": malformed,
            },
            "consistency": {
                "agent_tool_steps": {"ok": agent_tool_ok, "fail": agent_tool_fail},
                "agent_skill_steps": {"count": len(skill_steps),
                                      "names": [s["name"] for s in skill_steps]},
                "stats_observed_calls": total,
                "consistent": consistent,
                "note": "只有工具级调用在 stats.json 留痕；技能直接操作文件系统"
                        "不经 Registry（集成指南 §4，设计如此），权限被拒的调度层"
                        "拒绝也不产生记录 —— 三条都是与组3定死的契约",
            },
            "verdict": "PASS" if (consistent and not malformed) else "FAIL",
        }
        return report
