"""组1 HostAgent 替身 — 自然语言 → intent_json（纯逻辑，零依赖）。"""

from __future__ import annotations

import re
import time
import uuid

# 关键词 → 动作（真实组1 会用 LLM 做这一步，这里用规则演示数据形状）
_RULES: list[tuple[str, str, str]] = [
    (r"整理|归类|分类", "organize", "把目标目录里的文件按类型分类到子文件夹"),
    (r"重复|查重|冗余", "find_duplicates", "找出目标目录里内容重复的文件"),
    (r"备份|备个份", "backup", "把目标目录压缩备份"),
    (r"大文件", "find_large_files", "找出目标目录里最大的若干文件"),
    (r"磁盘|空间", "disk_usage", "查询磁盘使用情况"),
    (r"系统状态|体检|检查系统", "system_check", "检查系统状态"),
    (r"清理|清空", "cleanup_temp", "清理临时文件"),
    (r"找|搜索|查找", "find_files", "按条件搜索文件"),
]

_INTENT_RE = re.compile("|".join(pattern for pattern, _, _ in _RULES))


def _action_for(text: str) -> tuple[str, str] | None:
    for pattern, action, desc in _RULES:
        if re.search(pattern, text):
            return action, desc
    return None


class HostAgentStandIn:
    """解析用户话语，产出 intent_json（下游唯一输入）。"""

    def parse(self, user_text: str, default_target: str) -> dict:
        goals: list[dict] = []
        seen: set[str] = set()
        # 按规则表中顺序抽取多个动作（一句话可以包含多个目标）
        for pattern, action, desc in _RULES:
            if re.search(pattern, user_text) and action not in seen:
                seen.add(action)
                goals.append({"action": action, "description": desc})
        target = default_target          # 工作路径由宿主环境解析（组1 有环境访问权）
        target_label = default_target    # 用户口中的称呼（仅作展示）
        m = re.search(r"[「'\"]([^」'\"]+)[」'\"]", user_text)
        if m:
            target_label = m.group(1)
        return {
            "intent_id": f"intent-{uuid.uuid4().hex[:8]}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "user_text": user_text,
            "language": "zh-CN",
            "target": target,
            "target_label": target_label,
            "goals": goals,
            "confidence": 0.9 if goals else 0.3,
            "unresolved": [] if goals else ["未能从话语中识别出任何目标动作"],
        }
