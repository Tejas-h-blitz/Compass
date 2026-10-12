import os
import sys
import socket
import uuid
import threading
import pytest

from backend.paths import choose_port
from backend.security.auth import mint_launch_url
from backend.settings import load_settings, save_settings, get_setting

# Mark all tests in this file as windows-only
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows app shell tests require Windows")

if sys.platform == "win32":
    import winreg
    from backend.platform.hotkey import (
        parse_hotkey_string,
        MOD_ALT,
        MOD_CONTROL,
        MOD_SHIFT,
        MOD_WIN,
        MOD_NOREPEAT,
        VK_SPACE,
        VK_F1
    )
    from backend.platform.autostart import (
        build_autostart_command,
        enable as enable_autostart,
        disable as disable_autostart,
        is_enabled as is_autostart_enabled
    )
    from backend.platform.single_instance import SingleInstance

# -------------------------------------------------------------
# TASK 5: HOTKEY PARSER TESTS
# -------------------------------------------------------------

def test_hotkey_parser_valid_combos():
    """Valid hotkey string combinations must parse correctly with MOD_NOREPEAT."""
    # ctrl+alt+space
    mods, vk = parse_hotkey_string("ctrl+alt+space")
    assert vk == VK_SPACE
    assert mods & MOD_CONTROL
    assert mods & MOD_ALT
    assert mods & MOD_NOREPEAT

    # ctrl+shift+f1 (case-insensitive with whitespace)
    mods, vk = parse_hotkey_string("Ctrl + Shift + F1")
    assert vk == VK_F1
    assert mods & MOD_CONTROL
    assert mods & MOD_SHIFT
    assert mods & MOD_NOREPEAT

    # win+alt+k
    mods, vk = parse_hotkey_string("win+alt+k")
    assert vk == ord("K")
    assert mods & MOD_WIN
    assert mods & MOD_ALT

    # ctrl+9
    mods, vk = parse_hotkey_string("ctrl+9")
    assert vk == ord("9")
    assert mods & MOD_CONTROL

def test_hotkey_parser_rejects_bare_key():
    """Hotkey combos lacking at least one modifier must be rejected."""
    with pytest.raises(ValueError, match="at least one modifier"):
        parse_hotkey_string("space")

    with pytest.raises(ValueError, match="at least one modifier"):
        parse_hotkey_string("k")

    with pytest.raises(ValueError, match="at least one modifier"):
        parse_hotkey_string("f5")

def test_hotkey_parser_rejects_invalid_tokens():
    """Combos with unknown tokens or missing keys must be rejected."""
    with pytest.raises(ValueError, match="Unknown hotkey token"):
        parse_hotkey_string("ctrl+alt+unknown_key")

    with pytest.raises(ValueError, match="non-modifier key"):
        parse_hotkey_string("ctrl+alt")

    with pytest.raises(ValueError, match="empty"):
        parse_hotkey_string("")

    with pytest.raises(ValueError, match="multiple non-modifier keys"):
        parse_hotkey_string("ctrl+a+b")

# -------------------------------------------------------------
# TASK 4: AUTOSTART COMMAND BUILDER & REGISTRY TESTS
# -------------------------------------------------------------

def test_autostart_command_builder_source():
    """Source mode command builder quotes paths and points to pythonw.exe with --background."""
    fake_app_py = r"C:\Folder With Spaces\app.py"
    cmd = build_autostart_command(fake_app_py)
    assert "--background" in cmd
    assert f'"{os.path.abspath(fake_app_py)}"' in cmd
    assert "pythonw.exe" in cmd.lower() or "python.exe" in cmd.lower()

def test_autostart_command_builder_frozen(monkeypatch):
    """Frozen builds must use sys.executable directly."""
    fake_exe = r"C:\Program Files\Compass\Compass.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", fake_exe)

    cmd = build_autostart_command()
    assert cmd == f'"{fake_exe}" --background'

def test_autostart_enable_disable_throwaway_registry_key():
    """Autostart operations against an isolated throwaway registry key."""
    throwaway_key = rf"Software\CompassTest_{uuid.uuid4().hex}"
    test_cmd = r'"C:\Compass\pythonw.exe" "C:\Compass\app.py" --background'

    try:
        # Initially not enabled
        assert is_autostart_enabled(key_path=throwaway_key) is False

        # Enable
        assert enable_autostart(command=test_cmd, key_path=throwaway_key) is True
        assert is_autostart_enabled(key_path=throwaway_key) is True

        # Disable
        assert disable_autostart(key_path=throwaway_key) is True
        assert is_autostart_enabled(key_path=throwaway_key) is False
    finally:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, throwaway_key)
        except Exception:
            pass

# -------------------------------------------------------------
# TASK 5: SETTINGS TESTS
# -------------------------------------------------------------

def test_settings_defaults_and_roundtrip(tmp_path):
    """Settings loads defaults on fresh file and persists custom keys."""
    settings_file = str(tmp_path / "settings.json")
    
    # 1. Defaults loaded
    initial = load_settings(path=settings_file)
    assert initial["hotkey"] == "ctrl+alt+space"
    assert os.path.isfile(settings_file)

    # 2. Save custom setting
    initial["hotkey"] = "ctrl+shift+space"
    save_settings(initial, path=settings_file)

    reloaded = load_settings(path=settings_file)
    assert reloaded["hotkey"] == "ctrl+shift+space"

def test_settings_corrupt_file_recovery(tmp_path):
    """Corrupt settings file is backed up to .bak and default settings are restored."""
    settings_file = str(tmp_path / "settings.json")
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write("{this is invalid json: !!!")

    recovered = load_settings(path=settings_file)
    assert recovered["hotkey"] == "ctrl+alt+space"
    assert os.path.isfile(settings_file + ".bak")

# -------------------------------------------------------------
# TASK 2: SINGLE INSTANCE TESTS
# -------------------------------------------------------------

def test_single_instance_mutex_and_show_event():
    """Second acquisition fails and signals show event to primary listener."""
    unique_id = uuid.uuid4().hex
    mutex_name = rf"Local\CompassTestMut_{unique_id}"
    event_name = rf"Local\CompassTestEvt_{unique_id}"

    inst1 = SingleInstance(mutex_name=mutex_name, event_name=event_name)
    inst2 = SingleInstance(mutex_name=mutex_name, event_name=event_name)

    try:
        # Primary acquisition succeeds
        assert inst1.acquire() is True

        # Secondary acquisition reports already running
        assert inst2.acquire() is False

        # Start show-event listener on primary
        event_received = threading.Event()
        inst1.start_listener(lambda: event_received.set())

        # Secondary signals show event
        assert inst2.signal_existing_instance() is True

        # Wait for primary to receive signal
        assert event_received.wait(timeout=2.0) is True
    finally:
        inst2.close()
        inst1.close()

# -------------------------------------------------------------
# TASK 0 & 1: MINT LAUNCH URL & PORT SELECTION TESTS
# -------------------------------------------------------------

def test_mint_launch_url_yields_distinct_codes():
    """Each call to mint_launch_url must produce a fresh, distinct URL and single-use code."""
    url1 = mint_launch_url(8000)
    url2 = mint_launch_url(8000)
    url3 = mint_launch_url(8001)

    assert url1 != url2
    assert "8000" in url1
    assert "8000" in url2
    assert "8001" in url3
    assert "?launch=" in url1

def test_choose_port_fallback_when_preferred_occupied():
    """choose_port falls back to an available ephemeral port if preferred is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        occupied_port = s.getsockname()[1]

        chosen = choose_port(preferred=occupied_port)
        assert chosen != occupied_port
        assert chosen > 0
