import sys
import logging
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)

DEFAULT_MUTEX_NAME = r"Local\CompassSingleInstance"
DEFAULT_EVENT_NAME = r"Local\CompassShowWindow"

if sys.platform != "win32":
    class SingleInstance:
        """Non-Windows stub raising NotImplementedError."""
        def __init__(self, mutex_name: str = DEFAULT_MUTEX_NAME, event_name: str = DEFAULT_EVENT_NAME):
            raise NotImplementedError("SingleInstance named mutex and event mechanism is currently only implemented for Windows.")

        def acquire(self) -> bool:
            raise NotImplementedError("SingleInstance is only supported on Windows.")

        def signal_existing_instance(self) -> bool:
            raise NotImplementedError("SingleInstance is only supported on Windows.")

        def start_listener(self, on_show_callback: Callable[[], None]) -> None:
            raise NotImplementedError("SingleInstance is only supported on Windows.")

        def close(self) -> None:
            pass

else:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32

    # Win32 Error codes and constants
    ERROR_ALREADY_EXISTS = 183
    EVENT_MODIFY_STATE = 0x0002
    SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0x00000000
    WAIT_TIMEOUT = 0x00000102

    # Configure ctypes argtypes and restype
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE

    kernel32.GetLastError.argtypes = []
    kernel32.GetLastError.restype = wintypes.DWORD

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateEventW.restype = wintypes.HANDLE

    kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenEventW.restype = wintypes.HANDLE

    kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    kernel32.SetEvent.restype = wintypes.BOOL

    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD

    class SingleInstance:
        """
        Enforces a single running instance of Compass per user session using a named mutex.
        A named event allows subsequent invocations to signal the primary instance to focus
        its search window before exiting.
        """
        def __init__(self, mutex_name: str = DEFAULT_MUTEX_NAME, event_name: str = DEFAULT_EVENT_NAME):
            self.mutex_name = mutex_name
            self.event_name = event_name
            self.mutex_handle: Optional[int] = None
            self.event_handle: Optional[int] = None
            self.is_primary: bool = False
            self._stop_listening = threading.Event()
            self._listener_thread: Optional[threading.Thread] = None

        def acquire(self) -> bool:
            """
            Attempts to acquire the per-session named mutex.
            Returns True if this is the primary instance.
            Returns False if another instance is already running.
            """
            self.mutex_handle = kernel32.CreateMutexW(None, False, self.mutex_name)
            last_error = kernel32.GetLastError()

            if not self.mutex_handle:
                logger.error(f"Failed to create mutex '{self.mutex_name}', error: {last_error}")
                return False

            if last_error == ERROR_ALREADY_EXISTS:
                self.is_primary = False
                return False

            self.is_primary = True
            return True

        def signal_existing_instance(self) -> bool:
            """
            Opens the named event and signals it, telling the primary instance
            to restore and focus its window.
            """
            h_event = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, self.event_name)
            if not h_event:
                logger.warning(f"Could not open event '{self.event_name}', error: {kernel32.GetLastError()}")
                return False

            try:
                success = bool(kernel32.SetEvent(h_event))
                if not success:
                    logger.warning(f"Failed to signal event '{self.event_name}', error: {kernel32.GetLastError()}")
                return success
            finally:
                kernel32.CloseHandle(h_event)

        def start_listener(self, on_show_callback: Callable[[], None]) -> None:
            """
            Creates the named event and starts a background thread waiting for show signals.
            """
            if not self.is_primary:
                raise RuntimeError("Cannot start event listener on secondary instance.")

            # Auto-reset event (bManualReset=False), initially non-signaled (bInitialState=False)
            self.event_handle = kernel32.CreateEventW(None, False, False, self.event_name)
            if not self.event_handle:
                logger.error(f"Failed to create show event '{self.event_name}', error: {kernel32.GetLastError()}")
                return

            self._stop_listening.clear()

            def _listener_loop():
                logger.info(f"SingleInstance listener started on event '{self.event_name}'")
                while not self._stop_listening.is_set():
                    # Wait 250ms per iteration to allow responsive thread exit
                    res = kernel32.WaitForSingleObject(self.event_handle, 250)
                    if res == WAIT_OBJECT_0:
                        logger.info("Show-event signaled by secondary launch! Invoking callback...")
                        try:
                            on_show_callback()
                        except Exception as e:
                            logger.error(f"Error in show-event callback: {e}")
                    elif res == WAIT_TIMEOUT:
                        continue
                    else:
                        break
                logger.info("SingleInstance listener stopped.")

            self._listener_thread = threading.Thread(target=_listener_loop, daemon=True, name="CompassSingleInstanceListener")
            self._listener_thread.start()

        def close(self) -> None:
            """Cleans up event listener thread and closes all Win32 handles."""
            self._stop_listening.set()
            if self._listener_thread and self._listener_thread.is_alive():
                self._listener_thread.join(timeout=1.0)
                self._listener_thread = None

            if self.event_handle:
                kernel32.CloseHandle(self.event_handle)
                self.event_handle = None

            if self.mutex_handle:
                kernel32.CloseHandle(self.mutex_handle)
                self.mutex_handle = None

        def __enter__(self):
            self.acquire()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()
