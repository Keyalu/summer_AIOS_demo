"""
pipeline_demo — 五组全链路演示（组3 / 组5 为联调替身）

目的：在组3、组5 交付前，用可替换的替身把整条流水线跑起来，
让分组四看到"项目最终跑起来长什么样"，并提前验证组间契约。

契约纪律（与 docs/week3 组间集成指南一致）：
- 组1 HostAgent / 组2 TaskPlanner：纯逻辑，不 import 分组四任何代码；
- 组3 AppAgent 替身：只通过公开契约消费（ToolRegistry / SkillLibrary /
  ToolResult.to_dict()），Mock 换真实零改动；
- 组5 Coordinator 替身：只读 JSON 文件（stats.json / schemas.json /
  session_log.json），不 import 分组四任何代码；
- 组4：真实模块原样参与，不做任何适配性修改。

运行：python pipeline_demo/run_demo.py
"""

from .host_agent import HostAgentStandIn
from .task_planner import TaskPlannerStandIn
from .app_agent import AppAgentStandIn
from .coordinator import CoordinatorStandIn

__all__ = [
    "HostAgentStandIn",
    "TaskPlannerStandIn",
    "AppAgentStandIn",
    "CoordinatorStandIn",
]
