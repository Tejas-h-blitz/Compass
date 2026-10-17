import os
import pytest
from backend.indexing.debounce import Debouncer, ACTION_UPSERT, ACTION_DELETE, ACTION_MOVE, ACTION_RECONCILE

class FakeClock:
    def __init__(self, start_time: float = 1000.0):
        self.current_time = start_time

    def time(self) -> float:
        return self.current_time

    def advance(self, seconds: float):
        self.current_time += seconds

    def sleep(self, seconds: float):
        self.current_time += seconds


def test_rapid_modifies_coalesce():
    clock = FakeClock()
    debouncer = Debouncer(quiet_period=1.5, time_fn=clock.time)
    root = "C:\\test_root"
    file_path = "C:\\test_root\\doc.txt"

    # Rapid modifications within quiet period
    debouncer.add_modified(file_path, root)
    clock.advance(0.5)
    debouncer.add_modified(file_path, root)
    clock.advance(0.5)
    debouncer.add_modified(file_path, root)

    # Not ready yet (only 1.0s elapsed since last modify, quiet period is 1.5s)
    ready = debouncer.flush_ready()
    assert len(ready) == 0

    # Advance beyond quiet period
    clock.advance(1.6)
    ready = debouncer.flush_ready()
    assert len(ready) == 1
    assert ready[0]["action"] == ACTION_UPSERT
    assert ready[0]["path"] == os.path.normcase(os.path.abspath(file_path))


def test_create_then_delete_is_noop():
    clock = FakeClock()
    debouncer = Debouncer(quiet_period=1.5, time_fn=clock.time)
    root = "C:\\test_root"
    file_path = "C:\\test_root\\temp.txt"

    # Created then deleted within the window
    debouncer.add_created(file_path, root)
    clock.advance(0.5)
    debouncer.add_deleted(file_path, root)

    clock.advance(2.0)
    ready = debouncer.flush_ready()
    # Should be completely empty: no-op!
    assert len(ready) == 0


def test_storm_threshold_collapses_to_reconcile():
    clock = FakeClock()
    debouncer = Debouncer(quiet_period=1.5, storm_threshold=50, time_fn=clock.time)
    root = "C:\\test_root"

    # Emit 55 distinct path events
    for i in range(55):
        debouncer.add_created(f"C:\\test_root\\file_{i}.txt", root)

    # Should have collapsed the per-file events to a single reconcile
    ready = debouncer.flush_ready()
    assert len(ready) == 1
    assert ready[0]["action"] == ACTION_RECONCILE
    assert ready[0]["root"] == root


def test_backoff_retries_on_permission_error(tmp_path):
    clock = FakeClock()
    debouncer = Debouncer(quiet_period=1.5, time_fn=clock.time)

    test_file = tmp_path / "locked_file.txt"
    test_file.write_text("initial content", encoding="utf-8")
    filepath = str(test_file)

    # Simulate permission error by monkeypatching open
    original_open = open
    def mock_locked_open(*args, **kwargs):
        raise PermissionError("File locked by another process")

    # Monkeypatch open inside is_file_stable
    import builtins
    old_builtins_open = builtins.open
    try:
        builtins.open = mock_locked_open

        # Attempt 1: fails, backoff scheduled for +2s
        stable = debouncer.is_file_stable(filepath, stability_check_interval=0, sleep_fn=clock.sleep)
        assert not stable

        # Before 2s: still in backoff
        clock.advance(1.0)
        assert not debouncer.is_file_stable(filepath, stability_check_interval=0, sleep_fn=clock.sleep)

        # After 2s: attempt 2 fails, backoff scheduled for +5s
        clock.advance(1.5)
        assert not debouncer.is_file_stable(filepath, stability_check_interval=0, sleep_fn=clock.sleep)

        # Restore open: file becomes unlocked and stable
        builtins.open = old_builtins_open
        clock.advance(6.0)
        assert debouncer.is_file_stable(filepath, stability_check_interval=0, sleep_fn=clock.sleep)
    finally:
        builtins.open = old_builtins_open
