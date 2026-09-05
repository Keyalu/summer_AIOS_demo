"""
gen_charts.py — 分组四可视化图表生成器（纯标准库，零依赖）

生成 5 张 SVG 到 assets/charts/，再用浏览器截图导出 PNG（见 assets/README.md）：
  1. benchmark    — Week3 高压优化实测收益（对数轴前后对比）
  2. pipeline     — 五组流水线与组4位置
  3. permissions  — 三级权限模型
  4. security     — 四层安全闸门
  5. flow         — 一次命令调用的跨文件流转路线

运行：python tools/gen_charts.py
"""

from __future__ import annotations

import math
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "charts")

FONT = "'Microsoft YaHei', 'PingFang SC', 'Noto Sans CJK SC', sans-serif"
INK = "#0f172a"
SUB = "#64748b"
LINE = "#e2e8f0"
BLUE = "#2563eb"
BLUE_BG = "#dbeafe"
BLUE_MID = "#93c5fd"
GRAY_BG = "#f1f5f9"
GREEN = "#16a34a"
GREEN_BG = "#dcfce7"
RED = "#dc2626"
RED_BG = "#fee2e2"
AMBER = "#d97706"
AMBER_BG = "#fef3c7"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_open(w: int, h: int, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="{FONT}">\n'
        f'<title>{esc(title)}</title>\n'
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>\n'
    )


def title_block(w: int, title: str, sub: str) -> str:
    return (
        f'<text x="40" y="52" font-size="26" font-weight="700" fill="{INK}">{esc(title)}</text>\n'
        f'<text x="40" y="80" font-size="14" fill="{SUB}">{esc(sub)}</text>\n'
    )


def box(x: int, y: int, w: int, h: int, fill: str, stroke: str, rx: int = 10,
        dash: str = "") -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"{d}/>\n')


def text(x: int, y: int, s: str, size: int = 14, fill: str = INK, weight: str = "400",
         anchor: str = "start") -> str:
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>\n')


def arrow_h(x1: int, y: int, x2: int, color: str = SUB, label: str = "",
            label_y_off: int = -10) -> str:
    out = (f'<line x1="{x1}" y1="{y}" x2="{x2 - 8}" y2="{y}" stroke="{color}" '
           f'stroke-width="2" marker-end="url(#ah)"/>\n')
    if label:
        out += text((x1 + x2) // 2, y + label_y_off, label, 12, SUB, anchor="middle")
    return out


def arrow_v(x: int, y1: int, y2: int, color: str = SUB, label: str = "",
            label_dx: int = 10) -> str:
    out = (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2 - 8}" stroke="{color}" '
           f'stroke-width="2" marker-end="url(#ah)"/>\n')
    if label:
        out += text(x + label_dx, (y1 + y2) // 2 + 4, label, 12, SUB)
    return out


DEFS = (
    '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{SUB}"/></marker>'
    '<marker id="ah-red" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{RED}"/></marker>'
    '<marker id="ah-green" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{GREEN}"/></marker></defs>\n'
)


# ----------------------------------------------------------------------
# 1. benchmark — 高压优化实测收益（对数轴）
# ----------------------------------------------------------------------
def chart_benchmark() -> str:
    W, H = 1240, 560
    x0, x1 = 430, 1150          # 绘图区：0.01s ~ 1000s，5 个数量级
    decades = math.log10(1000) - math.log10(0.01)

    def xof(v: float) -> int:
        return int(x0 + (math.log10(v) - math.log10(0.01)) / decades * (x1 - x0))

    groups = [  # (名称, 优化前, 优化后, 加速比, 优化手段)
        ("list_directory\n万文件列目录", 108.55, 0.051, "2146.3x", "os.scandir + 分页游标"),
        ("find_duplicate_files\n2000 文件查重", 7.34, 0.533, "13.8x", "先按大小预分组，只对嫌疑文件算 MD5"),
        ("统计落盘 1000 条\nBufferedToolStats", 53.1, 0.30, "177.7x", "缓冲批量写入 + 环形缓冲"),
    ]
    out = svg_open(W, H, "Week3 高压优化实测收益")
    out += DEFS
    out += title_block(W, "Week3 高压优化：实测前后对比",
                       "数据来源：stress/results.json（B1/B2）与 docs/week3 压测报告 A2，均为实测值；横轴为对数刻度")

    # 网格与刻度
    ticks = [0.01, 0.1, 1, 10, 100, 1000]
    for t in ticks:
        tx = xof(t)
        out += f'<line x1="{tx}" y1="110" x2="{tx}" y2="470" stroke="{LINE}" stroke-width="1"/>\n'
        out += text(tx, 492, f"{t:g}s", 12, SUB, anchor="middle")
    out += text((x0 + x1) // 2, 518, "单次操作耗时（秒，对数轴）", 13, SUB, anchor="middle")

    for i, (name, old, new, speed, how) in enumerate(groups):
        top = 130 + i * 118
        lines = name.split("\n")
        out += text(x0 - 20, top + 22, lines[0], 15, INK, "600", anchor="end")
        out += text(x0 - 20, top + 44, lines[1], 13, SUB, anchor="end")
        # 优化前红条
        y_old = top + 8
        out += box(x0, y_old, xof(old) - x0, 26, RED_BG, RED, rx=5)
        out += text(xof(old) + 8, y_old + 18, f"{old:g}s", 13, RED, "600")
        # 优化后绿条
        y_new = top + 42
        out += box(x0, y_new, xof(new) - x0, 26, GREEN_BG, GREEN, rx=5)
        out += text(xof(new) + 8, y_new + 18, f"{new:g}s", 13, GREEN, "600")
        # 手段说明
        out += text(x0 + 8, y_new + 48, f"手段：{how}", 12, SUB)
        # 加速比徽章
        cx = x1 + 12
        out += box(cx, top + 16, 62, 40, BLUE_BG, BLUE, rx=8)
        out += text(cx + 31, top + 34, speed.replace("x", ""), 14, BLUE, "700", anchor="middle")
        out += text(cx + 31, top + 49, "倍速", 10, BLUE, anchor="middle")

    out += "</svg>\n"
    return out


# ----------------------------------------------------------------------
# 2. pipeline — 五组流水线
# ----------------------------------------------------------------------
def chart_pipeline() -> str:
    W, H = 1240, 430
    bw, bh, gap = 200, 112, 45
    total = 5 * bw + 4 * gap
    x_start = (W - total) // 2
    y = 140
    names = ["组1\nHostAgent", "组2\nTaskPlanner", "组3\nAppAgent", "组4\nTools + OS Skills", "组5\nCoordinator"]
    caps = ["解析用户意图", "规划任务步骤", "执行代理", "工具注册表·技能库·MCP（本组）", "审计·安全·RAG"]
    fills = [GRAY_BG, GRAY_BG, GRAY_BG, BLUE, GRAY_BG]
    strokes = [LINE, LINE, LINE, BLUE, LINE]
    inks = [INK, INK, INK, "#ffffff", INK]
    subs = [SUB, SUB, SUB, BLUE_BG, SUB]

    out = svg_open(W, H, "五组流水线")
    out += DEFS
    out += title_block(W, "我们在流水线中的位置：夹在组3与操作系统之间",
                       "参考 MCP 协议思想，组间以 JSON（JSON-RPC 2.0）传递数据；组4 为整条链路唯一真实触碰 OS 的环节")

    xs = []
    for i in range(5):
        x = x_start + i * (bw + gap)
        xs.append(x)
        out += box(x, y, bw, bh, fills[i], strokes[i], rx=12)
        lines = names[i].split("\n")
        out += text(x + bw // 2, y + 44, lines[0], 17, inks[i], "700", anchor="middle")
        out += text(x + bw // 2, y + 72, lines[1], 15, inks[i], "700", anchor="middle")
        if i == 3:  # 组4 的下方被 OS 连接箭头占用，说明放进盒子内第三行
            out += text(x + bw // 2, y + 94, "工具注册表 · 技能库 · MCP", 11, BLUE_BG, anchor="middle")
        else:
            out += text(x + bw // 2, y + bh + 24, caps[i], 12, SUB, anchor="middle")
        if i < 4:
            out += arrow_h(x + bw + 4, y + bh // 2, x + bw + gap - 4)

    # 数据标注
    out += text((xs[2] + bw + xs[3]) // 2, y - 26, "registry.call()", 12, BLUE, "600", anchor="middle")
    out += text((xs[3] + bw + xs[4]) // 2, y - 26, "stats.json", 12, SUB, "600", anchor="middle")

    # 组4 与 OS 的连接
    gx = xs[3] + bw // 2
    oy = y + bh + 66
    out += box(xs[3] - 40, oy, bw + 80, 70, "#f8fafc", "#94a3b8", rx=12, dash="6,4")
    out += text(xs[3] - 40 + (bw + 80) // 2, oy + 30, "Linux 文件系统 / Shell", 15, INK, "600", anchor="middle")
    out += text(xs[3] - 40 + (bw + 80) // 2, oy + 52, "8 个工具真实执行（copy/move/delete/create/list/read/write/run_command）", 11, SUB, anchor="middle")
    out += f'<line x1="{gx - 14}" y1="{y + bh + 6}" x2="{gx - 14}" y2="{oy - 8}" stroke="{SUB}" stroke-width="2" marker-end="url(#ah)"/>'
    out += text(gx - 22, (y + bh + 6 + oy) // 2 + 4, "调用", 12, SUB, anchor="end")
    out += f'<line x1="{gx + 14}" y1="{oy - 2}" x2="{gx + 14}" y2="{y + bh + 10}" stroke="{GREEN}" stroke-width="2" marker-end="url(#ah-green)"/>'
    out += text(gx + 22, (y + bh + 6 + oy) // 2 + 4, "ToolResult", 12, GREEN)
    out += "</svg>\n"
    return out


# ----------------------------------------------------------------------
# 3. permissions — 三级权限模型
# ----------------------------------------------------------------------
def chart_permissions() -> str:
    W, H = 1240, 560
    out = svg_open(W, H, "三级权限模型")
    out += DEFS
    out += title_block(W, "三级权限：数值 rank 比较，向上兼容、向下拦截",
                       "定义于 src/interfaces.py：public=0，user=1，admin=2；放行条件 user_level.rank() ≥ 工具要求 rank()")

    cards = [
        ("PUBLIC", "rank 0", "只读操作", "list_directory / read_file", GRAY_BG, "#94a3b8", 0),
        ("USER", "rank 1", "文件操作", "copy / move / delete / create / write", BLUE_BG, BLUE, 1),
        ("ADMIN", "rank 2", "执行命令", "run_command（受黑名单+保护路径约束）", AMBER_BG, AMBER, 2),
    ]
    cw, ch_base = 320, 150
    for i, (name, rank, kind, tools, fill, stroke, lift) in enumerate(cards):
        x = 60 + i * (cw + 30)
        y = 250 - lift * 26
        h = ch_base + lift * 26
        out += box(x, y, cw, h, fill, stroke, rx=12)
        out += text(x + 24, y + 42, name, 22, stroke, "700")
        out += text(x + cw - 24, y + 40, rank, 15, SUB, "600", anchor="end")
        out += text(x + 24, y + 76, kind, 15, INK, "600")
        out += text(x + 24, y + 104, tools, 12.5, SUB)
    out += text(60 + cw + 30 + cw // 2, 118, "调用时传入 user_level", 13, SUB, anchor="middle")
    out += arrow_h(60 + cw + 30 + cw // 2 - 60, 132, 60 + cw + 30 + cw // 2 + 60, BLUE)

    # 底部规则框（卡片底边在 y=400，下移避让）
    rx0, ry0 = 60, 418
    out += box(rx0, ry0, W - 120, 100, "#f8fafc", LINE, rx=10)
    out += text(rx0 + 24, ry0 + 32, "示例：USER（rank 1）调用 run_command（要求 rank 2）", 14, INK, "600")
    out += text(rx0 + 24, ry0 + 60, "1 < 2 → 拒绝执行，返回 ToolResult(success=False, error='权限不足: run_command 需要 admin 权限')", 12.5, RED)
    out += text(rx0 + 24, ry0 + 84, "建议：AppAgent 平时以 USER 运行，仅在用户确认后临时提权 ADMIN", 12.5, SUB)
    out += "</svg>\n"
    return out


# ----------------------------------------------------------------------
# 4. security — 四层安全闸门
# ----------------------------------------------------------------------
def chart_security() -> str:
    W, H = 1240, 600
    cx = 380
    out = svg_open(W, H, "四层安全闸门")
    out += DEFS
    out += title_block(W, "四层安全：一次调用必须依次闯过的闸门",
                       "全部通过 → 真实执行并统计；任一失败 → 统一返回 ToolResult.fail()，绝不带病执行")

    entry_y = 112
    out += box(cx - 130, entry_y, 260, 44, GRAY_BG, LINE, rx=8)
    out += text(cx, entry_y + 28, "registry.call(name, params)", 14, INK, "600", anchor="middle")

    gates = [
        ("① 工具存在性", "name 不在注册表 → 工具未注册", 180),
        ("② 权限校验", "user_level.rank() < 工具要求 → 权限不足", 248),
        ("③ 危险命令黑名单", "rm -rf / 等命中 → 拒绝执行（空白归一化防绕过）", 316),
        ("④ 受保护路径拦截", "/etc、/usr、C:\\Windows 等全入口拦截 → 受保护", 384),
        ("⑤ 参数 schema 预检", "缺参/类型错 → 参数错误", 452),
    ]
    lane_x = 760
    for i, (name, desc, gy) in enumerate(gates):
        out += box(cx - 150, gy, 300, 52, BLUE_BG, BLUE, rx=10)
        out += text(cx, gy + 22, name, 15, BLUE, "700", anchor="middle")
        out += text(cx, gy + 41, desc, 11.5, SUB, anchor="middle")
        out += arrow_v(cx, gy - 24 if i == 0 else gy - 16, gy - 2)
        # fail 分支
        fy = gy + 26
        out += f'<line x1="{cx + 150}" y1="{fy}" x2="{lane_x - 10}" y2="{fy}" stroke="{RED}" stroke-width="1.8" stroke-dasharray="5,4" marker-end="url(#ah-red)"/>'
        out += text(cx + 162, fy - 7, "fail", 11, RED)

    # 失败汇聚框：覆盖全部门门的 fail 红线（y 206~478）
    out += box(lane_x, 200, 320, 280, RED_BG, RED, rx=10)
    out += text(lane_x + 160, 244, "ToolResult(success=False)", 15, RED, "700", anchor="middle")
    out += text(lane_x + 160, 276, "error 带分类前缀：", 12.5, RED, anchor="middle")
    out += text(lane_x + 160, 298, "工具未注册 / 权限不足 / 参数错误 /", 12.5, RED, anchor="middle")
    out += text(lane_x + 160, 320, "拒绝执行 / 受保护 —— 组3 读前缀即可自愈", 12.5, RED, anchor="middle")
    out += text(lane_x + 160, 352, "· 拦截发生在统计之前，不产生调用记录", 11.5, SUB, anchor="middle")
    out += text(lane_x + 160, 374, "· 黑名单与保护路径即使 ADMIN 提权也拦截", 11.5, SUB, anchor="middle")

    # 通过 → 执行
    out += arrow_v(cx, 504, 528, GREEN)
    out += box(cx - 170, 530, 340, 44, GREEN_BG, GREEN, rx=10)
    out += text(cx, 548, "执行真实工具函数 → 计时 → stats.record()", 13.5, GREEN, "700", anchor="middle")
    out += text(cx, 566, "统计在执行之后：成功与失败（工具内部）都如实落盘", 11, SUB, anchor="middle")
    out += "</svg>\n"
    return out


# ----------------------------------------------------------------------
# 5. flow — 命令流转路线（跨文件）
# ----------------------------------------------------------------------
def chart_flow() -> str:
    W, H = 1240, 540
    out = svg_open(W, H, "命令流转路线")
    out += DEFS
    out += title_block(W, "一次 run_command 调用的完整流转（8 步）",
                       "以 registry.call(\"run_command\", {\"cmd\": \"echo hello\"}) 为例，对应 presentation/04 讲解路线")

    lanes = [
        ("main.py", 60, 250, "调用入口（组3 同样写法）"),
        ("tool_registry.py", 400, 260, "调度中枢：检查 + 计时 + 统计"),
        ("default_tools.py", 760, 240, "真实执行：黑名单 → subprocess"),
        ("组3 / 演示输出", 1050, 210, "拿到统一返回"),
    ]
    for name, x, w, cap in lanes:
        out += text(x + w // 2, 118, name, 15, BLUE, "700", anchor="middle")
        out += f'<line x1="{x}" y1="126" x2="{x + w - 20}" y2="126" stroke="{LINE}" stroke-width="3"/>\n'
        out += text(x + w // 2, 146, cap, 11.5, SUB, anchor="middle")

    steps = [
        (1, "发起调用", "registry.call(name, params, user_level)", 60, 190, 250, GRAY_BG, LINE, INK),
        (2, "存在性检查", "name 在 _tools 字典中？", 400, 190, 260, BLUE_BG, BLUE, BLUE),
        (3, "权限比较", "user_level.rank() >= tool rank ?", 400, 270, 260, BLUE_BG, BLUE, BLUE),
        (4, "解包执行", "self._tools[name](**params)", 400, 350, 260, BLUE_BG, BLUE, BLUE),
        (5, "黑名单检查", "空白归一化后匹配危险命令", 760, 190, 240, AMBER_BG, AMBER, AMBER),
        (6, "OS 级执行", "subprocess.run(cmd, timeout)", 760, 270, 240, GREEN_BG, GREEN, GREEN),
        (7, "原始返回", '{"success": True, "result": "hello\\n"}', 760, 350, 240, GRAY_BG, LINE, INK),
        (8, "计时+统计+包装", "stats.record() → ToolResult.to_dict()", 400, 440, 260, BLUE_BG, BLUE, BLUE),
    ]
    for n, name, code, x, y, w, fill, stroke, ink in steps:
        out += box(x, y, w, 62, fill, stroke, rx=10)
        out += text(x + 14, y + 25, f"{n}. {name}", 13.5, ink, "700")
        out += text(x + 14, y + 47, code, 11, SUB)

    def conn(x1, y1, x2, y2, color=SUB, dash=""):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<path d="M {x1} {y1} C {x1 + 40} {y1}, {x2 - 40} {y2}, {x2} {y2}" '
                f'fill="none" stroke="{color}" stroke-width="1.8"{d} marker-end="url(#ah)"/>\n')

    out += conn(310, 221, 400, 221)                      # 1→2
    out += arrow_v(530, 252, 270)                        # 2→3
    out += arrow_v(530, 332, 350)                        # 3→4
    out += conn(660, 381, 760, 221)                      # 4→5（解包执行→黑名单）
    out += arrow_v(880, 252, 270)                        # 5→6
    out += arrow_v(880, 332, 350)                        # 6→7
    out += conn(760, 381, 660, 470)                      # 7→8 回到 registry
    out += conn(400, 471, 310, 240, dash="5,4")          # 8→组3 返回
    out += text(400, 528, "最终统一返回：ToolResult.to_dict() = {success, result/error}", 12.5, GREEN, "600")
    out += "</svg>\n"
    return out


CHARTS = {
    "benchmark": chart_benchmark,
    "pipeline": chart_pipeline,
    "permissions": chart_permissions,
    "security": chart_security,
    "flow": chart_flow,
}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for name, fn in CHARTS.items():
        path = os.path.join(OUT, f"{name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(fn())
        print(f"[OK] {path}")


if __name__ == "__main__":
    main()
