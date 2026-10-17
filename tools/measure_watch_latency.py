import os
import sys
import time
import shutil
import tempfile
import statistics
import psutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.db import init_db
from backend.indexing.service import IndexingService
from backend.search.keyword_search import keyword_search
from backend.search.semantic_search import semantic_search

def measure_watch_latency(n_files: int = 20):
    proc = psutil.Process(os.getpid())
    idle_mem_before = proc.memory_info().rss / (1024 * 1024)

    temp_dir = tempfile.mkdtemp(prefix="compass_watch_measure_")
    os.environ["COMPASS_DATA_DIR"] = os.path.join(temp_dir, "data")
    init_db()

    monitored_root = os.path.join(temp_dir, "monitored")
    os.makedirs(monitored_root, exist_ok=True)

    print("--- Compass File Watcher Latency Benchmark ---")
    print(f"Monitoring folder: {monitored_root}")
    print(f"Test batch size: N={n_files} files")
    print(f"Idle memory before: {idle_mem_before:.2f} MB")

    service = IndexingService(
        quiet_period=1.5,
        startup_delay=0.0
    )
    service.start()
    service.add_root(monitored_root)

    # Let watcher settle
    time.sleep(1.0)

    keyword_latencies = []
    semantic_latencies = []

    print("\nCreating/modifying files and observing time-to-retrieval...")

    for i in range(n_files):
        unique_token = f"benchmark_token_xyz_{i}_{int(time.time() * 1000)}"
        filename = f"watch_test_{i}.txt"
        filepath = os.path.join(monitored_root, filename)
        content = (
            f"Document index test number {i}. "
            f"This document contains a unique secret key {unique_token} "
            f"designed to evaluate the precise latency of the debounced watchdog observer and semantic encoder."
        )

        t0 = time.perf_counter()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        # 1. Poll for keyword search availability
        kw_found = False
        t_kw = None
        timeout = 15.0
        while time.perf_counter() - t0 < timeout:
            res = keyword_search(unique_token, limit=5)
            if any(unique_token in r.get("snippet", "") or unique_token in r.get("content", "") or filename == r.get("filename") for r in res):
                t_kw = time.perf_counter() - t0
                kw_found = True
                break
            time.sleep(0.05)

        # 2. Poll for semantic search availability
        sem_found = False
        t_sem = None
        while time.perf_counter() - t0 < timeout:
            res = semantic_search(f"secret key {unique_token}", limit=5)
            if any(filename in r.get("filename", "") for r in res):
                t_sem = time.perf_counter() - t0
                sem_found = True
                break
            time.sleep(0.05)

        if kw_found:
            keyword_latencies.append(t_kw)
        if sem_found:
            semantic_latencies.append(t_sem)

        print(f"  [{i+1}/{n_files}] Keyword: {t_kw:.3f}s | Semantic: {t_sem:.3f}s")
        # Small gap between creates
        time.sleep(0.1)

    idle_mem_after = proc.memory_info().rss / (1024 * 1024)

    service.stop(timeout=2.0)

    # Compute statistics
    def percentile(data, p):
        if not data:
            return 0.0
        k = (len(data) - 1) * p
        f = int(k)
        c = f + 1
        if c < len(data):
            return sorted(data)[f] + (k - f) * (sorted(data)[c] - sorted(data)[f])
        else:
            return sorted(data)[f]

    kw_median = statistics.median(keyword_latencies) if keyword_latencies else 0.0
    kw_p95 = percentile(keyword_latencies, 0.95)

    sem_median = statistics.median(semantic_latencies) if semantic_latencies else 0.0
    sem_p95 = percentile(semantic_latencies, 0.95)

    print("\n--- Latency Benchmark Summary ---")
    print(f"Keyword Search Latency:  Median = {kw_median:.3f} s,  p95 = {kw_p95:.3f} s")
    print(f"Semantic Search Latency: Median = {sem_median:.3f} s,  p95 = {sem_p95:.3f} s")
    print(f"Memory before index: {idle_mem_before:.2f} MB")
    print(f"Memory after index:  {idle_mem_after:.2f} MB")
    print(f"Memory Delta:        {idle_mem_after - idle_mem_before:.2f} MB")

    # Clean up
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    return {
        "n_files": n_files,
        "kw_median": kw_median,
        "kw_p95": kw_p95,
        "sem_median": sem_median,
        "sem_p95": sem_p95,
        "idle_mem_before": idle_mem_before,
        "idle_mem_after": idle_mem_after
    }

if __name__ == "__main__":
    measure_watch_latency(n_files=20)
