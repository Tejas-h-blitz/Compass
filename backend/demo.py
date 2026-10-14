import os
import sys
import json
import time
import shutil
import logging
from typing import Dict, Any, Optional

from backend.paths import data_dir, app_home, repo_root
from backend.models.db import (
    get_db_connection, add_monitored_path, get_monitored_paths
)

logger = logging.getLogger(__name__)

def is_demo_mode() -> bool:
    """Returns True if the current process is running in Demo Mode."""
    curr = os.path.normcase(os.path.realpath(data_dir()))
    demo = os.path.normcase(os.path.realpath(os.path.join(app_home(), "demo")))
    return curr == demo

def get_demo_manifest() -> Dict[str, Any]:
    """Reads manifest.json from the bundled sample_corpus directory."""
    manifest_path = os.path.join(repo_root(), "sample_corpus", "manifest.json")
    if not os.path.exists(manifest_path):
        return {"version": "0", "files": [], "suggested_queries": []}
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

def setup_demo_corpus_if_needed() -> str:
    """
    Idempotently sets up the sample corpus inside app_home()/demo/corpus.
    Applies synthetic modification timestamps from manifest.json using os.utime.
    Registers the directory as a monitored root.
    Guarantees it only deletes inside the verified demo directory.
    """
    demo_base = os.path.realpath(os.path.join(app_home(), "demo"))
    corpus_dir = os.path.join(demo_base, "corpus")
    marker_file = os.path.join(demo_base, ".corpus_version")
    source_dir = os.path.join(repo_root(), "sample_corpus")

    manifest = get_demo_manifest()
    expected_version = manifest.get("version", "1.0")

    os.makedirs(corpus_dir, exist_ok=True)

    # Check if already setup with matching version
    if os.path.exists(marker_file):
        try:
            with open(marker_file, "r", encoding="utf-8") as f:
                saved_version = f.read().strip()
            if saved_version == expected_version and os.listdir(corpus_dir):
                logger.info("Demo corpus is already up-to-date; skipping rebuild.")
                _ensure_monitored(corpus_dir)
                return corpus_dir
        except Exception as e:
            logger.debug(f"Error reading corpus marker: {e}")

    logger.info(f"Provisioning demo sample corpus into '{corpus_dir}'...")

    # Safety check: ensure corpus_dir is strictly inside demo_base
    norm_demo = os.path.normcase(demo_base)
    norm_corpus = os.path.normcase(os.path.realpath(corpus_dir))
    if not norm_corpus.startswith(norm_demo + os.path.sep):
        raise RuntimeError(f"Refusing to touch directory outside demo profile: {corpus_dir}")

    # Clear existing files in verified corpus_dir
    for item in os.listdir(corpus_dir):
        p = os.path.join(corpus_dir, item)
        if os.path.isfile(p) or os.path.islink(p):
            os.remove(p)
        elif os.path.isdir(p):
            shutil.rmtree(p)

    # Copy files from sample_corpus
    now = time.time()
    for item in manifest.get("files", []):
        filename = item["filename"]
        src = os.path.join(source_dir, filename)
        dst = os.path.join(corpus_dir, filename)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            days_ago = item.get("days_ago", 0)
            target_mtime = now - (days_ago * 86400)
            try:
                os.utime(dst, (target_mtime, target_mtime))
            except Exception as e:
                logger.debug(f"Could not set mtime for {filename}: {e}")

    # Write version marker
    with open(marker_file, "w", encoding="utf-8") as f:
        f.write(expected_version)

    _ensure_monitored(corpus_dir)
    logger.info(f"Demo corpus successfully initialized with {len(manifest.get('files', []))} files.")
    return corpus_dir

def _ensure_monitored(corpus_dir: str):
    """Ensures corpus_dir is registered as a monitored path in SQLite."""
    monitored = [m["path"] for m in get_monitored_paths()]
    canonical = os.path.abspath(corpus_dir)
    if canonical not in monitored:
        add_monitored_path(canonical, label="Sample CS Corpus (Demo)")

def seed_simulated_history() -> int:
    """
    Seeds access_log with realistic usage patterns for sample demo documents.
    Restricted strictly to demo mode; raises PermissionError if called in normal mode.
    """
    if not is_demo_mode():
        raise PermissionError("Simulated history can only be loaded in Demo Mode.")

    manifest = get_demo_manifest()
    corpus_dir = os.path.join(app_home(), "demo", "corpus")
    now = time.time()

    # Pick 4 representative demo files
    target_filenames = [
        ("kubernetes_guide.pdf", [1, 2, 4, 8, 14, 20, 24, 28]),     # Highly frequent & recent
        ("database_indexing_notes.md", [3, 7, 12, 18, 30]),          # Frequent
        ("course_project_proposal.docx", [2, 5, 10]),                # Moderate
        ("healthy_meal_prep.txt", [4, 16])                           # Occasional
    ]

    conn = get_db_connection()
    cursor = conn.cursor()
    total_seeded = 0

    try:
        for filename, hour_offsets in target_filenames:
            filepath = os.path.abspath(os.path.join(corpus_dir, filename))
            for hours in hour_offsets:
                access_time = now - (hours * 3600)
                cursor.execute(
                    "INSERT INTO access_log (filepath, accessed_at) VALUES (?, ?)",
                    (filepath, access_time)
                )
                total_seeded += 1
        conn.commit()
        logger.info(f"Loaded {total_seeded} simulated history records into access_log.")
        return total_seeded
    finally:
        conn.close()
