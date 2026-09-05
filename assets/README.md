# assets/ — 可视化产物目录

本目录存放分组四的可视化交付物，全部由纯标准库脚本生成（零第三方依赖）。

## 内容清单

| 文件 | 说明 | 再生成方式 |
|------|------|-----------|
| `charts/benchmark.png/.svg` | Week3 高压优化实测收益（对数轴前后对比，2146×/13.8×/177.7×） | `python tools/gen_charts.py` |
| `charts/pipeline.png/.svg` | 五组流水线与组4位置 | 同上 |
| `charts/permissions.png/.svg` | 三级权限模型（rank 0/1/2） | 同上 |
| `charts/security.png/.svg` | 四层安全闸门纵深 | 同上 |
| `charts/flow.png/.svg` | 一次 run_command 调用的 8 步流转 | 同上 |
| `dashboard.html` | 审计看板（单文件、离线可用，内嵌 stats 数据） | `python tools/gen_dashboard.py` |
| `stats_demo.json` | 看板数据源：一次模拟 Agent 会话的真实统计 | `gen_dashboard.py` 自动生成 |
| `dashboard_preview.png` | 看板截图（可直接贴 PPT/报告） | 浏览器截取 |
| `gui_tools.png` / `gui_stats.png` / `gui_mcp.png` | GUI 三个页签的实测截图 | 浏览器截取 |
| `archify/group4-pipeline.html` | 交互式五组流水线图（用开源技能 [archify](https://github.com/tt-a1i/archify) 生成：深浅主题/缩放/搜索/演示模式/导出，双击即开） | 改 `archify/*.architecture.json` 后用 archify 重渲染 |
| `archify/group4-internal.html` | 交互式组4内部模块图（12 模块 + 12 条数据流：Mock 双轨/Registry/Skills/MCP/Stats/GUI） | 同上 |

## PNG 导出方式

SVG 由 `tools/gen_charts.py` 生成后，两种方式得到 PNG：

1. **GUI 服务自动渲染**（推荐）：`python gui/server.py` 后访问
   `http://127.0.0.1:8765/charts/view/<名称>`，浏览器截图（视口设为图表原始尺寸）；
2. 用任意浏览器/Office/Inkscape 打开 SVG 另存为 PNG。

> 注意：SVG 是源文件（可无损缩放、可改配色），PNG 是导出产物；
> 建议改动一律改 `tools/gen_charts.py` 再重新生成，不要手改 SVG。

## GUI 响应模块

`gui/server.py` 是给 Tools 层套的本地可视化操作台（工具台/技能台/统计看板/MCP 四页签），
详见根目录《快速开始.md》与 `gui/server.py` 文件头说明。
