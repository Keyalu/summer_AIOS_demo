"""
test_highpressure.py — 高压特性测试

覆盖 Week3 高压优化方案的新能力：
1. list_directory 的 scandir + 分页游标（方案②③）
2. BufferedToolStats 缓冲统计（方案①）
3. BatchExecutor Worker池 + 背压（方案④）
4. find_duplicate_files size 预分组（方案⑤）
5. RateLimiter 令牌桶限速 + CircuitBreaker 失败率熔断（方案⑥）
6. organize_downloads 并行搬运（技能并行化）
"""

import json
import shutil
import tempfile
import threading
import time
from pathlib import Path

import pytest

from src import (
    BatchExecutor, BufferedToolStats, CircuitBreaker, PermissionLevel,
    RateLimiter, SkillLibrary, ToolRegistry,
)


def make_noop():
    def noop(x: int = 1) -> dict:
        return {"success": True, "result": x}
    return noop


# ==============================================================
# 1. list_directory：scandir + 分页
# ==============================================================
class TestListDirectoryPaging:
    def setup_method(self):
        self.reg = ToolRegistry()
        self.tmp = Path(tempfile.mkdtemp(prefix="hp_list_"))
        for i in range(250):
            (self.tmp / f"f_{i:04d}.txt").write_text("x" * (i + 1))

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_behavior_unchanged(self):
        """不带分页参数时，行为与旧版一致（count=总数，entries 前 100 条）。"""
        r = self.reg.call("list_directory", {"path": str(self.tmp)}, PermissionLevel.PUBLIC)
        assert r.success
        assert r.result["count"] == 250
        assert r.result["returned"] == 100
        assert len(r.result["entries"]) == 100
        assert r.result["has_more"] is True
        assert r.result["next_offset"] == 100

    def test_pagination_covers_all_without_gap(self):
        """翻页遍历：250 条按 60/页翻，必须不重不漏。"""
        seen = []
        offset = 0
        while True:
            r = self.reg.call(
                "list_directory",
                {"path": str(self.tmp), "offset": offset, "limit": 60},
                PermissionLevel.PUBLIC,
            )
            assert r.success
            seen.extend(e["name"] for e in r.result["entries"])
            if not r.result["has_more"]:
                break
            offset = r.result["next_offset"]
        assert len(seen) == 250
        assert len(set(seen)) == 250

    def test_offset_beyond_total(self):
        """offset 超出总数：返回空页，has_more=False。"""
        r = self.reg.call(
            "list_directory",
            {"path": str(self.tmp), "offset": 9999, "limit": 10},
            PermissionLevel.PUBLIC,
        )
        assert r.success
        assert r.result["returned"] == 0
        assert r.result["has_more"] is False
        assert r.result["next_offset"] is None

    def test_entry_types_and_sizes(self):
        """目录/文件类型与 size 正确（scandir 版本语义不变）。"""
        small = self.tmp / "_small"
        small.mkdir()
        (small / "a.txt").write_text("12345")     # 5 字节
        (small / "b.bin").write_bytes(b"\x00" * 7)  # 7 字节
        r = self.reg.call("list_directory", {"path": str(small)}, PermissionLevel.PUBLIC)
        assert r.success
        by_name = {e["name"]: e for e in r.result["entries"]}
        assert set(by_name) == {"a.txt", "b.bin"}
        types = {e["name"]: e["type"] for e in by_name.values()}
        assert types["a.txt"] == "file"
        assert types["b.bin"] == "file"
        sizes = {e["name"]: e["size"] for e in r.result["entries"]}
        assert sizes["a.txt"] == 5
        assert sizes["b.bin"] == 7

    def test_bad_offset_limit(self):
        r = self.reg.call(
            "list_directory",
            {"path": str(self.tmp), "offset": "abc"},
            PermissionLevel.PUBLIC,
        )
        assert not r.success
        assert "参数错误" in r.error


# ==============================================================
# 2. BufferedToolStats：缓冲统计
# ==============================================================
class TestBufferedStats:
    def make_reg(self, **kw):
        stats = BufferedToolStats(**kw)
        reg = ToolRegistry(stats=stats)
        reg.register("noop", make_noop())
        return reg, stats

    def test_counters_match_toolstats_semantics(self):
        reg, stats = self.make_reg()
        for i in range(50):
            reg.call("noop", {"x": i}, PermissionLevel.USER)
        assert stats.total_calls() == 50
        assert stats.tool_stats("noop")["success"] == 50
        assert stats.success_rate("noop") == pytest.approx(1.0)

    def test_flush_persists_valid_json(self, tmp_path):
        log = tmp_path / "stats.json"
        reg, stats = self.make_reg(log_path=str(log))
        for i in range(30):
            reg.call("noop", {"x": i}, PermissionLevel.USER)
        stats.flush()
        data = json.loads(log.read_text(encoding="utf-8"))
        assert sum(c["calls"] for c in data["counters"].values()) == 30
        assert len(data["records"]) == 30

    def test_ring_buffer_caps_memory(self):
        reg, stats = self.make_reg(max_records=50)
        for i in range(300):
            reg.call("noop", {"x": i}, PermissionLevel.USER)
        assert stats.total_calls() == 300            # 计数不受影响
        assert len(stats.recent_records(1000)) == 50  # 明细只留最近 50 条

    def test_thread_safety_no_lost_updates(self):
        reg, stats = self.make_reg()
        THREADS, PER = 16, 100

        def worker(_):
            for j in range(PER):
                reg.call("noop", {"x": j}, PermissionLevel.USER)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert stats.total_calls() == THREADS * PER


# ==============================================================
# 3. BatchExecutor：Worker 池 + 背压
# ==============================================================
class TestBatchExecutor:
    def setup_method(self):
        self.reg = ToolRegistry()
        self.reg.register("noop", make_noop())

    def test_submit_and_drain(self):
        with BatchExecutor(self.reg, workers=4, max_queue=100) as ex:
            for i in range(200):
                assert ex.submit("noop", {"x": i}, PermissionLevel.USER) is True
            results = ex.drain()
        assert len(results) == 200
        assert all(r.success for r in results)
        s = ex.stats()
        assert s["submitted"] == 200 and s["succeeded"] == 200 and s["rejected"] == 0

    def test_backpressure_rejects_when_full(self):
        """队列满时 submit 阻塞等待，超时返回 False（背压拒绝）。"""
        started = threading.Event()
        release = threading.Event()

        def blocker() -> dict:
            started.set()
            release.wait(timeout=5)
            return {"success": True, "result": "done"}

        self.reg.register("blocker", blocker)
        ex = BatchExecutor(self.reg, workers=1, max_queue=1)
        try:
            assert ex.submit("blocker") is True
            assert started.wait(timeout=5)                       # worker 已被占用
            assert ex.submit("blocker") is True                  # 占据队列最后 1 格
            assert ex.submit("blocker", block_timeout=0.2) is False  # 背压拒绝
        finally:
            release.set()
            results = ex.drain()
            ex.shutdown()
        assert len(results) == 2
        assert ex.stats()["rejected"] == 1

    def test_worker_survives_tool_crash(self):
        """工具抛异常不杀死 worker，后续任务照常执行。"""

        def boom() -> dict:
            raise RuntimeError("boom")

        self.reg.register("boom", boom)
        with BatchExecutor(self.reg, workers=2, max_queue=10) as ex:
            ex.submit("boom")
            ex.submit("noop", {"x": 1}, PermissionLevel.USER)
            results = ex.drain()
        assert len(results) == 2
        assert results[0].success is False and "boom" in results[0].error
        assert results[1].success is True


# ==============================================================
# 4. find_duplicate_files：size 预分组
# ==============================================================
class TestDupPregroup:
    def test_finds_duplicates_and_reports_coverage(self):
        tmp = Path(tempfile.mkdtemp(prefix="hp_dup_"))
        try:
            # 30 个唯一文件 + 10 组内容各 2 份 = 50 个文件
            for i in range(30):
                (tmp / f"u_{i:03d}.bin").write_bytes(bytes([i]) * (100 + i))
            for g in range(10):
                content = bytes([200 + g]) * (300 + g)
                (tmp / f"d_{g:03d}_a.bin").write_bytes(content)
                (tmp / f"d_{g:03d}_b.bin").write_bytes(content)

            skills = SkillLibrary()
            r = skills.call_skill("find_duplicate_files", {"path": str(tmp)})
            assert r.success
            assert r.result["scanned"] == 50
            assert r.result["hashed"] == 20            # 只有 size 撞车的 20 个被哈希
            assert r.result["duplicate_groups"] == 10
            assert r.result["total_duplicated_files"] == 20
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_all_unique_hashes_nothing(self):
        """全部唯一（size 互不相同）→ 0 个文件需要算哈希。"""
        tmp = Path(tempfile.mkdtemp(prefix="hp_uniq_"))
        try:
            for i in range(20):
                (tmp / f"u_{i:03d}.bin").write_bytes(bytes([i]) * (50 + i * 3))
            skills = SkillLibrary()
            r = skills.call_skill("find_duplicate_files", {"path": str(tmp)})
            assert r.success
            assert r.result["scanned"] == 20
            assert r.result["hashed"] == 0             # 两级过滤把哈希量降为 0
            assert r.result["duplicate_groups"] == 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ==============================================================
# 5. RateLimiter + CircuitBreaker（方案⑥）
# ==============================================================
class TestRateLimiter:
    def test_paces_execution(self):
        """限速 50/s 执行 10 个任务，总耗时应 >= ~0.18s（9 个间隔）。"""
        reg = ToolRegistry()
        reg.register("noop", make_noop())
        limiter = RateLimiter(50)
        with BatchExecutor(reg, workers=4, max_queue=50,
                           rate_limiter=limiter) as ex:
            t0 = time.monotonic()
            for i in range(10):
                ex.submit("noop", {"x": i}, PermissionLevel.USER)
            results = ex.drain()
            elapsed = time.monotonic() - t0
        assert len(results) == 10
        assert all(r.success for r in results)
        assert elapsed >= 0.15          # 不限速时 10 个 noop 只要几毫秒
        assert elapsed < 5              # 也不能卡死

    def test_invalid_rate_rejected(self):
        with pytest.raises(ValueError):
            RateLimiter(0)
        with pytest.raises(ValueError):
            RateLimiter(-5)


class TestCircuitBreaker:
    def setup_method(self):
        self.reg = ToolRegistry()
        self.calls = 0
        self.lock = threading.Lock()

        def always_fail() -> dict:
            with self.lock:
                self.calls += 1
            return {"success": False, "error": "模拟系统性故障"}

        self.reg.register("always_fail", always_fail)

    def test_trips_on_high_failure_rate(self):
        """全部失败时熔断打开：后续任务快速失败，不再真正执行。"""
        cb = CircuitBreaker(failure_threshold=0.5, min_samples=10, cooldown=60)
        with BatchExecutor(self.reg, workers=2, max_queue=100,
                           circuit_breaker=cb) as ex:
            for _ in range(50):
                ex.submit("always_fail")
            results = ex.drain()
        assert len(results) == 50
        # 熔断后真正执行的次数远小于 50（约 min_samples + 少量在途任务）
        assert self.calls < 30
        tripped = [r for r in results if "熔断" in (r.error or "")]
        assert len(tripped) > 0
        assert ex.stats()["tripped"] == len(tripped)

    def test_healthy_traffic_never_trips(self):
        """全部成功时熔断器永不打开。"""
        self.reg.register("noop", make_noop())
        cb = CircuitBreaker(failure_threshold=0.5, min_samples=10)
        with BatchExecutor(self.reg, workers=4, max_queue=100,
                           circuit_breaker=cb) as ex:
            for i in range(100):
                ex.submit("noop", {"x": i}, PermissionLevel.USER)
            results = ex.drain()
        assert all(r.success for r in results)
        assert ex.stats()["tripped"] == 0
        assert ex.stats()["circuit_open"] is False

    def test_reset_recovers(self):
        cb = CircuitBreaker(failure_threshold=0.5, min_samples=5, cooldown=600)
        for _ in range(6):
            cb.record(False)
        assert cb.is_open() is True
        cb.reset()
        assert cb.is_open() is False

    def test_cooldown_auto_half_open(self):
        """冷却结束后自动半开（放行试探）。"""
        cb = CircuitBreaker(failure_threshold=0.5, min_samples=5, cooldown=0.2)
        for _ in range(6):
            cb.record(False)
        assert cb.is_open() is True
        time.sleep(0.3)
        assert cb.is_open() is False      # 冷却已过 → 半开


class TestBatchPresets:
    def test_preset_creates_working_executor(self):
        reg = ToolRegistry()
        reg.register("noop", make_noop())
        for name in ("light", "medium", "high"):
            with BatchExecutor.preset(reg, name) as ex:
                for i in range(20):
                    ex.submit("noop", {"x": i}, PermissionLevel.USER)
                results = ex.drain()
            assert len(results) == 20
            assert all(r.success for r in results)

    def test_preset_rejects_unknown_name(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError):
            BatchExecutor.preset(reg, "ultra")


# ==============================================================
# 6. organize_downloads 并行搬运
# ==============================================================
class TestParallelOrganize:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hp_org_"))
        # 200 个文件，覆盖多个分类 + 一批同分类文件
        for i in range(80):
            (self.tmp / f"doc_{i:03d}.txt").write_text(f"doc{i}")
        for i in range(60):
            (self.tmp / f"pic_{i:03d}.png").write_bytes(b"\x89PNG")
        for i in range(40):
            (self.tmp / f"song_{i:03d}.mp3").write_bytes(b"ID3")
        for i in range(20):
            (self.tmp / f"misc_{i:03d}.xyz").write_text("?")

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, workers: int):
        skills = SkillLibrary()
        return skills.call_skill(
            "organize_downloads", {"path": str(self.tmp), "workers": workers})

    def test_parallel_result_matches_serial(self):
        """并行与串行的整理结果一致：200 个文件全部正确分类、零丢失。"""
        r = self._run(workers=8)
        assert r.success
        assert r.result["total_moved"] == 200
        assert r.result["workers"] == 8
        cats = {k: len(v) for k, v in r.result["categories"].items()}
        assert cats == {"文档": 80, "图片": 60, "音频": 40, "其他": 20}
        # 物理验证：文件真的各就各位
        assert len(list((self.tmp / "文档").iterdir())) == 80
        assert len(list((self.tmp / "其他").iterdir())) == 20
        # 根目录不再残留任何普通文件
        assert [f for f in self.tmp.iterdir() if f.is_file()] == []

    def test_workers_default_is_serial_compatible(self):
        """workers=1（默认）时返回结构与旧版完全一致。"""
        r = self._run(workers=1)
        assert r.success
        assert r.result["total_moved"] == 200
        assert r.result["workers"] == 1
        assert set(r.result) >= {"path", "total_moved", "categories", "skipped"}
