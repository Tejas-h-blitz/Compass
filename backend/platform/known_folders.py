import os
import sys
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

if sys.platform != "win32":
    def get_known_folder(name: str) -> Optional[str]:
        raise NotImplementedError("Known folders via SHGetKnownFolderPath is only supported on Windows.")

    def get_known_folders() -> Dict[str, str]:
        # Graceful fallback for non-Windows dev / testing
        folders = {}
        for name in ("Documents", "Downloads", "Desktop"):
            p = os.path.expanduser(f"~/{name}")
            if os.path.exists(p):
                folders[name] = p
        return folders
else:
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", wintypes.BYTE * 8)
        ]

    # Known folder GUIDs (Windows Vista+)
    FOLDERID_DOCUMENTS = GUID(0xFDD39AD0, 0x238F, 0x46AF, (wintypes.BYTE * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
    FOLDERID_DOWNLOADS = GUID(0x374DE290, 0x123F, 0x4565, (wintypes.BYTE * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
    FOLDERID_DESKTOP   = GUID(0xB4BFCC3A, 0xDB2C, 0x424C, (wintypes.BYTE * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41))

    FOLDER_GUIDS = {
        "Documents": FOLDERID_DOCUMENTS,
        "Downloads": FOLDERID_DOWNLOADS,
        "Desktop":   FOLDERID_DESKTOP
    }

    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32

    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(GUID),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.LPWSTR)
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long

    ole32.CoTaskMemFree.argtypes = [wintypes.LPVOID]
    ole32.CoTaskMemFree.restype = None

    def get_known_folder(name: str) -> Optional[str]:
        """
        Retrieves the true canonical path of a Windows known folder (Documents, Downloads, Desktop)
        using SHGetKnownFolderPath, resolving OneDrive-redirected folders correctly.
        Frees the allocated memory with CoTaskMemFree. Falls back to os.path.expanduser.
        """
        guid = FOLDER_GUIDS.get(name)
        if not guid:
            return None

        p_path = wintypes.LPWSTR()
        try:
            hr = shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(p_path))
            if hr == 0 and p_path.value:
                path = p_path.value
                return os.path.abspath(path)
        except Exception as e:
            logger.debug(f"SHGetKnownFolderPath failed for {name}: {e}")
        finally:
            if p_path.value is not None:
                try:
                    ole32.CoTaskMemFree(p_path)
                except Exception:
                    pass

        # Fallback to standard user home directory
        fallback = os.path.expanduser(f"~/{name}")
        if os.path.exists(fallback):
            return os.path.abspath(fallback)
        return None

    def get_known_folders() -> Dict[str, str]:
        """Returns a mapping of folder name to absolute path for known folders that exist on disk."""
        result = {}
        for name in ("Documents", "Downloads", "Desktop"):
            path = get_known_folder(name)
            if path and os.path.exists(path) and os.path.isdir(path):
                result[name] = path
        return result
