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
]
