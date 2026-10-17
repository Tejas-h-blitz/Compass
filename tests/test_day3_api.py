import os
import sys
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.security.auth import SESSION_COOKIE_NAME, generate_launch_code, consume_launch_code

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_client():
    c = TestClient(app)
    token = consume_launch_code(generate_launch_code())
    c.cookies.set(SESSION_COOKIE_NAME, token)
    c.headers.update({"Host": "127.0.0.1:8000"})
    return c

NEW_ROUTES = [
    ("GET", "/api/index/status"),
    ("POST", "/api/index/pause"),
    ("POST", "/api/index/resume"),
    ("POST", "/api/index/rescan"),
    ("GET", "/api/monitored"),
    ("POST", "/api/monitored"),
    ("DELETE", "/api/monitored"),
    ("POST", "/api/monitored/estimate"),
    ("GET", "/api/system/known-folders"),
    ("POST", "/api/system/pick-folder"),
    ("GET", "/api/system/info"),
    ("POST", "/api/system/mode"),
    ("POST", "/api/demo/simulate-history"),
    ("GET", "/api/demo/suggested-queries"),
]

@pytest.mark.parametrize("method,path", NEW_ROUTES)
def test_new_routes_return_401_unauthenticated(client, method, path):
    if method == "GET":
        resp = client.get(path)
    elif method == "POST":
        resp = client.post(path, json={})
    elif method == "DELETE":
        resp = client.delete(path)
    assert resp.status_code == 401, f"Expected 401 for unauthenticated {method} {path}, got {resp.status_code}"

def test_authenticated_index_status_and_system_info(auth_client):
    r_status = auth_client.get("/api/index/status")
    assert r_status.status_code == 200
    data = r_status.json()
    assert "state" in data
    assert "roots" in data
    assert "counters" in data

    r_info = auth_client.get("/api/system/info")
    assert r_info.status_code == 200
    info = r_info.json()
    assert info["version"] == "0.3.0"
    assert info["mode"] in ("normal", "demo")

def test_estimate_bounded(auth_client, tmp_path):
    # Test estimate on empty directory
    r = auth_client.post("/api/monitored/estimate", json={"path": str(tmp_path)})
    assert r.status_code == 200
    res = r.json()
    assert "supported_files" in res
    assert "capped" in res
    assert res["supported_files"] == 0

def test_simulate_history_forbidden_in_normal_mode(auth_client):
    # Ensure normal data dir
    os.environ.pop("COMPASS_DATA_DIR", None)
    r = auth_client.post("/api/demo/simulate-history")
    assert r.status_code == 403

@pytest.mark.skipif(sys.platform != "win32", reason="Windows known folders test")
def test_known_folders_resolve_on_windows(auth_client):
    r = auth_client.get("/api/system/known-folders")
    assert r.status_code == 200
    folders = r.json().get("folders", {})
    assert len(folders) > 0
    for name, path in folders.items():
        assert os.path.exists(path), f"Known folder '{name}' does not exist on disk: {path}"
