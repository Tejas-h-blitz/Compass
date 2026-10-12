import sys
import logging
import threading
from typing import Tuple, Optional, Callable

logger = logging.getLogger(__name__)

# Win32 Modifier Constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Win32 Virtual Key Constants
VK_SPACE = 0x20
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_F1 = 0x70

HOTKEY_ID = 1001
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

_active_hotkey_thread: Optional["HotkeyListenerThread"] = None

def parse_hotkey_string(combo: str) -> Tuple[int, int]:
    """
    Pure parser for hotkey strings like 'ctrl+alt+space'.
    Supports modifiers: ctrl, alt, shift, win.
    Supports keys: letters (a-z), digits (0-9), F1-F12, space, tab, enter, esc.
    Enforces MOD_NOREPEAT.
    Rejects combos with no modifier or invalid/unknown tokens.
    Returns (modifiers_bitmask, virtual_key_code).
    """
    if not combo or not combo.strip():
        raise ValueError("Hotkey combination string cannot be empty.")

    tokens = [t.strip().lower() for t in combo.split("+") if t.strip()]
    if not tokens:
        raise ValueError("No valid tokens found in hotkey combination.")

    modifiers = 0
    vk_code: Optional[int] = None

    for token in tokens:
        if token in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif token == "alt":
            modifiers |= MOD_ALT
        elif token == "shift":
            modifiers |= MOD_SHIFT
        elif token in ("win", "windows", "super"):
            modifiers |= MOD_WIN
        elif token == "space":
            if vk_code is not None:
                raise ValueError("Hotkey cannot have multiple non-modifier keys.")
            vk_code = VK_SPACE
        elif token == "tab":
            if vk_code is not None:
                raise ValueError("Hotkey cannot have multiple non-modifier keys.")
            vk_code = VK_TAB
        elif token in ("enter", "return"):
            if vk_code is not None:
                raise ValueError("Hotkey cannot have multiple non-modifier keys.")
            vk_code = VK_RETURN
        elif token in ("esc", "escape"):
            if vk_code is not None:
                raise ValueError("Hotkey cannot have multiple non-modifier keys.")
            vk_code = VK_ESCAPE
        elif len(token) == 1 and token.isalpha():
            if vk_code is not None:
                raise ValueError("Hotkey cannot have multiple non-modifier keys.")
            vk_code = ord(token.upper())
        elif len(token) == 1 and token.isdigit():
            if vk_code is not None:
                raise ValueError("Hotkey cannot have multiple non-modifier keys.")
            vk_code = ord(token)
        elif token.startswith("f") and token[1:].isdigit():
            f_num = int(token[1:])
            if 1 <= f_num <= 12:
                if vk_code is not None:
                    raise ValueError("Hotkey cannot have multiple non-modifier keys.")
                vk_code = VK_F1 + (f_num - 1)
            else:
                raise ValueError(f"Unsupported function key '{token}'. Only F1-F12 are supported.")
        else:
            raise ValueError(f"Unknown hotkey token: '{token}'")

    if modifiers == 0:
        raise ValueError(f"Hotkey '{combo}' must contain at least one modifier key (ctrl, alt, shift, win).")

    if vk_code is None:
        raise ValueError(f"Hotkey '{combo}' must include a non-modifier key.")

    return (modifiers | MOD_NOREPEAT, vk_code)

if sys.platform != "win32":
    def start_hotkey_listener(on_trigger: Callable[[], None], combo: Optional[str] = None) -> bool:
        raise NotImplementedError("Global hotkeys are currently only implemented for Windows.")

    def stop_hotkey_listener() -> None:
        pass

else:
    import ctypes
    from ctypes import wintypes
    from backend.settings import get_setting
    from backend.platform.tray import show_notification

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Win32 Function Signatures
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL

    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL

    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = wintypes.BOOL

    user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostThreadMessageW.restype = wintypes.BOOL

    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    class HotkeyListenerThread(threading.Thread):
        """
        Runs a dedicated Win32 message loop to register and listen for the global hotkey.
        """
        def __init__(self, modifiers: int, vk: int, combo_str: str, on_trigger: Callable[[], None]):
            super().__init__(name="CompassGlobalHotkeyThread", daemon=True)
            self.modifiers = modifiers
            self.vk = vk
            self.combo_str = combo_str
            self.on_trigger = on_trigger
            self.thread_id: Optional[int] = None
            self.is_registered: bool = False
            self.ready_event = threading.Event()

        def run(self):
            self.thread_id = kernel32.GetCurrentThreadId()
            # Register hotkey associated with this thread (hWnd=None)
            success = user32.RegisterHotKey(None, HOTKEY_ID, self.modifiers, self.vk)
            self.is_registered = bool(success)
            self.ready_event.set()

            if not success:
                err = kernel32.GetLastError()
                logger.warning(
                    f"RegisterHotKey failed for '{self.combo_str}' (Win32 error {err}). "
                    "The combination is likely already claimed by another application."
                )
                show_notification("Compass Hotkey Conflict", "Hotkey in use: change it in settings.json")
                return

            logger.info(f"Global hotkey '{self.combo_str}' registered successfully.")
            msg = wintypes.MSG()
            try:
                # Message loop for the thread
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                        logger.info(f"Global hotkey '{self.combo_str}' pressed! Summoning search window...")
                        try:
                            self.on_trigger()
                        except Exception as e:
                            logger.error(f"Error in hotkey callback: {e}")
            finally:
                user32.UnregisterHotKey(None, HOTKEY_ID)
                self.is_registered = False
                logger.info(f"Global hotkey '{self.combo_str}' unregistered.")

        def stop(self):
            """Cleanly posts WM_QUIT to the thread message loop."""
            if self.thread_id:
                user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
                self.join(timeout=1.0)

    def start_hotkey_listener(on_trigger: Callable[[], None], combo: Optional[str] = None) -> bool:
        """
        Parses configured hotkey from settings.json (default: ctrl+alt+space) and starts
        the background listening thread.
        If RegisterHotKey fails due to a conflict, logs a warning, alerts the tray, and
        allows the app to continue without crashing.
        """
        global _active_hotkey_thread
        stop_hotkey_listener()

        hotkey_str = combo if combo is not None else get_setting("hotkey", "ctrl+alt+space")
        try:
            modifiers, vk = parse_hotkey_string(hotkey_str)
        except Exception as e:
            logger.warning(f"Invalid hotkey configuration '{hotkey_str}': {e}. Falling back to 'ctrl+alt+space'.")
            hotkey_str = "ctrl+alt+space"
            modifiers, vk = parse_hotkey_string(hotkey_str)

        thread = HotkeyListenerThread(modifiers, vk, hotkey_str, on_trigger)
        thread.start()
        thread.ready_event.wait(timeout=1.0)
        _active_hotkey_thread = thread
        return thread.is_registered

    def stop_hotkey_listener() -> None:
        """Stops the active global hotkey listening thread if running."""
        global _active_hotkey_thread
        if _active_hotkey_thread:
            _active_hotkey_thread.stop()
            _active_hotkey_thread = None
