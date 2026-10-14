import os
import sys
import time
import queue
import logging
import threading
from typing import Dict, List, Optional, Type, Set, Any
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from backend.paths import data_dir, app_home
from backend.indexing.rules import should_ignore
from backend.indexing.status import IndexingStatus, global_indexing_status
from backend.indexing.debounce import Debouncer, ACTION_UPSERT, ACTION_DELETE, ACTION_MOVE, ACTION_RECONCILE
from backend.models.db import (
    get_monitored_paths, add_monitored_path, remove_monitored_path,
    delete_file, rename_file_in_access_log, prune_monitored_root_data,
    get_file_by_path, update_monitored_path_scanned
)
from backend.scanner.scanner import scan_file, scan_directory
from backend.platform.priority import set_thread_priority_below_normal

try:
    from backend.search.semantic_search import delete_file_embeddings
except ImportError:
    def delete_file_embeddings(filepath: str):
        pass

logger = logging.getLogger(__name__)

class CompassWatchdogHandler(FileSystemEventHandler):
    def __init__(self, service: 'IndexingService', root: str):
        super().__init__()
        self.service = service
        self.root = root

    def on_created(self, event):
        if event.is_directory:
            # Directory created -> check if ignored, else reconcile
            if not should_ignore(event.src_path, is_dir=True):
                self.service.queue_reconcile(self.root)
        else:
            self.service.on_fs_created(event.src_path, self.root)

    def on_modified(self, event):
        if not event.is_directory:
            self.service.on_fs_modified(event.src_path, self.root)

    def on_deleted(self, event):
        if event.is_directory:
            self.service.queue_reconcile(self.root)
        else:
            self.service.on_fs_deleted(event.src_path, self.root)

    def on_moved(self, event):
        if event.is_directory:
            self.service.queue_reconcile(self.root)
        else:
            self.service.on_fs_moved(event.src_path, event.dest_path, self.root)


class IndexingService:
    """
    Incremental live indexing service for Compass.
    Maintains active watchdog observers per monitored root, coalesces events with debouncing,
    runs a low-priority worker thread, performs periodic/startup reconcile scans,
    and exposes full pause/resume/stop lifecycle controls.
    """
    def __init__(
        self,
        status: Optional[IndexingStatus] = None,
        observer_cls: Type[Any] = Observer,
        quiet_period: float = 1.5,
        storm_threshold: int = 500,
        startup_delay: Optional[float] = None,
        periodic_reconcile_interval: float = 6 * 3600,  # 6 hours
        is_background_mode: bool = False
    ):
        self.status = status or global_indexing_status
        self.observer_cls = observer_cls
        self.quiet_period = quiet_period
        self.storm_threshold = storm_threshold
        self.periodic_reconcile_interval = periodic_reconcile_interval
        self.is_background_mode = is_background_mode

        # Set startup reconcile delay: 45s in background mode, 3s in interactive mode
        if startup_delay is not None:
            self.startup_delay = startup_delay
        else:
            self.startup_delay = 45.0 if is_background_mode else 3.0

        self.debouncer = Debouncer(
            quiet_period=self.quiet_period,
            storm_threshold=self.storm_threshold
        )

        self._observers: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._paused = threading.Event()  # Cleared when running, set when paused
        self._wake_worker = threading.Event()

        self._worker_thread: Optional[threading.Thread] = None
        self._scheduler_thread: Optional[threading.Thread] = None
        self._reconcile_queue: List[Tuple[str, bool]] = []  # (root_path, force)
        self._reconcile_lock = threading.Lock()

    # --- Filesystem Watcher Callbacks ---

    def on_fs_created(self, path: str, root: str):
        if should_ignore(path, is_dir=False):
            return
        logger.debug(f"Live index: file created '{path}'")
        with self._lock:
            self.debouncer.add_created(path, root)
            self.status.set_queue_length(self.debouncer.pending_count())
        self._wake_worker.set()

    def on_fs_modified(self, path: str, root: str):
        if should_ignore(path, is_dir=False):
            return
        logger.debug(f"Live index: file modified '{path}'")
        with self._lock:
            self.debouncer.add_modified(path, root)
            self.status.set_queue_length(self.debouncer.pending_count())
        self._wake_worker.set()

    def on_fs_deleted(self, path: str, root: str):
        if should_ignore(path, is_dir=False):
            return
        logger.debug(f"Live index: file deleted '{path}'")
        with self._lock:
            self.debouncer.add_deleted(path, root)
            self.status.set_queue_length(self.debouncer.pending_count())
        self._wake_worker.set()

    def on_fs_moved(self, src_path: str, dst_path: str, root: str):
        logger.debug(f"Live index: file moved '{src_path}' -> '{dst_path}'")
        with self._lock:
            self.debouncer.add_moved(src_path, dst_path, root)
            self.status.set_queue_length(self.debouncer.pending_count())
        self._wake_worker.set()

    def queue_reconcile(self, root: str, force: bool = False):
        norm_root = os.path.normcase(os.path.abspath(root))
        with self._reconcile_lock:
            if not any(r[0] == norm_root for r in self._reconcile_queue):
                self._reconcile_queue.append((norm_root, force))
        self._wake_worker.set()

    # --- Worker Thread Execution ---

    def _worker_loop(self):
        """Worker thread entrypoint. Lowers thread priority and continuously drains queues."""
        try:
            set_thread_priority_below_normal()
        except Exception as e:
            logger.debug(f"Could not lower thread priority: {e}")

        logger.info("Indexing worker thread started at below-normal priority.")

        while not self._stop_event.is_set():
            # Check paused state
            if self._paused.is_set():
                self.status.set_state("paused")
                self._wake_worker.wait(timeout=0.5)
                continue

            # 1. Process Reconcile jobs
            next_reconcile = None
            with self._reconcile_lock:
                if self._reconcile_queue:
                    next_reconcile = self._reconcile_queue.pop(0)

            if next_reconcile:
                root_path, force = next_reconcile
                self._execute_reconcile(root_path, force)
                continue

            # 2. Flush and process debounced events
            with self._lock:
                ready_jobs = self.debouncer.flush_ready()
                self.status.set_queue_length(self.debouncer.pending_count())

            if ready_jobs:
                self.status.set_state("indexing")
                for job in ready_jobs:
                    if self._stop_event.is_set():
                        break
                    if self._paused.is_set():
                        break
                    self._execute_job(job)

                if not self._paused.is_set() and not self._stop_event.is_set():
                    self.status.set_state("idle")
            else:
                if self.status.state not in ("paused", "reconciling", "error"):
                    self.status.set_state("idle")
                self._wake_worker.wait(timeout=0.5)
                self._wake_worker.clear()

        logger.info("Indexing worker thread exited cleanly.")

    def _execute_job(self, job: Dict[str, Any]):
        action = job.get("action")
        root = job.get("root")

        try:
            if action == ACTION_RECONCILE:
                self._execute_reconcile(root, force=False)

            elif action == ACTION_DELETE:
                path = job["path"]
                self.status.current_file = path
                delete_file(path)
                delete_file_embeddings(path)
                self.status.increment("pruned")
                logger.info(f"Incremental indexing deleted: {path}")

            elif action == ACTION_MOVE:
                src = job["src"]
                dst = job["dst"]
                self.status.current_file = dst

                # Delete old index records and rewrite access_log
                delete_file(src)
                delete_file_embeddings(src)
                rename_file_in_access_log(src, dst)

                # Check if destination is valid and within a monitored root
                if should_ignore(dst, is_dir=False) or not self._is_within_monitored_roots(dst):
                    # Destination is outside or ignored -> treat as delete
                    self.status.increment("pruned")
                    logger.info(f"Moved file outside monitored roots (treated as delete): {src} -> {dst}")
                else:
                    # Index destination
                    if self.debouncer.is_file_stable(dst):
                        updated = scan_file(dst, force=False)
                        if updated:
                            self.status.increment("updated")
                    else:
                        # Re-add to debouncer for backoff retry
                        with self._lock:
                            self.debouncer.add_modified(dst, root)

            elif action == ACTION_UPSERT:
                path = job["path"]
                self.status.current_file = path
                if not os.path.exists(path):
                    # File was deleted before stability check
                    delete_file(path)
                    delete_file_embeddings(path)
                    return

                if self.debouncer.is_file_stable(path):
                    existing = get_file_by_path(path)
                    updated = scan_file(path, force=False)
                    if updated:
                        if existing:
                            self.status.increment("updated")
                        else:
                            self.status.increment("indexed")
                else:
                    # Still locked or unstable: debouncer backoff manages next attempt
                    with self._lock:
                        self.debouncer.add_modified(path, root)

        except Exception as e:
            logger.error(f"Error processing index job {job}: {e}")
            self.status.record_error(str(e))

    def _execute_reconcile(self, root_path: str, force: bool = False):
        """Performs full reconcile walk of root_path with progress updates."""
        if not os.path.exists(root_path) or not os.path.isdir(root_path):
            logger.warning(f"Reconcile skipped for non-existent path: {root_path}")
            return

        self.status.set_state("reconciling")
        logger.info(f"Starting reconcile scan for root: {root_path}")

        # 1. Count candidate files for live progress reporting
        candidates: List[str] = []
        for root, dirs, files in os.walk(root_path, followlinks=False):
            if self._stop_event.is_set():
                return
            dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), is_dir=True)]
            for f in files:
                full_p = os.path.join(root, f)
                if not should_ignore(full_p, is_dir=False):
                    candidates.append(full_p)

        total_candidates = len(candidates)
        self.status.set_progress(0, total_candidates, "")

        # 2. Process candidate files with progress updates
        processed_count = 0
        found_set = set()
        for filepath in candidates:
            if self._stop_event.is_set():
                return
            while self._paused.is_set() and not self._stop_event.is_set():
                time.sleep(0.2)

            norm_p = os.path.abspath(filepath)
            found_set.add(norm_p)
            self.status.set_progress(processed_count, total_candidates, norm_p)

            try:
                existing = get_file_by_path(norm_p)
                updated = scan_file(norm_p, force=force)
                if updated:
                    if existing:
                        self.status.increment("updated")
                    else:
                        self.status.increment("indexed")
            except Exception as e:
                logger.error(f"Error scanning during reconcile {norm_p}: {e}")
                self.status.record_error(str(e))

            processed_count += 1
            self.status.set_progress(processed_count, total_candidates, norm_p)

        # 3. Prune deleted files under root
        self._prune_missing_files_under_root(root_path, found_set)

        update_monitored_path_scanned(root_path)
        self.status.record_reconcile()
        self.status.set_progress(total_candidates, total_candidates, "")
        self.status.set_state("idle")
        logger.info(f"Reconcile scan completed for root: {root_path} ({total_candidates} files evaluated).")

    def _prune_missing_files_under_root(self, root_path: str, found_set: Set[str]):
        """Removes indexed records for files under root_path that no longer exist on disk."""
        from backend.models.db import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        norm_root = os.path.abspath(root_path)
        sep = os.path.sep
        prefix = norm_root if norm_root.endswith(sep) else norm_root + sep

        try:
            cursor.execute("SELECT filepath FROM files WHERE filepath LIKE ? OR filepath = ?", (prefix + "%", norm_root))
            db_paths = [r[0] for r in cursor.fetchall()]
        finally:
            conn.close()

        for p in db_paths:
            if p not in found_set:
                delete_file(p)
                delete_file_embeddings(p)
                self.status.increment("pruned")
                logger.info(f"Pruned deleted file during reconcile: {p}")

    def _is_within_monitored_roots(self, path: str) -> bool:
        norm_p = os.path.normcase(os.path.abspath(path))
        for root in self._observers.keys():
            norm_r = os.path.normcase(os.path.abspath(root))
            prefix = norm_r if norm_r.endswith(os.path.sep) else norm_r + os.path.sep
            if norm_p == norm_r or norm_p.startswith(prefix):
                return True
        return False

    # --- Periodic and Startup Scheduler ---

    def _scheduler_loop(self):
        """Handles delayed startup reconcile and 6-hour periodic reconcile scans."""
        # Startup reconcile delay
        if self.startup_delay > 0:
            logger.info(f"Waiting startup reconcile delay: {self.startup_delay}s...")
            slept = 0.0
            while slept < self.startup_delay and not self._stop_event.is_set():
                time.sleep(0.5)
                slept += 0.5

        if self._stop_event.is_set():
            return

        # Queue initial reconcile for all active roots
        with self._lock:
            roots_to_reconcile = list(self._observers.keys())
        for r in roots_to_reconcile:
            self.queue_reconcile(r, force=False)

        # Periodic reconcile loop
        last_check = time.time()
        while not self._stop_event.is_set():
            time.sleep(10.0)
            now = time.time()
            if now - last_check >= self.periodic_reconcile_interval:
                last_check = now
                with self._lock:
                    active_roots = list(self._observers.keys())
                for r in active_roots:
                    self.queue_reconcile(r, force=False)

    # --- Public Lifecycle Management ---

    def start(self):
        """Starts observers for all monitored roots, worker thread, and scheduler."""
        with self._lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return  # Already running

            self._stop_event.clear()
            self._paused.clear()
            self.status.set_state("idle")

            # Load monitored roots from database
            try:
                roots = get_monitored_paths()
                for r in roots:
                    p = r["path"]
                    if os.path.exists(p) and os.path.isdir(p):
                        self._start_observer_for_root(p)
            except Exception as e:
                logger.error(f"Failed to load monitored paths: {e}")

            # Start worker thread
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="CompassIndexingWorker",
                daemon=True
            )
            self._worker_thread.start()

            # Start scheduler thread
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="CompassIndexingScheduler",
                daemon=True
            )
            self._scheduler_thread.start()

        logger.info("IndexingService started successfully.")

    def stop(self, timeout: float = 5.0):
        """
        Gracefully stops all observers, scheduler, and worker within the timeout budget.
        Conforms strictly to Day 2's 5-second shutdown budget.
        """
        logger.info(f"Stopping IndexingService (timeout={timeout}s)...")
        self._stop_event.set()
        self._wake_worker.set()

        # Stop and join all observers
        with self._lock:
            observers = list(self._observers.values())
            self._observers.clear()

        for obs in observers:
            try:
                obs.stop()
            except Exception as e:
                logger.debug(f"Error stopping observer: {e}")

        # Wait for observers to terminate
        for obs in observers:
            try:
                obs.join(timeout=1.0)
            except Exception:
                pass

        # Join worker thread
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=min(2.5, timeout))

        # Join scheduler thread
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=1.0)

        self.status.set_state("idle")
        logger.info("IndexingService stopped.")

    def _start_observer_for_root(self, root_path: str):
        """Helper to create and start a watchdog observer for a single root."""
        norm_root = os.path.abspath(root_path)
        if norm_root in self._observers:
            return

        handler = CompassWatchdogHandler(self, norm_root)
        observer = self.observer_cls()
        observer.schedule(handler, norm_root, recursive=True)
        try:
            observer.start()
            self._observers[norm_root] = observer
            logger.info(f"Started file watcher observer for: '{norm_root}'")
        except Exception as e:
            logger.error(f"Failed to start observer for '{norm_root}': {e}. Queuing reconcile.")
            self.queue_reconcile(norm_root)

    def add_root(self, path: str, label: Optional[str] = None) -> bool:
        """
        Adds a new monitored root, starts its observer, and triggers an initial reconcile.
        """
        canonical = os.path.abspath(path)
        with self._lock:
            added = add_monitored_path(canonical, label)
            if added or canonical not in self._observers:
                self._start_observer_for_root(canonical)
                self.queue_reconcile(canonical, force=False)
                return True
            return False

    def remove_root(self, path: str) -> bool:
        """
        Stops the observer for a root and prunes index data and access history
        for files under it not covered by any other root.
        """
        canonical = os.path.abspath(path)
        with self._lock:
            obs = self._observers.pop(canonical, None)
            if obs:
                try:
                    obs.stop()
                    obs.join(timeout=1.0)
                except Exception:
                    pass

            # Prune SQLite rows, Chroma embeddings, and access_log
            remove_monitored_path(canonical, prune_files=False)
            pruned_count = prune_monitored_root_data(canonical)
            self.status.increment("pruned", pruned_count)
            logger.info(f"Removed monitored root '{canonical}' and pruned {pruned_count} files.")
            return True

    def pause(self):
        """Pauses indexing worker from processing new jobs (observers keep collecting)."""
        self._paused.set()
        self.status.set_state("paused")
        logger.info("Indexing worker paused.")

    def resume(self):
        """Resumes indexing worker and drains accumulated jobs."""
        self._paused.clear()
        self.status.set_state("idle")
        self._wake_worker.set()
        logger.info("Indexing worker resumed.")

    def rescan(self, force: bool = False):
        """Triggers reconcile jobs for all active monitored roots."""
        with self._lock:
            roots = list(self._observers.keys())
        for r in roots:
            self.queue_reconcile(r, force=force)
        logger.info(f"Rescan triggered for {len(roots)} roots (force={force}).")

    def is_paused(self) -> bool:
        return self._paused.is_set()

    def get_monitored_roots(self) -> List[Dict[str, Any]]:
        """Returns list of monitored roots with active watching status and file counts."""
        db_roots = get_monitored_paths()
        with self._lock:
            for r in db_roots:
                canonical = os.path.abspath(r["path"])
                r["watching"] = canonical in self._observers
        return db_roots

# Global service singleton instance
global_indexing_service = IndexingService()
