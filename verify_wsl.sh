#!/bin/bash
# ============================================================
# WSL Ubuntu 一键复验脚本
# 用法：在 WSL 终端中执行
#   cd ~/linux-agentic-os-group4 && bash verify_wsl.sh
# ============================================================
set -e

echo "=== [1/4] 环境检查 ==="
# 确保使用系统 Python（miniforge 的 python3 没有 pytest）
PY=/usr/bin/python3
$PY --version
$PY -m pytest --version

echo ""
echo "=== [2/4] 运行全部测试（5 套，共 115+ 个）==="
$PY -m pytest tests/ docs/week1/test_week1.py docs/week2/test_week2.py docs/week3/test_week3.py -v --tb=short

echo ""
echo "=== [3/4] 运行演示 ==="
$PY main.py --demo 2>/dev/null || $PY main.py

echo ""
echo "=== [4/4] 快速验证 ==="
$PY quick_check.py

echo ""
echo "=== WSL 复验完成：如上方全绿，则双平台一致 ==="
