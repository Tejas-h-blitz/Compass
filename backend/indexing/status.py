import time
import threading
from typing import Optional, Dict, Any

VALID_STATES = {"idle", "indexing", "reconciling", "paused", "error"}

class IndexingStatus:
    """
    Thread-safe holder for live indexing state, progress metrics, and counters.
    Shared across file watcher observers, indexing worker threads, and REST API endpoints.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.state: str = "idle"
        self.queue_length: int = 0
        self.processed: int = 0
        self.total_expected: int = 0
        self.current_file: str = ""
        self.indexed: int = 0
        self.updated: int = 0
        self.pruned: int = 0
        self.skipped_cloud: int = 0
        self.errors: int = 0
        self.last_error: Optional[str] = None
        self.last_reconcile_at: Optional[float] = None

    def set_state(self, state: str) -> None:
        if state not in VALID_STATES:
            raise ValueError(f"Invalid indexing state: {state}")
        with self._lock:
            self.state = state

    def set_queue_length(self, length: int) -> None:
        with self._lock:
            self.queue_length = max(0, length)

    def set_progress(self, processed: int, total_expected: int, current_file: str = "") -> None:
        with self._lock:
            self.processed = processed
            self.total_expected = total_expected
            self.current_file = current_file

    def increment(self, counter: str, delta: int = 1) -> None:
        with self._lock:
            if hasattr(self, counter):
                setattr(self, counter, getattr(self, counter) + delta)

    def record_error(self, error_message: str) -> None:
        with self._lock:
            self.state = "error"
            self.last_error = error_message
            self.errors += 1

    def record_reconcile(self, timestamp: Optional[float] = None) -> None:
        with self._lock:
            self.last_reconcile_at = timestamp if timestamp is not None else time.time()

    def reset_counters(self) -> None:
        with self._lock:
            self.processed = 0
            self.total_expected = 0
            self.current_file = ""
            self.indexed = 0
            self.updated = 0
            self.pruned = 0
            self.skipped_cloud = 0
            self.errors = 0
            self.last_error = None

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self.state,
                "queue_length": self.queue_length,
                "processed": self.processed,
                "total_expected": self.total_expected,
                "current_file": self.current_file,
                "counters": {
                    "indexed": self.indexed,
                    "updated": self.updated,
                    "pruned": self.pruned,
                    "skipped_cloud": self.skipped_cloud,
                    "errors": self.errors
                },
                "last_error": self.last_error,
                "last_reconcile_at": self.last_reconcile_at
            }

# Global singleton status holder
global_indexing_status = IndexingStatus()
