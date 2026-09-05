"""
benchmark_stress.py — 高压请求压测脚本

模拟 8 类高压场景，暴露当前实现的性能瓶颈，并用 A/B 对比验证优化方案：

  S1  万级工具注册与查询     （Registry 容量上限）
  S2  万级文件 list_directory（目录遍历 + stat 放大）
  S3  万级文件 organize      （技能层批量文件搬运）
  S4  万级文件 查重          （CPU 密集：MD5 分块哈希）
  S5  多线程并发调用         （线程安全验证：计数是否丢失）
  S6  统计持久化 O(n²) 放大  （每次 record 全量重写 JSON 的代价）
  S7  MCP JSON-RPC 吞吐      （协议层开销）
  S8  统计内存占用           （20 万条记录的内存增长）

  A1  [对比] iterdir+stat  vs os.scandir     （目录遍历优化）
  A2  [对比] 每次 record 落盘 vs 缓冲批量落盘 （统计 IO 优化）

运行: python stress/benchmark_stress.py
输出: 终端表格 + stress/results.json
"""

from __future__ import annotations
import json
import os
import shutil
import sys
import tempfile
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import ToolRegistry, SkillLibrary, MCPConnector, ToolStats, PermissionLevel  # noqa: E402
from src.stats_buffered import BufferedToolStats  # noqa: E402

RESULTS: list[dict] = []


def bench(sid: str, name: str, fn, count: int | None = None) -> dict:
    t0 = time.perf_counter()
    detail: dict = {}
    err = None
    try:
        detail = fn() or {}
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
    dt = time.perf_counter() - t0
    ops = count if count is not None else detail.pop("count", 0)
    row = {
        "id": sid, "scenario": name, "time_s": round(dt, 3),
        "ops": ops,
        "throughput_ops_per_s": round(ops / dt, 1) if dt > 0 and ops else None,
        "error": err, **detail,
    }
    RESULTS.append(row)
    # 增量保存，防止超时丢数据
    with open(Path(__file__).parent / "results.json", "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    line = f"[{sid}] {name}: {dt:.2f}s"
    if ops:
        line += f" | {ops} ops | {ops / dt:,.0f} ops/s"
    for k, v in detail.items():
        line += f" | {k}={v}"
    if err:
        line += f" | ERROR: {err}"
    print(line, flush=True)
    return row


def make_noop():
    def noop(x: int = 1) -> dict:
        return {"success": True, "result": x}
    return noop


# ==============================================================
# S1 万级工具注册
# ==============================================================
def s1_register_10k():
    reg = ToolRegistry()
    base = reg.count()
    for i in range(10000):
        reg.register(f"tool_{i:05d}", make_noop())
    t0 = time.perf_counter()
    for _ in range(10000):
        reg.has("tool_05000")
    lookup_us = (time.perf_counter() - t0) * 1e6 / 10000
    return {"count": 10000, "total_registered": reg.count(),
            "has_lookup_avg_us": round(lookup_us, 2)}


def s1b_list_tools_10k():
    reg = ToolRegistry()
    for i in range(10000):
        reg.register(f"tool_{i:05d}", make_noop())
    t0 = time.perf_counter()
    schemas = reg.list_tools()
    return {"count": len(schemas)}


# ==============================================================
# 文件夹造数据辅助
# ==============================================================
def create_files(dirpath: Path, n: int, size: int = 64, groups: int = 0) -> Path:
    """在 dirpath 下创建 n 个文件。groups>0 时让内容重复（供查重）。"""
    dirpath.mkdir(parents=True, exist_ok=True)
    contents = [os.urandom(size) for _ in range(max(groups, 1))]
    for i in range(n):
        ext = [".txt", ".jpg", ".mp3", ".pdf", ".zip", ".png", ".csv", ".md"][i % 8]
        data = contents[i % len(contents)] if groups else os.urandom(size)
        (dirpath / f"file_{i:06d}{ext}").write_bytes(data)
    return dirpath


# ==============================================================
# S2/S3/S4 万级文件
# ==============================================================
N_LIST = 10000
N_ORG = 3000
N_DUP = 2000


def s2_list_directory_10k():
    tmp = Path(tempfile.mkdtemp(prefix="stress_list_"))
    try:
        create_files(tmp, N_LIST)
        reg = ToolRegistry()
        r = reg.call("list_directory", {"path": str(tmp)}, PermissionLevel.ADMIN)
        assert r.success, r.error
        return {"count": N_LIST, "returned_entries": r.result["count"]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def s3_organize_3000():
    tmp = Path(tempfile.mkdtemp(prefix="stress_org_"))
    try:
        create_files(tmp, N_ORG)
        skills = SkillLibrary()
        r = skills.call_skill("organize_downloads", {"path": str(tmp)})
        assert r.success, r.error
        return {"count": N_ORG, "moved": r.result["total_moved"]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def s4_find_dup_2000():
    tmp = Path(tempfile.mkdtemp(prefix="stress_dup_"))
    try:
        create_files(tmp, N_DUP, size=4096, groups=50)  # 50 组重复内容
        skills = SkillLibrary()
        r = skills.call_skill("find_duplicate_files", {"path": str(tmp)})
        assert r.success, r.error
        return {"count": N_DUP, "dup_groups": r.result["duplicate_groups"]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ==============================================================
# S5 并发线程安全
# ==============================================================
def s5_concurrent_8000():
    reg = ToolRegistry(ToolStats())  # 显式挂载统计，验证计数竞态
    reg.register("noop", make_noop())
    THREADS, PER = 16, 500
    expected = THREADS * PER

    def worker(_):
        for j in range(PER):
            reg.call("noop", {"x": j}, PermissionLevel.USER)

    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        list(ex.map(worker, range(THREADS)))

    recorded = reg._stats.total_calls()
    return {"count": expected, "recorded": recorded,
            "lost_updates": expected - recorded}


def s5b_concurrent_with_disk():
    """并发 + 磁盘持久化：验证 _save 文件写入竞态是否丢数据/损坏。"""
    log = ROOT / "stress" / "_tmp_stats.json"
    if log.exists():
        log.unlink()
    try:
        reg = ToolRegistry(ToolStats(log_path=str(log)))
        reg.register("noop", make_noop())
        THREADS, PER = 16, 125  # 2000 次，O(n²) 下已足够暴露问题
        expected = THREADS * PER

        def worker(_):
            for j in range(PER):
                reg.call("noop", {"x": j}, PermissionLevel.USER)

        with ThreadPoolExecutor(max_workers=THREADS) as ex:
            list(ex.map(worker, range(THREADS)))

        recorded_mem = reg._stats.total_calls()
        ok_json = False
        try:
            with open(log, encoding="utf-8") as f:
                data = json.load(f)
            ok_json = True
            recorded_disk = sum(c["calls"] for c in data["counters"].values())
        except Exception:
            recorded_disk = -1
        return {"count": expected, "recorded_mem": recorded_mem,
                "recorded_disk": recorded_disk, "json_valid": ok_json,
                "lost_in_mem": expected - recorded_mem}
    finally:
        if log.exists():
            log.unlink()


# ==============================================================
# S6 统计持久化 O(n²) 放大
# ==============================================================
def s6_stats_quadratic():
    out = {"detail": {}}
    for n in (250, 500, 1000):
        log = ROOT / "stress" / f"_tmp_q_{n}.json"
        if log.exists():
            log.unlink()
        try:
            reg = ToolRegistry(ToolStats(log_path=str(log)))
            reg.register("noop", make_noop())
            t0 = time.perf_counter()
            for i in range(n):
                reg.call("noop", {"x": i}, PermissionLevel.USER)
            out["detail"][f"{n}条"] = round(time.perf_counter() - t0, 3)
        finally:
            if log.exists():
                log.unlink()
    return out


# ==============================================================
# S7 MCP 吞吐
# ==============================================================
def s7_mcp_5000():
    reg = ToolRegistry()
    reg.register("noop", make_noop())
    mcp = MCPConnector()
    t0 = time.perf_counter()
    for i in range(5000):
        r = mcp.mock_jsonrpc_call(reg, "noop", {"x": i})
        assert r["jsonrpc"] == "2.0"
    return {"count": 5000}


# ==============================================================
# S8 统计内存
# ==============================================================
def s8_memory_200k():
    tracemalloc.start()
    stats = ToolStats()
    reg = ToolRegistry(stats)
    reg.register("noop", make_noop())
    for i in range(200000):
        reg.call("noop", {"x": i, "note": "payload" * 4}, PermissionLevel.USER)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"count": 200000, "peak_memory_mb": round(peak / 1024 / 1024, 1)}


# ==============================================================
# A1 [对比] iterdir+stat vs scandir
# ==============================================================
def a1_scandir_vs_iterdir():
    tmp = Path(tempfile.mkdtemp(prefix="stress_ab1_"))
    try:
        N_AB1 = 3000
        create_files(tmp, N_AB1)
        from src.default_tools import list_directory as orig_impl

        # --- 当前实现（Path.iterdir + 每文件 stat）---
        t0 = time.perf_counter()
        base = tmp
        entries_old = 0
        for p in sorted(base.iterdir()):
            entries_old += 1
            _ = p.is_dir(), (p.stat().st_size if p.is_file() else None)
        t_old = time.perf_counter() - t0

        # --- 优化实现（os.scandir，Windows 上 stat 信息随目录项免费返回）---
        t0 = time.perf_counter()
        entries_new = 0
        with os.scandir(base) as it:
            for e in it:
                entries_new += 1
                _ = e.is_dir(), (e.stat().st_size if e.is_file() else None)
        t_new = time.perf_counter() - t0

        return {"count": N_AB1,
                "iterdir_s": round(t_old, 3), "scandir_s": round(t_new, 3),
                "speedup_x": round(t_old / t_new, 1) if t_new > 0 else None}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ==============================================================
# A2 [对比] 每次 record 落盘 vs 缓冲批量落盘
# ==============================================================
def a2_buffered_vs_per_record():
    out = {}
    for label, cls, kw in (
        ("per_record", ToolStats, {}),
        ("buffered", BufferedToolStats, {}),
    ):
        log = ROOT / "stress" / f"_tmp_ab2_{label}.json"
        if log.exists():
            log.unlink()
        try:
            reg = ToolRegistry(cls(log_path=str(log), **kw))
            reg.register("noop", make_noop())
            t0 = time.perf_counter()
            for i in range(1000):
                reg.call("noop", {"x": i}, PermissionLevel.USER)
            if hasattr(reg._stats, "flush"):
                reg._stats.flush()
            out[f"{label}_1000条_s"] = round(time.perf_counter() - t0, 3)
        finally:
            if log.exists():
                log.unlink()
    t_old = out["per_record_1000条_s"]
    t_new = out["buffered_1000条_s"]
    out["speedup_x"] = round(t_old / t_new, 1) if t_new > 0 else None
    return out


# ==============================================================
# 主流程
# ==============================================================
def main() -> None:
    print("=" * 78)
    print("高压请求压测 — 分组四 Tools + OS Skills")
    print("=" * 78)

    print("\n--- 压力场景 ---")
    bench("S1", f"注册 1 万个工具", s1_register_10k)
    bench("S1b", "1 万工具时 list_tools 全量列举", s1b_list_tools_10k)
    bench("S2", f"list_directory 扫描 {N_LIST:,} 个文件", s2_list_directory_10k)
    bench("S3", f"organize_downloads 搬运 {N_ORG:,} 个文件", s3_organize_3000)
    bench("S4", f"find_duplicate_files 查重 {N_DUP:,} 个文件", s4_find_dup_2000)
    bench("S5", "16 线程并发 8000 次调用(纯内存)", s5_concurrent_8000)
    bench("S5b", "16 线程并发 4000 次调用(带磁盘持久化)", s5b_concurrent_with_disk)
    bench("S6", "统计落盘 O(n²) 放大曲线(500/1000/2000)", s6_stats_quadratic)
    bench("S7", "MCP JSON-RPC 5000 次调用", s7_mcp_5000)
    bench("S8", "统计 20 万条记录内存占用", s8_memory_200k)

    print("\n--- 优化方案 A/B 对比 ---")
    bench("A1", f"[对比] iterdir+stat vs scandir ({N_LIST:,} 文件)", a1_scandir_vs_iterdir)
    bench("A2", "[对比] 每条落盘 vs 缓冲批量落盘 (2000 条)", a2_buffered_vs_per_record)

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
