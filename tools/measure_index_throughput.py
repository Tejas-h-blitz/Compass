import os
import sys
import time
import shutil
import tempfile
import psutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.paths import repo_root
from backend.models.db import init_db
from backend.scanner.scanner import scan_directory

def measure_index_throughput():
    proc = psutil.Process(os.getpid())
    mem_before_mb = proc.memory_info().rss / (1024 * 1024)

    # Use a temp data dir to avoid corrupting existing data
    temp_dir = tempfile.mkdtemp(prefix="compass_measure_")
    os.environ["COMPASS_DATA_DIR"] = os.path.join(temp_dir, "data")
    init_db()

    corpus_dir = os.path.join(repo_root(), "sample_corpus")
    assert os.path.exists(corpus_dir), "sample_corpus directory does not exist!"

    file_count = len([f for f in os.listdir(corpus_dir) if f != "manifest.json" and os.path.isfile(os.path.join(corpus_dir, f))])

    print(f"--- Compass Indexing Throughput Benchmark ---")
    print(f"Corpus location: {corpus_dir}")
    print(f"Total files: {file_count}")
    print(f"Initial process memory: {mem_before_mb:.2f} MB")

    start_time = time.perf_counter()
    stats = scan_directory(corpus_dir, force=True)
    elapsed = time.perf_counter() - start_time

    mem_after_mb = proc.memory_info().rss / (1024 * 1024)
    peak_mem_mb = mem_after_mb # After model and DB loading

    throughput = file_count / elapsed if elapsed > 0 else 0

    print(f"\n--- Benchmark Results ---")
    print(f"Files scanned/indexed: {stats['scanned']}")
    print(f"Total indexing duration: {elapsed:.3f} s")
    print(f"Indexing throughput: {throughput:.2f} files/s")
    print(f"Final process memory: {mem_after_mb:.2f} MB")
    print(f"Memory delta: {mem_after_mb - mem_before_mb:.2f} MB")

    # Clean up temp data
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    return {
        "file_count": file_count,
        "elapsed_seconds": elapsed,
        "throughput_fps": throughput,
        "peak_mem_mb": peak_mem_mb,
        "mem_delta_mb": mem_after_mb - mem_before_mb
    }

if __name__ == "__main__":
    measure_index_throughput()
