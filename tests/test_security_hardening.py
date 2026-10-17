import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.main import app
import time as _time

from backend.models.db import (
    get_db_connection, add_monitored_path, get_monitored_paths,
    insert_or_update_file
)
from backend.security.auth import (
    generate_launch_code, reset_auth_state_for_testing
)

TEST_CORPUS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "test_corpus"))

# Files directly required by security tests (we only index these few to keep setup fast)
_REQUIRED_FILES = [
    "doc3_dummy_test.pdf",
    "climate_data_statistical_analysis.py",
]

@pytest.fixture(autouse=True)
def setup_auth_and_monitored():
    reset_auth_state_for_testing()
    add_monitored_path(TEST_CORPUS_DIR, "Test Corpus")

    # Seed the required files directly into SQLite without triggering ChromaDB so
    # that /api/log-access can locate them in the files table even on a fresh DB.
    now = _time.time()
    for fname in _REQUIRED_FILES:
        fpath = os.path.join(TEST_CORPUS_DIR, fname)
        if not os.path.exists(fpath):
            continue
        st = os.stat(fpath)
        _, ext = os.path.splitext(fname)
        try:
            content = open(fpath, "r", encoding="utf-8", errors="ignore").read() if ext not in {".pdf"} else ""
        except Exception:
            content = ""
        insert_or_update_file(
            filepath=os.path.abspath(fpath),
            filename=fname,
            file_type=ext,
            file_size=st.st_size,
            created_at=st.st_ctime,
            modified_at=st.st_mtime,
            content=content,
        )
    yield

@pytest.fixture
def auth_client():
    client = TestClient(app, base_url="http://127.0.0.1:8000")
    code = generate_launch_code()
    res = client.get(f"/?launch={code}", follow_redirects=False)
    assert res.status_code == 303
    assert "compass_session" in res.cookies
    return client

@pytest.fixture
def unauth_client():
    return TestClient(app, base_url="http://127.0.0.1:8000")

def get_access_log_count(filepath: str) -> int:
    conn = get_db_connection()
    norm = os.path.normcase(os.path.realpath(filepath))
    cursor = conn.cursor()
    cursor.execute("SELECT filepath FROM access_log")
    rows = cursor.fetchall()
    conn.close()
    return sum(1 for (p,) in rows if os.path.normcase(os.path.realpath(p)) == norm)

# -------------------------------------------------------------
# TASK 1 LAUNCH SECURITY TESTS
# -------------------------------------------------------------

def test_path_not_in_index_is_rejected_and_not_logged(auth_client, monkeypatch):
    """
    Paths not indexed in the files table must return 404, not launch,
    and not record any access log entry.
    """
    open_calls = []
    reveal_calls = []
    monkeypatch.setattr("backend.main.open_file", lambda p: open_calls.append(p))
    monkeypatch.setattr("backend.main.reveal_in_folder", lambda p: reveal_calls.append(p))

    unindexed_path = os.path.join(TEST_CORPUS_DIR, "nonexistent_file_xyz123.pdf")
    initial_count = get_access_log_count(unindexed_path)

    res = auth_client.post("/api/log-access", json={"filepath": unindexed_path})
    assert res.status_code == 404
    assert "not" in res.json()["detail"].lower()
    assert len(open_calls) == 0
    assert len(reveal_calls) == 0
    assert get_access_log_count(unindexed_path) == initial_count

def test_path_traversal_and_non_normalized_variants_safe(auth_client, monkeypatch):
    """
    Non-normalized paths (e.g. using '..' or mixed slashes) resolving to an indexed
    file should be safely normalized and handled without permitting traversal escape.
    """
    open_calls = []
    monkeypatch.setattr("backend.main.open_file", lambda p: open_calls.append(p))
    monkeypatch.setattr("backend.main.reveal_in_folder", lambda p: None)

    real_indexed_pdf = os.path.join(TEST_CORPUS_DIR, "doc3_dummy_test.pdf")
    initial_count = get_access_log_count(real_indexed_pdf)

    # 1. Non-normalized variant resolving to indexed file
    non_norm_variant = os.path.join(TEST_CORPUS_DIR, "subdir", "..", "doc3_dummy_test.pdf")
    res1 = auth_client.post("/api/log-access", json={"filepath": non_norm_variant})
    assert res1.status_code == 200
    assert res1.json()["launched"] is True
    assert len(open_calls) == 1
    assert get_access_log_count(real_indexed_pdf) == initial_count + 1

    # 2. Path traversal escaping to unindexed outside file (e.g. system binary)
    escape_path = os.path.join(TEST_CORPUS_DIR, "..", "..", "Windows", "System32", "calc.exe")
    res2 = auth_client.post("/api/log-access", json={"filepath": escape_path})
    assert res2.status_code in (403, 404)
    assert len(open_calls) == 1  # No additional calls

def test_path_outside_monitored_paths_is_rejected(auth_client, monkeypatch, tmp_path):
    """
    Even if a file exists on disk, if it is outside registered monitored paths
    or not indexed, it must be rejected with 403 or 404 and not logged.
    """
    open_calls = []
    monkeypatch.setattr("backend.main.open_file", lambda p: open_calls.append(p))

    # Create a real file on disk outside monitored horizons
    outside_file = tmp_path / "secret_unmonitored.txt"
    outside_file.write_text("Hello outside")

    initial_count = get_access_log_count(str(outside_file))
    res = auth_client.post("/api/log-access", json={"filepath": str(outside_file)})
    assert res.status_code in (403, 404)
    assert len(open_calls) == 0
    assert get_access_log_count(str(outside_file)) == initial_count

def test_blocklisted_extension_triggers_reveal_not_open(auth_client, monkeypatch):
    """
    Executable and script files (.py, .exe, .bat, etc.) must NEVER be launched.
    They must trigger reveal_in_folder instead.
    """
    open_calls = []
    reveal_calls = []
    monkeypatch.setattr("backend.main.open_file", lambda p: open_calls.append(p))
    monkeypatch.setattr("backend.main.reveal_in_folder", lambda p: reveal_calls.append(p))

    py_file = os.path.join(TEST_CORPUS_DIR, "climate_data_statistical_analysis.py")
    assert os.path.exists(py_file)
    initial_count = get_access_log_count(py_file)

    res = auth_client.post("/api/log-access", json={"filepath": py_file})
    assert res.status_code == 200
    data = res.json()
    assert data["launched"] is False
    assert data["revealed"] is True
    assert data["action"] == "revealed"
    assert len(open_calls) == 0
    assert len(reveal_calls) == 1
    assert get_access_log_count(py_file) == initial_count + 1

def test_normal_indexed_pdf_triggers_open_file_and_logs(auth_client, monkeypatch):
    """
    Normal indexed documents (.pdf, .docx, .txt) must trigger open_file and log an access row.
    """
    open_calls = []
    reveal_calls = []
    monkeypatch.setattr("backend.main.open_file", lambda p: open_calls.append(p))
    monkeypatch.setattr("backend.main.reveal_in_folder", lambda p: reveal_calls.append(p))

    pdf_file = os.path.join(TEST_CORPUS_DIR, "doc3_dummy_test.pdf")
    assert os.path.exists(pdf_file)
    initial_count = get_access_log_count(pdf_file)

    res = auth_client.post("/api/log-access", json={"filepath": pdf_file})
    assert res.status_code == 200
    data = res.json()
    assert data["launched"] is True
    assert data["revealed"] is False
    assert data["action"] == "launched"
    assert len(open_calls) == 1
    assert len(reveal_calls) == 0
    assert get_access_log_count(pdf_file) == initial_count + 1

# -------------------------------------------------------------
# TASK 2 AUTH & SECURITY MIDDLEWARE TESTS
# -------------------------------------------------------------

def test_api_auth_no_cookie_returns_401(unauth_client):
    """Requests to /api/* without a valid session cookie must return HTTP 401."""
    res = unauth_client.get("/api/stats")
    assert res.status_code == 401
    assert "unauthorized" in res.json()["detail"].lower()

def test_api_auth_bad_host_is_rejected(auth_client):
    """Requests with disallowed Host header (e.g. DNS rebinding) must be rejected with 400."""
    res = auth_client.get("/api/stats", headers={"Host": "evil.example.com"})
    assert res.status_code == 400
    assert "host" in res.json()["detail"].lower()

def test_api_auth_valid_session_returns_200(auth_client):
    """Requests with a valid session cookie and valid host must return 200."""
    res = auth_client.get("/api/stats")
    assert res.status_code == 200
    assert "total_files" in res.json()

def test_launch_code_is_single_use(unauth_client):
    """One-time launch codes must be single-use and cannot be redeemed twice."""
    code = generate_launch_code()
    # First use: succeeds with 303 redirect and sets cookie
    res1 = unauth_client.get(f"/?launch={code}", follow_redirects=False)
    assert res1.status_code == 303
    assert "compass_session" in res1.cookies

    # Second use: must fail with 401
    res2 = unauth_client.get(f"/?launch={code}", follow_redirects=False)
    assert res2.status_code == 401

def test_disallowed_cross_origin_rejected(auth_client):
    """State-changing requests with an external Origin header must return 403."""
    res = auth_client.post(
        "/api/log-access",
        json={"filepath": "doc.pdf"},
        headers={"Origin": "https://attacker.site"}
    )
    assert res.status_code == 403
    assert "cross-origin" in res.json()["detail"].lower()
