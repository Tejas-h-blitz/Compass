import os
import time
import pytest
from backend.demo import get_demo_manifest, setup_demo_corpus_if_needed, is_demo_mode, seed_simulated_history
from backend.models.db import init_db
from backend.paths import app_home
from backend.scanner.scanner import scan_directory
from backend.router.router import route_and_search

def test_demo_manifest_structure():
    manifest = get_demo_manifest()
    assert "version" in manifest
    assert "files" in manifest
    assert "suggested_queries" in manifest
    assert len(manifest["files"]) >= 40
    assert len(manifest["suggested_queries"]) == 8

def test_demo_corpus_setup_and_idempotence():
    # Run in demo profile
    demo_dir = os.path.join(app_home(), "demo")
    os.environ["COMPASS_DATA_DIR"] = demo_dir
    init_db()

    # Force a fresh rebuild by clearing the version marker so mtime assertions are reliable
    marker_file = os.path.join(demo_dir, ".corpus_version")
    if os.path.exists(marker_file):
        os.remove(marker_file)

    corpus_dir = setup_demo_corpus_if_needed()
    assert os.path.exists(corpus_dir)
    assert len(os.listdir(corpus_dir)) >= 40

    # Verify mtimes applied from days_ago
    manifest = get_demo_manifest()
    now = time.time()
    for item in manifest["files"][:5]:
        p = os.path.join(corpus_dir, item["filename"])
        assert os.path.exists(p)
        st = os.stat(p)
        expected_age_sec = item["days_ago"] * 86400
        # Allow +/- 300 seconds delta
        assert abs((now - st.st_mtime) - expected_age_sec) < 300

    # Idempotence: running second time does not fail or recreate
    corpus_dir_2 = setup_demo_corpus_if_needed()
    assert corpus_dir_2 == corpus_dir

@pytest.mark.slow
def test_demo_suggested_queries_accuracy():
    """
    Evaluates that all 8 suggested queries in manifest.json place their expected file
    in the top 3 search results. Marked slow as it exercises the full embedding pipeline.
    """
    demo_dir = os.path.join(app_home(), "demo")
    os.environ["COMPASS_DATA_DIR"] = demo_dir
    init_db()

    corpus_dir = setup_demo_corpus_if_needed()
    # Scan/index the corpus
    stats = scan_directory(corpus_dir, force=True)
    assert stats["scanned"] >= 40

    manifest = get_demo_manifest()
    queries = manifest.get("suggested_queries", [])
    assert len(queries) == 8

    for q_entry in queries:
        query_text = q_entry["query"]
        expected_file = q_entry["expected"].lower()
        res = route_and_search(query_text, limit=3)
        results = res.get("results", [])
        top3_filenames = [r["filename"].lower() for r in results[:3]]

        assert expected_file in top3_filenames, (
            f"Query '{query_text}' failed! Expected '{expected_file}' in top 3, but got: {top3_filenames}"
        )
