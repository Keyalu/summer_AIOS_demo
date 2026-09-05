"""
gen_dashboard.py — 组4 审计看板生成器（纯标准库，零依赖）

1. 若 assets/stats_demo.json 不存在，先运行一段模拟 Agent 会话
   （成功 + 各类失败混合），经真实 ToolRegistry/ToolStats 落盘；
2. 读取统计 JSON，把数据内嵌进单文件 assets/dashboard.html
   （无 CDN、离线可用，双击即可在浏览器打开，发给组5也无需任何环境）。

运行：python tools/gen_dashboard.py [--stats 路径]
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from src.tool_registry import ToolRegistry          # noqa: E402
from src.skill_library import SkillLibrary          # noqa: E402
from src.stats import ToolStats                     # noqa: E402
from src.interfaces import PermissionLevel          # noqa: E402

ASSETS = os.path.join(ROOT, "assets")
DEFAULT_STATS = os.path.join(ASSETS, "stats_demo.json")


def make_demo_stats(path: str) -> None:
    """跑一段模拟会话，产出带成功/失败/慢调用的真实统计数据。"""
    if os.path.exists(path):
        os.remove(path)
    stats = ToolStats(log_path=path)
    registry = ToolRegistry(stats=stats)
    skills = SkillLibrary(registry=registry)

    sandbox = os.path.join(ASSETS, "_sandbox")
    os.makedirs(os.path.join(sandbox, "docs"), exist_ok=True)

    U = PermissionLevel.USER
    A = PermissionLevel.ADMIN
    ok = registry.call("write_file", {"path": f"{sandbox}/readme.md", "content": "demo\n"}, U)
    assert ok.success, ok.error
    for name in ("a.md", "b.md", "c.md"):
        registry.call("write_file", {"path": f"{sandbox}/docs/{name}", "content": "x" * 400}, U)
    registry.call("list_directory", {"path": sandbox}, U)
    registry.call("read_file", {"path": f"{sandbox}/readme.md"}, U)
    registry.call("copy_file", {"src": f"{sandbox}/readme.md", "dest": f"{sandbox}/docs/readme_copy.md"}, U)
    skills.call_skill("find_duplicate_files", {"path": sandbox})
    skills.call_skill("disk_usage", {"path": sandbox})
    skills.call_skill("system_check")
    registry.call("run_command", {"cmd": "echo hello-from-gui-demo"}, A)

    # 失败样本：覆盖组3会遇到的各类 error 前缀
    registry.call("list_directory", {"path": sandbox}, PermissionLevel.PUBLIC)  # success（public 可只读）
    registry.call("run_command", {"cmd": "echo nope"}, U)                       # 权限不足
    registry.call("copy_file", {"src": "nonexistent__x.bin", "dest": f"{sandbox}/d.bin"}, U)  # 工具内部失败
    registry.call("write_file", {"path": "/etc/demo_block_test.txt", "content": "x"}, A)      # 受保护路径
    registry.call("run_command", {"cmd": "rm -rf /"}, A)                        # 拒绝执行（黑名单）
    registry.call("read_file", {}, U)                                           # 参数错误
    registry.call("no_such_tool", {}, U)                                        # 工具未注册（不进统计）
    print(f"[OK] 模拟会话完成 → {path}")


def load_stats(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>组4 · 工具调用审计看板</title>
<style>
:root{--ink:#0f172a;--sub:#64748b;--line:#e2e8f0;--blue:#2563eb;--blue-bg:#dbeafe;
--green:#16a34a;--green-bg:#dcfce7;--red:#dc2626;--red-bg:#fee2e2;--amber:#d97706}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f8fafc;color:var(--ink);padding:28px}
.wrap{max-width:1100px;margin:0 auto}
h1{font-size:22px}h1 small{font-size:13px;color:var(--sub);font-weight:400;margin-left:10px}
.meta{color:var(--sub);font-size:12.5px;margin:6px 0 22px}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:26px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.kpi .v{font-size:26px;font-weight:700}
.kpi .l{font-size:12px;color:var(--sub);margin-top:4px}
.ok{color:var(--green)}.bad{color:var(--red)}.bl{color:var(--blue)}
.panel{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:22px}
.panel h2{font-size:15px;margin-bottom:12px}
.bar-row{display:grid;grid-template-columns:170px 1fr 84px;align-items:center;gap:10px;margin:7px 0;font-size:12.5px}
.bar-track{background:#f1f5f9;border-radius:6px;height:18px;overflow:hidden}
.bar-fill{height:100%;border-radius:6px;background:var(--blue-bg);border-right:3px solid var(--blue)}
.fail .bar-fill{background:var(--red-bg);border-right-color:var(--red)}
.bar-num{color:var(--sub);text-align:right}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--sub);font-weight:600;font-size:12px;white-space:nowrap}
tr:hover td{background:#f8fafc}
.chip{display:inline-block;padding:1px 9px;border-radius:99px;font-size:11.5px;font-weight:600}
.chip.ok{background:var(--green-bg);color:var(--green)}.chip.bad{background:var(--red-bg);color:var(--red)}
code{font-family:Consolas,monospace;font-size:11.5px;color:#475569;word-break:break-all}
td:first-child code{white-space:nowrap;font-size:11px}
.err{color:var(--red)}
.note{font-size:12px;color:var(--sub);margin-top:8px}
</style>
</head>
<body>
<div class="wrap">
<h1>组4 · 工具调用审计看板<small>Tools 调用统计可视化</small></h1>
<div class="meta">数据文件：__SRC__ ｜ 生成时间：__GEN__ ｜ 组5 可直接消费本页所依据的 JSON，无需 import 任何 Python 代码</div>

<div class="kpis" id="kpis"></div>

<div class="panel"><h2>按工具聚合（调用 / 成功 / 失败）</h2><div id="bars"></div></div>

<div class="panel"><h2>失败事件分类（按 error 前缀）</h2><div id="fails"></div><div class="note">权限拦截发生在统计之前（调度层拒绝），因此不产生记录 —— 这是与组3定死的契约。</div></div>

<div class="panel"><h2>调用明细时间线（__N__ 条）</h2>
<table><thead><tr><th>时间</th><th>工具</th><th>结果</th><th>耗时</th><th>参数 / 错误</th></tr></thead>
<tbody id="rows"></tbody></table></div>

<div class="note">重新生成：修改演示内容后运行 <code>python tools/gen_dashboard.py</code>；联调演示可用 GUI（gui/server.py）实时产生新数据。</div>
</div>
<script>
const DATA = __DATA__;

function kpi(v,l,cls){return `<div class="kpi"><div class="v ${cls||""}">${v}</div><div class="l">${l}</div></div>`}

const recs=DATA.records||[], counters=DATA.counters||{};
let total=0,okN=0,failN=0,dur=0;
recs.forEach(r=>{total++;r.success?okN++:failN++;dur+=r.duration_ms||0});
const rate=total?(100*okN/total).toFixed(1):"0.0";
document.getElementById("kpis").innerHTML=
 kpi(total,"总调用次数","bl")+kpi(okN,"成功","ok")+kpi(failN,"失败",failN?"bad":"")+
 kpi(rate+"%","成功率",parseFloat(rate)>=90?"ok":"bad")+kpi((dur/Math.max(total,1)).toFixed(1)+" ms","平均耗时");

const tools=Object.keys(counters).sort((a,b)=>counters[b].calls-counters[a].calls);
const maxN=Math.max(1,...tools.map(t=>counters[t].calls));
document.getElementById("bars").innerHTML=tools.map(t=>{
 const c=counters[t],w=(100*c.calls/maxN).toFixed(1);
 const fail=c.fail>0;
 return `<div class="bar-row${fail?" fail":""}"><span>${t}</span>
 <div class="bar-track"><div class="bar-fill" style="width:${w}%"></div></div>
 <span class="bar-num">${c.calls} 次 · 败 ${c.fail}</span></div>`}).join("");

const errCount={};
recs.filter(r=>!r.success).forEach(r=>{
 const p=(r.error||"未知错误").split(":")[0].split("，")[0].split("（")[0].trim();
 errCount[p]=(errCount[p]||0)+1});
const errs=Object.entries(errCount).sort((a,b)=>b[1]-a[1]);
const maxE=Math.max(1,...errs.map(e=>e[1]));
document.getElementById("fails").innerHTML=errs.length?errs.map(([p,n])=>{
 const w=(100*n/maxE).toFixed(1);
 return `<div class="bar-row fail"><span>${p}</span>
 <div class="bar-track"><div class="bar-fill" style="width:${w}%"></div></div>
 <span class="bar-num">${n} 次</span></div>`}).join("")
 :'<div class="note">本次会话没有失败事件。</div>';

document.getElementById("rows").innerHTML=recs.slice().reverse().map(r=>`
 <tr><td><code>${(r.time||"").replace("T"," ").slice(0,19)}</code></td>
 <td><b>${r.tool}</b></td>
 <td><span class="chip ${r.success?"ok":"bad"}">${r.success?"成功":"失败"}</span></td>
 <td>${r.duration_ms} ms</td>
 <td>${r.success?`<code>${esc(JSON.stringify(r.params))}</code>`
   :`<span class="err">${esc(r.error||"")}</span>`}</td></tr>`).join("");

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
</script>
</body>
</html>
"""


def build_dashboard(stats_path: str, out_path: str) -> None:
    data = load_stats(stats_path)
    html = (
        HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
        .replace("__SRC__", os.path.relpath(stats_path, ROOT).replace("\\", "/"))
        .replace("__GEN__", data.get("updated", "-"))
        .replace("__N__", str(len(data.get("records", []))))
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] 看板已生成 → {out_path}")


def main() -> None:
    stats_path = DEFAULT_STATS
    if "--stats" in sys.argv:
        stats_path = os.path.abspath(sys.argv[sys.argv.index("--stats") + 1])
    if not os.path.exists(stats_path):
        make_demo_stats(stats_path)
    os.makedirs(ASSETS, exist_ok=True)
    build_dashboard(stats_path, os.path.join(ASSETS, "dashboard.html"))


if __name__ == "__main__":
    main()
