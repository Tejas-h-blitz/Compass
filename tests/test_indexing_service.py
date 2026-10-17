"""
Integration tests for the live IndexingService (watchdog + debouncer + background worker).

Each test runs against an **isolated temp database** (COMPASS_DATA_DIR pointed at
a per-test tmp_path) so that stale monitored_path rows from other runs cannot
poison the service's startup reconcile queue.

Timeout budgets are generous (15 s) because the first call to scan_file in a test
process triggers ChromaDB / SentenceTransformer model initialization which can
take 8-10 s on a cold cache.
"""
import os
import time
import pytest
from pathlib import Path
from watchdog.observers.polling import PollingObserver

from backend.indexing.status import IndexingStatus
from backend.indexing.service import IndexingService
from backend.models.db import (
    get_file_by_path, get_db_connection, log_file_access,
    get_recent_and_frequent_files, init_db, remove_monitored_path
)


class FastPollingObserver(PollingObserver):
    """PollingObserver with a 0.1 s poll interval for snappy tests."""
    def __init__(self, **kwargs):
        super().__init__(timeout=0.1, **kwargs)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """
    Redirect every test to its own fresh SQLite DB so that stale monitored_path
    rows left by earlier tests (or the live Compass instance) cannot clog the
    service's startup reconcile queue.

    Also mocks ChromaDB embedding calls (upsert_file_embeddings,
    delete_file_embeddings) so the worker thread only does SQLite work — avoiding
    multi-second ChromaDB initialisation in throw-away temp directories.
    """
    db_dir = str(tmp_path / "db")
    os.makedirs(db_dir, exist_ok=True)
    monkeypatch.setenv("COMPASS_DATA_DIR", db_dir)
    # Re-initialise the schema in the fresh directory
    init_db()

    # Stub out ChromaDB to keep tests fast and hermetic.
    # scan_file uses an inline "from backend.search.semantic_search import ..."
    # so we must inject a fake module into sys.modules before the import fires.
    import sys
    import types

    _fake_ss = types.ModuleType("backend.search.semantic_search")
    _fake_ss.upsert_file_embeddings = lambda *a, **kw: None
    _fake_ss.delete_file_embeddings = lambda *a, **kw: None

    _original_ss = sys.modules.get("backend.search.semantic_search")
    sys.modules["backend.search.semantic_search"] = _fake_ss

    # Also patch the already-bound name in service.py (imported at module load time)
    import backend.indexing.service as _svc
    _original_dfe = _svc.delete_file_embeddings
    _svc.delete_file_embeddings = lambda *a, **kw: None

    yield db_dir

    # Restore originals
    if _original_ss is None:
        sys.modules.pop("backend.search.semantic_search", None)
    else:
        sys.modules["backend.search.semantic_search"] = _original_ss
    _svc.delete_file_embeddings = _original_dfe


# ── Test 1 ─────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_service_create_modify_delete_move(tmp_path):
    status = IndexingStatus()
    service = IndexingService(
        status=status,
        observer_cls=FastPollingObserver,
        quiet_period=0.2,
        startup_delay=0.0,
    )

    monitored_root = tmp_path / "monitored_test"
    monitored_root.mkdir()
    service.start()
    service.add_root(str(monitored_root))

    try:
        # 1. Create file -------------------------------------------------------
        test_file = monitored_root / "test_doc.txt"
        test_file.write_text("Unique searchable content for live indexing test.", encoding="utf-8")
        filepath = str(test_file)

        # Allow up to 15 s for ChromaDB cold-start + debounce + worker
        deadline = time.time() + 15.0
        indexed = False
        while time.time() < deadline:
            f = get_file_by_path(filepath)
            if f and "Unique searchable content" in f["content"]:
                indexed = True
                break
            time.sleep(0.2)
        assert indexed, "File was not indexed after creation."

        # 2. Modify file -------------------------------------------------------
        test_file.write_text("Modified updated content for live indexing test.", encoding="utf-8")
        deadline = time.time() + 15.0
        modified = False
        while time.time() < deadline:
            f = get_file_by_path(filepath)
            if f and "Modified updated content" in f["content"]:
                modified = True
                break
            time.sleep(0.2)
        assert modified, "File update was not reflected in index."

        # 3. Move / rename file ------------------------------------------------
        log_file_access(filepath)
        log_file_access(filepath)
        log_file_access(filepath)

        renamed_file = monitored_root / "renamed_doc.txt"
        new_filepath = str(renamed_file)
        os.replace(filepath, new_filepath)

        deadline = time.time() + 10.0
        moved = False
        while time.time() < deadline:
            old_f = get_file_by_path(filepath)
            new_f = get_file_by_path(new_filepath)
            if not old_f and new_f:
                moved = True
                break
            time.sleep(0.2)
        assert moved, "Move/rename was not reflected in index."

        # Verify access_log rewrite
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM access_log WHERE filepath = ?",
            (os.path.abspath(new_filepath),),
        )
        count = c.fetchone()[0]
        conn.close()
        assert count == 3, f"access_log filepath was not rewritten; found {count} records."

        # 4. Delete file -------------------------------------------------------
        os.remove(new_filepath)
        deadline = time.time() + 10.0
        deleted = False
        while time.time() < deadline:
            f = get_file_by_path(new_filepath)
            if not f:
                deleted = True
                break
            time.sleep(0.2)
        assert deleted, "File deletion was not pruned from index."

    finally:
        service.stop(timeout=2.0)
        remove_monitored_path(str(monitored_root), prune_files=True)


# ── Test 2 ─────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_cloud_attribute_file_indexed_without_content(tmp_path, monkeypatch):
    status = IndexingStatus()
    service = IndexingService(
        status=status,
        observer_cls=FastPollingObserver,
        quiet_period=0.2,
        startup_delay=0.0,
    )

    monitored_root = tmp_path / "cloud_root"
    monitored_root.mkdir()
    service.start()
    service.add_root(str(monitored_root))

    test_file = monitored_root / "cloud_doc.txt"
    test_file.write_text("This text should not be read because it is in cloud", encoding="utf-8")
    filepath = str(test_file)

    # Monkeypatch os.stat to return FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS (0x00400000)
    real_stat = os.stat

    def mock_stat(path, *args, **kwargs):
        res = real_stat(path, *args, **kwargs)
        if os.path.normcase(os.path.abspath(str(path))) == os.path.normcase(
            os.path.abspath(filepath)
        ):
            class MockStatResult:
                st_size = res.st_size
                st_mtime = res.st_mtime
                st_ctime = res.st_ctime
                st_file_attributes = 0x00400000  # Recall on data access

            return MockStatResult()
        return res

    monkeypatch.setattr(os, "stat", mock_stat)

    try:
        service.queue_reconcile(str(monitored_root), force=True)
        deadline = time.time() + 15.0
        indexed_cloud = False
        while time.time() < deadline:
            f = get_file_by_path(filepath)
            if f:
                assert f["content"] == "", f"Cloud-only file content must be empty, got: {f['content']}"
                assert status.skipped_cloud >= 1
                indexed_cloud = True
                break
            time.sleep(0.2)
        assert indexed_cloud, "Cloud-only file was not indexed with empty content."

    finally:
        service.stop(timeout=2.0)
        remove_monitored_path(str(monitored_root), prune_files=True)


# ── Test 3 ─────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_root_removal_pruning(tmp_path):
    root_a = tmp_path / "folder_a"
    root_b = tmp_path / "folder_b"
    root_a.mkdir()
    root_b.mkdir()

    file_a = root_a / "file_a.txt"
    file_a.write_text("Content in folder A", encoding="utf-8")
    path_a = str(file_a)

    file_b = root_b / "file_b.txt"
    file_b.write_text("Content in folder B", encoding="utf-8")
    path_b = str(file_b)

    service = IndexingService(
        observer_cls=FastPollingObserver,
        quiet_period=0.2,
        startup_delay=0.0,
    )
    service.start()
    service.add_root(str(root_a))
    service.add_root(str(root_b))

    try:
        # Trigger reconcile for both roots
        service.queue_reconcile(str(root_a))
        service.queue_reconcile(str(root_b))

        deadline = time.time() + 15.0
        while time.time() < deadline:
            if get_file_by_path(path_a) and get_file_by_path(path_b):
                break
            time.sleep(0.2)

        assert get_file_by_path(path_a) is not None, "file_a.txt was not indexed."
        assert get_file_by_path(path_b) is not None, "file_b.txt was not indexed."

        # Add access logs to both
        log_file_access(path_a)
        log_file_access(path_b)

        # Remove root_a — its file and access_log rows should be pruned
        service.remove_root(str(root_a))

        assert get_file_by_path(path_a) is None, "file_a.txt was not pruned after root removal."

        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM access_log WHERE filepath = ?",
            (os.path.abspath(path_a),),
        )
        count_a = c.fetchone()[0]
        c.execute(
            "SELECT COUNT(*) FROM access_log WHERE filepath = ?",
            (os.path.abspath(path_b),),
        )
        count_b = c.fetchone()[0]
        conn.close()

        assert count_a == 0, "access_log rows for removed root were not pruned."
        assert count_b == 1, "access_log rows for remaining root were mistakenly pruned."
        assert get_file_by_path(path_b) is not None, "File in remaining root was mistakenly pruned."

    finally:
        service.stop(timeout=2.0)
        remove_monitored_path(str(root_b), prune_files=True)


# ── Test 4 ─────────────────────────────────────────────────────────────────────

def test_pause_and_resume():
    service = IndexingService(quiet_period=0.2, startup_delay=0.0)
    assert not service.is_paused()
    service.pause()
    assert service.is_paused()
    assert service.status.state == "paused"
    service.resume()
    assert not service.is_paused()


# ── Test 5 ─────────────────────────────────────────────────────────────────────

def test_stop_completes_within_timeout():
    service = IndexingService(quiet_period=0.2, startup_delay=0.0)
    service.start()
    start_t = time.time()
    service.stop(timeout=5.0)
    elapsed = time.time() - start_t
    assert elapsed < 5.0, f"Service stop took {elapsed}s, exceeded 5.0 s budget."
