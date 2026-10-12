import os
import sys
import shutil
import logging
import subprocess
import webbrowser
from typing import Optional, List

logger = logging.getLogger(__name__)

_browser_process: Optional[subprocess.Popen] = None

if sys.platform != "win32":
    def find_compass_windows() -> List[int]:
        raise NotImplementedError("Window management is currently only implemented for Windows.")

    def focus_window(hwnd: int) -> bool:
        raise NotImplementedError("Window management is currently only implemented for Windows.")

    def locate_browser_executable() -> Optional[str]:
        raise NotImplementedError("Browser detection is currently only implemented for Windows.")

    def show_or_open(port: Optional[int] = None) -> bool:
        raise NotImplementedError("Window management is currently only implemented for Windows.")

    def terminate_browser_process() -> None:
        pass

else:
    import ctypes
    from ctypes import wintypes
    import winreg
    from backend.paths import edge_profile_dir, get_runtime_port
    from backend.security.auth import mint_launch_url

    user32 = ctypes.windll.user32

    # Win32 Constants
    SW_RESTORE = 9
    SW_SHOW = 5
    FLASHW_ALL = 0x00000003
    FLASHW_TIMERNOFG = 0x0000000C

    # Win32 Function Signatures
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL

    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL

    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int

    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int

    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL

    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL

    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("hwnd", wintypes.HWND),
            ("dwFlags", wintypes.DWORD),
            ("uCount", wintypes.UINT),
            ("dwTimeout", wintypes.DWORD),
        ]

    user32.FlashWindowEx.argtypes = [ctypes.POINTER(FLASHWINFO)]
    user32.FlashWindowEx.restype = wintypes.BOOL

    def find_compass_windows() -> List[int]:
        """
        Enumerates top-level visible windows and returns HWNDs whose titles
        start with 'Compass'.
        """
        compass_hwnds: List[int] = []

        def _enum_proc(hwnd: int, lparam: int) -> bool:
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value
                    if title.startswith("Compass"):
                        compass_hwnds.append(hwnd)
            return True

        cb = WNDENUMPROC(_enum_proc)
        user32.EnumWindows(cb, 0)
        return compass_hwnds

    def flash_window(hwnd: int) -> bool:
        """Flashes the window caption and taskbar button to draw user attention."""
        finfo = FLASHWINFO()
        finfo.cbSize = ctypes.sizeof(FLASHWINFO)
        finfo.hwnd = hwnd
        finfo.dwFlags = FLASHW_ALL | FLASHW_TIMERNOFG
        finfo.uCount = 3
        finfo.dwTimeout = 0
        return bool(user32.FlashWindowEx(ctypes.byref(finfo)))

    def focus_window(hwnd: int) -> bool:
        """
        Restores window if minimized and attempts to set it as the foreground window.
        If SetForegroundWindow is refused by Windows (e.g. lock restriction), falls back
        to FlashWindowEx and logs the limitation.
        """
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        success = bool(user32.SetForegroundWindow(hwnd))
        if not success:
            logger.info("SetForegroundWindow refused by Windows foreground lock policy; falling back to FlashWindowEx.")
            flash_window(hwnd)
        return success

    def _query_app_path(reg_hive, subkey: str) -> Optional[str]:
        try:
            with winreg.OpenKey(reg_hive, subkey) as key:
                val, _ = winreg.QueryValueEx(key, "")
                if val and os.path.isfile(val):
                    return val
        except Exception:
            pass
        return None

    def locate_browser_executable() -> Optional[str]:
        """
        Locates msedge.exe via App Paths registry key or shutil.which.
        Falls back to chrome.exe if Edge is not available.
        Returns the absolute path to the executable, or None if neither is found.
        """
        # 1. Search for Microsoft Edge
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            p = _query_app_path(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe")
            if p:
                return p

        edge_which = shutil.which("msedge.exe") or shutil.which("msedge")
        if edge_which and os.path.isfile(edge_which):
            return os.path.abspath(edge_which)

        for candidate in [
            os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), r"Microsoft\Edge\Application\msedge.exe"),
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"Microsoft\Edge\Application\msedge.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\Application\msedge.exe"),
        ]:
            if os.path.isfile(candidate):
                return candidate

        # 2. Fall back to Google Chrome
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            p = _query_app_path(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
            if p:
                return p

        chrome_which = shutil.which("chrome.exe") or shutil.which("chrome")
        if chrome_which and os.path.isfile(chrome_which):
            return os.path.abspath(chrome_which)

        for candidate in [
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"Google\Chrome\Application\chrome.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), r"Google\Chrome\Application\chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
        ]:
            if os.path.isfile(candidate):
                return candidate

        return None

    def launch_browser_app(url: str) -> bool:
        """
        Spawns Edge (or Chrome) in standalone app mode with a dedicated profile.
        If neither browser is found, falls back to webbrowser.open with a warning.
        """
        global _browser_process
        browser_exe = locate_browser_executable()
        profile_dir = edge_profile_dir()

        if browser_exe:
            cmd = [
                browser_exe,
                f"--app={url}",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check"
            ]
            logger.info(f"Launching standalone app window: {browser_exe} with dedicated profile {profile_dir}")
            try:
                _browser_process = subprocess.Popen(cmd)
                return True
            except Exception as e:
                logger.error(f"Failed to spawn app mode browser: {e}")

        logger.warning("No standalone app browser (Edge/Chrome) found. Falling back to default system browser.")
        webbrowser.open(url)
        return False

    def show_or_open(port: Optional[int] = None) -> bool:
        """
        If a Compass window already exists, restores and focuses it.
        Otherwise mints a fresh launch URL and opens a dedicated-profile window.
        """
        compass_hwnds = find_compass_windows()
        if compass_hwnds:
            logger.info(f"Found existing Compass window (HWND {compass_hwnds[0]}); focusing.")
            focus_window(compass_hwnds[0])
            return True

        runtime_port = port if port is not None else get_runtime_port()
        fresh_url = mint_launch_url(runtime_port)
        logger.info(f"No existing Compass window found; opening new window with fresh launch URL on port {runtime_port}.")
        return launch_browser_app(fresh_url)

    def terminate_browser_process() -> None:
        """Terminates the dedicated-profile browser process if still active."""
        global _browser_process
        if _browser_process and _browser_process.poll() is None:
            logger.info("Terminating dedicated-profile browser process...")
            try:
                _browser_process.terminate()
                _browser_process.wait(timeout=2.0)
            except Exception as e:
                logger.warning(f"Browser process terminate timeout or error: {e}; killing.")
                try:
                    _browser_process.kill()
                except Exception:
                    pass
            _browser_process = None
