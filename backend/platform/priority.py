import sys
import logging

logger = logging.getLogger(__name__)

if sys.platform != "win32":
    def set_thread_priority_below_normal() -> bool:
        raise NotImplementedError("Thread priority management is only supported on Windows.")
else:
    import ctypes
    from ctypes import wintypes

    # Windows Thread Priority constants
    THREAD_PRIORITY_BELOW_NORMAL = -1

    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentThread.restype = wintypes.HANDLE
    kernel32.SetThreadPriority.argtypes = [wintypes.HANDLE, ctypes.c_int]
    kernel32.SetThreadPriority.restype = wintypes.BOOL

    def set_thread_priority_below_normal() -> bool:
        """
        Sets the calling thread's priority to THREAD_PRIORITY_BELOW_NORMAL (-1).
        Ensures background indexing worker threads do not starve UI or search queries.
        """
        try:
            thread_handle = kernel32.GetCurrentThread()
            success = kernel32.SetThreadPriority(thread_handle, THREAD_PRIORITY_BELOW_NORMAL)
            if success:
                logger.debug("Successfully lowered indexing worker thread priority.")
                return True
            else:
                logger.warning(f"Failed to lower thread priority (error code {kernel32.GetLastError()}).")
                return False
        except Exception as e:
            logger.warning(f"Failed to set thread priority: {e}")
            return False
