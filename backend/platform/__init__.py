from backend.platform.launcher import open_file, reveal_in_folder
from backend.platform.single_instance import SingleInstance
from backend.platform.window import show_or_open, find_compass_windows, focus_window, terminate_browser_process
from backend.platform.tray import run_tray, stop_tray, show_notification
from backend.platform.autostart import (
    is_enabled as is_autostart_enabled,
    enable as enable_autostart,
    disable as disable_autostart,
    build_autostart_command
)
from backend.platform.hotkey import (
    parse_hotkey_string,
    start_hotkey_listener,
    stop_hotkey_listener
)
from backend.platform.known_folders import get_known_folder, get_known_folders
from backend.platform.dialogs import pick_folder
from backend.platform.priority import set_thread_priority_below_normal

__all__ = [
    "open_file",
    "reveal_in_folder",
    "SingleInstance",
    "show_or_open",
    "find_compass_windows",
    "focus_window",
    "terminate_browser_process",
    "run_tray",
    "stop_tray",
    "show_notification",
    "is_autostart_enabled",
    "enable_autostart",
    "disable_autostart",
    "build_autostart_command",
    "parse_hotkey_string",
    "start_hotkey_listener",
    "stop_hotkey_listener",
    "get_known_folder",
    "get_known_folders",
    "pick_folder",
    "set_thread_priority_below_normal",
]
