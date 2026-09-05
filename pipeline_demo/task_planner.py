"""组2 TaskPlanner 替身 — intent_json → plan_json（纯逻辑，零依赖）。

计划里的 name 只使用分组四《组间集成指南》公布的工具/技能全名；
requires_admin 标记该步骤需要 ADMIN 级（真实组2 会把它变成
"请求用户确认"的交互点）。
"""

from __future__ import annotations

import time
import uuid

# intent 动作 → 计划步骤（skill 名与指南第 4 节一致）
_SKILL_FOR_ACTION = {
    "organize": ("organize_downloads", "整理目录"),
    "find_duplicates": ("find_duplicate_files", "查找重复文件"),
    "backup": ("backup_directory", "目录压缩备份"),
    "find_large_files": ("find_large_files", "查找大文件"),
    "disk_usage": ("disk_usage", "查询磁盘使用情况"),
    "system_check": ("system_check", "检查系统状态"),
    "cleanup_temp": ("cleanup_temp", "清理临时文件"),
    "find_files": ("find_files", "搜索文件"),
}


class TaskPlannerStandIn:
    """把 intent_json 翻译成可执行的 plan_json（下游唯一输入）。"""

    def plan(self, intent: dict) -> dict:
        steps: list[dict] = []
        n = 0
        target = intent.get("target", "~/Downloads")

        for goal in intent.get("goals", []):
            action = goal.get("action", "")
            if action in _SKILL_FOR_ACTION:
                name, desc = _SKILL_FOR_ACTION[action]
                n += 1
                params: dict = {"path": target} if name not in (
                    "system_check", "backup_directory") else {}
                if name == "backup_directory":
                    params = {"src": target, "dest": target.rstrip("/\\") + "_backup"}
                steps.append({
                    "step": n,
                    "kind": "skill",
                    "name": name,
                    "params": params,
                    "requires_admin": False,
                    "description": desc,
                })

        if not steps:  # 兜底：听不懂就先只读探查（PUBLIC 即可）
            n += 1
            steps.append({
                "step": n, "kind": "tool", "name": "list_directory",
                "params": {"path": target}, "requires_admin": False,
                "description": "未能理解目标，先列出目录内容",
            })

        # 收尾：用一条系统命令汇报完成（演示权限流：需要 ADMIN）
        n += 1
        steps.append({
            "step": n, "kind": "tool", "name": "run_command",
            "params": {"cmd": "echo [plan done]"},
            "requires_admin": True,
            "description": "执行收尾命令（演示 USER→ADMIN 提权流）",
        })

        return {
            "plan_id": f"plan-{uuid.uuid4().hex[:8]}",
            "based_on": intent.get("intent_id"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "target": target,
            "steps": steps,
            "policy": {
                "on_permission_denied": "请求用户确认后提权重试一次",
                "on_tool_not_found": "用 list_tools 模糊匹配纠错",
                "on_other_fail": "记录并继续后续步骤",
            },
        }
