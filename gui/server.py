"""
server.py — 分组四 GUI 响应模块（纯标准库，零第三方依赖）

给 ToolRegistry / SkillLibrary / MCPConnector 套一层本地 Web 界面：
  - 工具台：列出全部工具（schema 内省），填参数、选权限、发起真实调用
  - 技能台：一键调用 8 个 OS 技能
  - 统计看板：实时查看 stats（成功/失败/耗时），供组5审计演示
  - MCP：以 JSON-RPC 2.0 格式调用 3 个 Mock 工具

运行：
    python gui/server.py            # 默认 http://127.0.0.1:8765
    python gui/server.py --port 9000

安全说明：工具调用是**真实 OS 操作**。服务只绑定 127.0.0.1，
权限闸门、黑名单、受保护路径拦截与生产代码完全一致；
演示时建议把文件参数指向沙箱目录。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from src.tool_registry import ToolRegistry          # noqa: E402
from src.skill_library import SkillLibrary          # noqa: E402
from src.mcp_connector import MCPConnector          # noqa: E402
from src.stats import ToolStats                     # noqa: E402
from src.interfaces import PermissionLevel          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
STATS_PATH = os.path.join(ROOT, "assets", "stats_gui.json")
INDEX_PATH = os.path.join(HERE, "index.html")

LEVELS = {"public": PermissionLevel.PUBLIC, "user": PermissionLevel.USER,
          "admin": PermissionLevel.ADMIN}


class Stack:
    """一次可整体重建的模块栈（Reset 用）。"""

    def __init__(self) -> None:
        self.stats = ToolStats(log_path=STATS_PATH)
        self.registry = ToolRegistry(stats=self.stats)
        self.skills = SkillLibrary(registry=self.registry)
        self.mcp = MCPConnector()
        self.mcp.register_mock_tools(self.registry)

    def reset(self) -> None:
        if os.path.exists(STATS_PATH):
            os.remove(STATS_PATH)
        new = Stack()
        self.stats, self.registry, self.skills, self.mcp = (
            new.stats, new.registry, new.skills, new.mcp)


STACK = Stack()


def stats_payload(max_records: int = 200) -> dict:
    """读取统计（直接读落盘 JSON，与组5消费方式一致）。"""
    payload: dict = {"records": [], "counters": {}, "updated": None}
    if os.path.exists(STATS_PATH):
        try:
            with open(STATS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            payload["records"] = data.get("records", [])[-max_records:]
            payload["counters"] = data.get("counters", {})
            payload["updated"] = data.get("updated")
        except (json.JSONDecodeError, OSError):
            pass
    total = sum(c["calls"] for c in payload["counters"].values())
    ok = sum(c["success"] for c in payload["counters"].values())
    payload["summary"] = {"total": total, "ok": ok,
                          "fail": total - ok,
                          "rate": round(100 * ok / total, 1) if total else 0.0}
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "Group4GUI/1.0"

    # ---------- helpers ----------
    def _serve_file(self, path: str, ctype: str) -> None:
        if not os.path.exists(path):
            self._json({"error": "not found"}, 404)
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: dict, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict | None:
        """解析请求体；返回 None 表示请求体非法，{} 表示合法的空体。"""
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def log_message(self, fmt: str, *args) -> None:  # 安静模式
        pass

    # ---------- GET ----------
    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            with open(INDEX_PATH, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/dashboard":
            self._serve_file(os.path.join(ROOT, "assets", "dashboard.html"),
                             "text/html; charset=utf-8")
        elif self.path.startswith("/charts/"):
            rest = self.path[len("/charts/"):]
            if rest.startswith("view/"):                    # HTML 包裹页（便于截图/查看）
                name = os.path.basename(rest)
                svg_path = os.path.join(ROOT, "assets", "charts", name + ".svg")
                if not os.path.exists(svg_path):
                    self._json({"error": "not found"}, 404)
                    return
                import re
                with open(svg_path, encoding="utf-8") as f:
                    svg = f.read()
                m = re.search(r'width="(\d+)" height="(\d+)"', svg)
                w, h = (int(m.group(1)), int(m.group(2))) if m else (1240, 560)  # noqa
                html = (f'<!DOCTYPE html><meta charset="utf-8">'
                        f'<title>{name}</title>'
                        f'<style>html,body{{margin:0;padding:0;background:#fff;overflow:hidden}}</style>'
                        f'{svg}')
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                name = os.path.basename(rest)               # 防路径穿越
                self._serve_file(os.path.join(ROOT, "assets", "charts", name),
                                 "image/svg+xml; charset=utf-8")
        elif self.path == "/api/tools":
            self._json({"tools": [s.to_dict() for s in STACK.registry.list_tools()]})
        elif self.path == "/api/skills":
            self._json({"skills": [s.to_dict() for s in STACK.skills.list_skills()]})
        elif self.path == "/api/stats":
            self._json(stats_payload())
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self._json({"error": "not found"}, 404)

    # ---------- POST ----------
    def do_POST(self) -> None:
        body = self._body()
        if body is None:  # 请求体不是合法 UTF-8 JSON
            self._json({"error": "请求体不是合法的 UTF-8 JSON"}, 400)
            return
        try:
            self._route_post(body)
        except Exception as e:  # 任何异常都以 JSON 返回，不让连接裸断
            self._json({"error": f"服务端异常: {type(e).__name__}: {e}"}, 500)

    def _route_post(self, body: dict) -> None:
        if self.path == "/api/call":
            name = str(body.get("name", ""))
            params = body.get("params") or {}
            level = LEVELS.get(str(body.get("level", "user")).lower())
            if level is None:
                self._json({"error": "level 必须是 public/user/admin"}, 400)
                return
            t0 = time.perf_counter()
            result = STACK.registry.call(name, params, level)
            self._json({"result": result.to_dict(),
                        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                        "level": level.value})
        elif self.path == "/api/skill":
            name = str(body.get("name", ""))
            params = body.get("params") or {}
            t0 = time.perf_counter()
            result = STACK.skills.call_skill(name, params)
            self._json({"result": result.to_dict(),
                        "duration_ms": round((time.perf_counter() - t0) * 1000, 2)})
        elif self.path == "/api/jsonrpc":
            method = str(body.get("method", ""))
            params = body.get("params") or {}
            resp = STACK.mcp.mock_jsonrpc_call(STACK.registry, method, params)
            self._json({"response": resp})
        elif self.path == "/api/pipeline":
            # 五组全链路演示：组1/2/3/5 为联调替身，组4 真实模块参与
            try:
                from pipeline_demo.run_demo import run_pipeline, OUT as PIPE_OUT
                user_text = str(body.get("user_text")) if body.get("user_text") else None
                result = run_pipeline(user_text=user_text, out=PIPE_OUT, verbose=False)
                self._json(result)
            except Exception as e:
                self._json({"ok": False, "error": f"全链路执行失败: {type(e).__name__}: {e}"}, 500)
        elif self.path == "/api/reset":
            STACK.reset()
            self._json({"ok": True, "message": "统计已清零，模块栈已重建"})
        else:
            self._json({"error": "not found"}, 404)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="分组四 GUI 响应模块")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(STATS_PATH), exist_ok=True)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    n_tools = len(STACK.registry.list_tools())
    n_skills = len(STACK.skills.list_skills())
    print("=" * 56)
    print("  组4 GUI 响应模块已启动")
    print(f"  地址：http://{args.host}:{args.port}")
    print(f"  已加载：{n_tools} 个工具 / {n_skills} 个技能 / 3 个 MCP Mock")
    print("  注意：调用是真实 OS 操作，演示请用沙箱目录")
    print("  Ctrl+C 停止")
    print("=" * 56)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
