"""
mcp_connector.py — 模型上下文协议集成模块

融合了三个版本的优点：
- 我搭建版本的 MCP Server 连接管理、Mock 工具注册
- 版本2 的 JSON-RPC 2.0 Mock 调用格式
- 真实 MCP 接入预留接口
"""

from __future__ import annotations
from typing import Any, Callable
from datetime import datetime
from .interfaces import IToolRegistry, ToolResult


class MCPConnector:
    """MCP 协议连接器。当前为 Mock 实现，预留真实接入接口。"""

    def __init__(self) -> None:
        self.servers: dict[str, dict] = {}
        self.tools: dict[str, Callable] = {}

    # ----------------------------------------------------------
    # MCP Server 管理
    # ----------------------------------------------------------

    def connect_server(self, name: str, config: dict) -> dict:
        """连接一个 MCP Server（当前为 Mock）。"""
        if name in self.servers:
            return {"success": False, "error": f"服务器 '{name}' 已连接"}

        self.servers[name] = {
            "name": name,
            "config": config,
            "status": "connected",
            "tools_count": 0,
        }
        return {"success": True, "server_id": name}

    def disconnect_server(self, name: str) -> dict:
        """断开 MCP Server 连接。"""
        if name not in self.servers:
            return {"success": False, "error": f"服务器 '{name}' 未连接"}
        del self.servers[name]
        return {"success": True, "result": f"已断开: {name}"}

    def list_servers(self) -> list[dict]:
        """列出所有已连接的 MCP Server。"""
        return list(self.servers.values())

    # ----------------------------------------------------------
    # Mock 工具注册
    # ----------------------------------------------------------

    def register_mock_tools(self, registry: IToolRegistry) -> None:
        """将 Mock MCP 工具注册到 ToolRegistry（幂等：重复调用不会报错）。"""
        self._setup_mock_search(registry)
        self._setup_mock_weather(registry)
        self._setup_mock_translate(registry)

        server_id = "mock-server"
        self.servers[server_id] = {
            "name": server_id,
            "config": {"mode": "mock"},
            "status": "connected",
            "tools_count": 3,
        }

    def _setup_mock_search(self, registry: IToolRegistry) -> None:
        def mock_search(query: str, engine: str = "web") -> str:
            return f"Mock 搜索 ({engine}): 找到 3 条 {query} 相关结果"
        # Week3 加固：已注册则跳过，保证重复调用 register_mock_tools 不崩溃
        if not registry.has("mcp_search"):
            registry.register("mcp_search", mock_search)

    def _setup_mock_weather(self, registry: IToolRegistry) -> None:
        def mock_weather(city: str, days: int = 1) -> str:
            return f"Mock 天气: {city} 晴转多云, 18°C~28°C, 空气质量良"
        if not registry.has("mcp_weather"):
            registry.register("mcp_weather", mock_weather)

    def _setup_mock_translate(self, registry: IToolRegistry) -> None:
        def mock_translate(text: str, to_lang: str = "en") -> str:
            samples = {
                ("你好", "en"): "Hello",
                ("Hello", "zh"): "你好",
            }
            return samples.get((text, to_lang), f"[Mock翻译] {text} -> {to_lang}")
        if not registry.has("mcp_translate"):
            registry.register("mcp_translate", mock_translate)

    # ----------------------------------------------------------
    # JSON-RPC 2.0 Mock 调用（来自版本2）
    # ----------------------------------------------------------

    def mock_jsonrpc_call(
        self,
        registry: IToolRegistry,
        name: str,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """以 JSON-RPC 2.0 格式调用工具（Mock）。

        错误码细分（Week3 加固，符合 JSON-RPC 2.0 规范）：
        -32601  Method not found  —— 工具未注册
        -32603  Internal error    —— 工具执行失败
        """
        params = params or {}
        req_id = abs(hash(datetime.now().isoformat())) % 100000
        result = registry.call(name, params)
        if result.success:
            error = None
        elif not registry.has(name):
            error = {"code": -32601, "message": result.error}
        else:
            error = {"code": -32603, "message": result.error}
        return {
            "jsonrpc": "2.0",
            "result": result.result if result.success else None,
            "error": error,
            "id": req_id,
        }

    # ----------------------------------------------------------
    # 真实 MCP 接入预留
    # ----------------------------------------------------------

    def connect_real_mcp(self, command: str, args: list[str]) -> dict:
        """连接真实 MCP Server（预留接口）。"""
        return {
            "success": False,
            "error": (
                "真实 MCP 连接尚未实现。"
                "请安装 mcp SDK (pip install mcp) 后替换此 Mock。"
                f"预期配置: command={command}, args={args}"
            ),
        }
