import os
import time
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable, Set

logger = logging.getLogger(__name__)

# Event Action constants
ACTION_UPSERT = "upsert"
ACTION_DELETE = "delete"
ACTION_MOVE = "move"
ACTION_RECONCILE = "reconcile"

class PendingEvent:
    def __init__(self, action: str, path: str, root: str, timestamp: float,
                 src_path: Optional[str] = None, is_initial_create: bool = False):
        self.action = action                  # ACTION_UPSERT, ACTION_DELETE, ACTION_MOVE
        self.path = path                      # Canonical target path
        self.root = root                      # Monitored root directory
        self.timestamp = timestamp            # Last update timestamp
        self.src_path = src_path              # Used for moves (old path)
        self.is_initial_create = is_initial_create
        self.retry_count = 0
        self.next_retry_at = 0.0

class Debouncer:
    """
    Coalesces filesystem events per path within a configurable quiet period (default 1.5s).
    - Rapid modifies collapse into a single upsert.
    - Create followed by delete inside the window is a no-op.
    - Collapse to reconcile if pending paths for a root exceed storm_threshold (default 500).
    - Pure and deterministic: clock (time_fn) is injectable for unit tests.
    """
    def __init__(
        self,
        quiet_period: float = 1.5,
        storm_threshold: int = 500,
        time_fn: Callable[[], float] = time.time
    ):
        self.quiet_period = quiet_period
        self.storm_threshold = storm_threshold
        self.time_fn = time_fn
        # Map: path -> PendingEvent
        self._events: Dict[str, PendingEvent] = {}
        # Set of roots that triggered storm collapse to reconcile
        self._storm_roots: Set[str] = set()
        # Backoff tracker: path -> (retry_count, next_retry_time)
        self._backoff_tracker: Dict[str, Tuple[int, float]] = {}
        self._logged_failures: Set[str] = set()

    def add_created(self, path: str, root: str):
        now = self.time_fn()
        norm_path = os.path.normcase(os.path.abspath(path))
        if norm_path in self._events:
            ev = self._events[norm_path]
            ev.timestamp = now
            if ev.action == ACTION_DELETE:
                # Was deleted then recreated -> upsert (not initial create)
                ev.action = ACTION_UPSERT
                ev.is_initial_create = False
        else:
            self._events[norm_path] = PendingEvent(
                action=ACTION_UPSERT,
                path=norm_path,
                root=root,
                timestamp=now,
                is_initial_create=True
            )
        self._check_storm(root)

    def add_modified(self, path: str, root: str):
        now = self.time_fn()
        norm_path = os.path.normcase(os.path.abspath(path))
        if norm_path in self._events:
            ev = self._events[norm_path]
            ev.timestamp = now
            if ev.action == ACTION_DELETE:
                # File re-appeared/modified after delete -> treat as upsert
                ev.action = ACTION_UPSERT
                ev.is_initial_create = False
        else:
            self._events[norm_path] = PendingEvent(
                action=ACTION_UPSERT,
                path=norm_path,
                root=root,
                timestamp=now,
                is_initial_create=False
            )
        self._check_storm(root)

    def add_deleted(self, path: str, root: str):
        now = self.time_fn()
        norm_path = os.path.normcase(os.path.abspath(path))
        if norm_path in self._events:
            ev = self._events[norm_path]
            if ev.is_initial_create:
                # Created then deleted within the window -> no-op!
                del self._events[norm_path]
                return
            ev.action = ACTION_DELETE
            ev.timestamp = now
        else:
            self._events[norm_path] = PendingEvent(
                action=ACTION_DELETE,
                path=norm_path,
                root=root,
                timestamp=now
            )
        self._check_storm(root)

    def add_moved(self, src_path: str, dst_path: str, root: str):
        now = self.time_fn()
        norm_src = os.path.normcase(os.path.abspath(src_path))
        norm_dst = os.path.normcase(os.path.abspath(dst_path))

        src_ev = self._events.pop(norm_src, None)
        if src_ev and src_ev.is_initial_create:
            # File was created in this window and moved -> becomes create at destination
            self._events[norm_dst] = PendingEvent(
                action=ACTION_UPSERT,
                path=norm_dst,
                root=root,
                timestamp=now,
                is_initial_create=True
            )
        else:
            self._events[norm_dst] = PendingEvent(
                action=ACTION_MOVE,
                path=norm_dst,
                root=root,
                timestamp=now,
                src_path=norm_src
            )
        self._check_storm(root)

    def _check_storm(self, root: str):
        """Checks if pending distinct paths for this root exceed storm threshold."""
        count = sum(1 for ev in self._events.values() if ev.root == root)
        if count >= self.storm_threshold:
            logger.warning(
                f"Event storm detected: {count} events pending for root '{root}'. "
                f"Dropping per-file jobs and triggering full reconcile."
            )
            # Remove all per-file events for this root
            keys_to_remove = [k for k, ev in self._events.items() if ev.root == root]
            for k in keys_to_remove:
                del self._events[k]
            self._storm_roots.add(root)

    def flush_ready(self) -> List[Dict[str, Any]]:
        """
        Flushes all jobs whose quiet period has expired.
        Returns list of action dicts:
        - {"action": "reconcile", "root": root}
        - {"action": "delete", "path": path, "root": root}
        - {"action": "move", "src": src_path, "dst": path, "root": root}
        - {"action": "upsert", "path": path, "root": root}
        Sorted with deletes and moves first, followed by upserts.
        """
        now = self.time_fn()
        ready_jobs: List[Dict[str, Any]] = []

        # 1. Storm reconciles first
        if self._storm_roots:
            for root in list(self._storm_roots):
                ready_jobs.append({"action": ACTION_RECONCILE, "root": root})
            self._storm_roots.clear()

        # 2. Check pending per-path events
        deletes = []
        moves = []
        upserts = []

        ready_keys = []
        for path, ev in self._events.items():
            if now - ev.timestamp >= self.quiet_period:
                ready_keys.append(path)
                if ev.action == ACTION_DELETE:
                    deletes.append({"action": ACTION_DELETE, "path": ev.path, "root": ev.root})
                elif ev.action == ACTION_MOVE:
                    moves.append({"action": ACTION_MOVE, "src": ev.src_path, "dst": ev.path, "root": ev.root})
                else:
                    upserts.append({"action": ACTION_UPSERT, "path": ev.path, "root": ev.root})

        for k in ready_keys:
            del self._events[k]

        # Return: deletes and moves first, then upserts
        return ready_jobs + deletes + moves + upserts

    def pending_count(self) -> int:
        return len(self._events) + len(self._storm_roots)

    def is_file_stable(
        self,
        filepath: str,
        stability_check_interval: float = 0.1,
        sleep_fn: Callable[[float], None] = time.sleep
    ) -> bool:
        """
        Checks that a file is readable and its size is stable across two checks.
        Handles PermissionError (file still locked/written) with backoff schedule: 2s, 5s, 15s (max 3 retries).
        """
        now = self.time_fn()
        norm_path = os.path.normcase(os.path.abspath(filepath))

        # Check backoff if in backoff state
        if norm_path in self._backoff_tracker:
            retry_count, next_retry_at = self._backoff_tracker[norm_path]
            if now < next_retry_at:
                return False  # Still in backoff window

        if not os.path.exists(filepath):
            return False

        try:
            stat1 = os.stat(filepath)
            size1 = stat1.st_size
            if stability_check_interval > 0:
                sleep_fn(stability_check_interval)
            stat2 = os.stat(filepath)
            size2 = stat2.st_size

            if size1 != size2:
                # File is actively being written
                return False

            # Test readability of first byte
            with open(filepath, "rb") as f:
                _ = f.read(1)

            # Success! Clear any backoff state
            self._backoff_tracker.pop(norm_path, None)
            self._logged_failures.discard(norm_path)
            return True

        except (PermissionError, OSError) as e:
            # File is locked or inaccessible
            retries, _ = self._backoff_tracker.get(norm_path, (0, 0.0))
            backoffs = [2.0, 5.0, 15.0]
            if retries < len(backoffs):
                delay = backoffs[retries]
                self._backoff_tracker[norm_path] = (retries + 1, now + delay)
                logger.debug(f"File locked: '{filepath}', retrying in {delay}s (attempt {retries + 1}/3)")
            else:
                # Max retries exceeded
                if norm_path not in self._logged_failures:
                    logger.warning(f"File locked/inaccessible after 3 retries, skipping for now: '{filepath}': {e}")
                    self._logged_failures.add(norm_path)
                self._backoff_tracker.pop(norm_path, None)
            return False
