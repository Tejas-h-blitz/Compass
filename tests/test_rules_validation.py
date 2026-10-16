import os
import sys
import pytest
from pathlib import Path

from backend.indexing.rules import should_ignore
from backend.indexing.validate import validate_monitored_path
from backend.paths import data_dir, app_home

def test_should_ignore_temp_and_lock_files():
    assert should_ignore("C:\\docs\\~$WordDoc.docx")
    assert should_ignore("C:\\docs\\tempfile.tmp")
    assert should_ignore("C:\\docs\\download.crdownload")
    assert should_ignore("C:\\docs\\partial_file.part")
    assert should_ignore("C:\\docs\\Thumbs.db")
    assert should_ignore("C:\\docs\\desktop.ini")
    assert should_ignore("C:\\docs\\.~lock.document.docx#")

def test_should_ignore_blacklisted_directories():
    assert should_ignore("C:\\projects\\.git\\HEAD")
    assert should_ignore("C:\\projects\\node_modules\\package\\index.js")
    assert should_ignore("C:\\projects\\.venv\\Scripts\\python.exe")
    assert should_ignore("C:\\projects\\dist\\bundle.js")
    assert should_ignore("C:\\projects\\build\\output.bin")

def test_should_ignore_unsupported_extensions():
    assert should_ignore("C:\\music\\song.mp3")
    assert should_ignore("C:\\videos\\movie.mp4")
    assert should_ignore("C:\\archives\\backup.zip")
    assert should_ignore("C:\\binaries\\program.exe")

def test_should_not_ignore_supported_files():
    assert not should_ignore("C:\\docs\\notes.txt", is_dir=False)
    assert not should_ignore("C:\\docs\\readme.md", is_dir=False)
    assert not should_ignore("C:\\docs\\report.pdf", is_dir=False)
    assert not should_ignore("C:\\docs\\paper.docx", is_dir=False)
    assert not should_ignore("C:\\code\\script.py", is_dir=False)

def test_should_ignore_compass_own_directories():
    c_data = data_dir()
    c_home = app_home()

    data_file = os.path.join(c_data, "compass.db")
    home_file = os.path.join(c_home, "settings.json")

    assert should_ignore(data_file)
    assert should_ignore(home_file)

def test_validate_monitored_path_drive_roots():
    res = validate_monitored_path("C:\\")
    assert not res.is_valid
    assert "Drive root" in res.error

def test_validate_monitored_path_system_directories():
    windir = os.environ.get("windir", "C:\\Windows")
    if os.path.exists(windir):
        res = validate_monitored_path(windir)
        assert not res.is_valid
        assert "Security restriction" in res.error

def test_validate_monitored_path_user_profile_root():
    userprofile = os.environ.get("USERPROFILE")
    if userprofile and os.path.exists(userprofile):
        res = validate_monitored_path(userprofile)
        assert not res.is_valid
        assert "user profile root" in res.error

def test_validate_monitored_path_own_data_dir():
    c_data = data_dir()
    res = validate_monitored_path(c_data)
    assert not res.is_valid
    assert "Compass" in res.error

def test_validate_monitored_path_existing_roots_coverage(tmp_path):
    root_a = tmp_path / "project_a"
    root_a.mkdir()
    child_a = root_a / "subfolder"
    child_a.mkdir()

    # Reject subfolder of existing root
    res = validate_monitored_path(str(child_a), existing_roots=[str(root_a)])
    assert not res.is_valid
    assert "already covered" in res.error

    # Reject duplicate
    res_dup = validate_monitored_path(str(root_a), existing_roots=[str(root_a)])
    assert not res_dup.is_valid
    assert "already monitored" in res_dup.error

    # Accept parent of existing root
    parent = tmp_path
    res_parent = validate_monitored_path(str(parent), existing_roots=[str(root_a)])
    assert res_parent.is_valid
