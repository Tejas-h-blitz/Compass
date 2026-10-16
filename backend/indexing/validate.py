import os
import sys
from typing import Optional, List, Tuple
from dataclasses import dataclass

from backend.paths import data_dir, app_home

@dataclass
class PathValidationResult:
    is_valid: bool
    canonical_path: Optional[str] = None
    error: Optional[str] = None

def _get_system_protected_dirs() -> List[str]:
    """Returns canonical paths for Windows system directories that must never be monitored."""
    protected = []
    env_keys = [
        "SystemRoot", "windir", "ProgramFiles", "ProgramFiles(x86)",
        "ProgramData", "APPDATA", "LOCALAPPDATA"
    ]
    for key in env_keys:
        val = os.environ.get(key)
        if val and os.path.exists(val):
            protected.append(os.path.normcase(os.path.realpath(val)))
    return protected

def validate_monitored_path(
    path: str,
    existing_roots: Optional[List[str]] = None
) -> PathValidationResult:
    r"""
    Validates a directory path for inclusion in monitored horizons.
    Returns PathValidationResult with canonical path on success, or structured error on rejection.
    Rejects:
    - Non-existent or non-directory paths
    - Drive roots (e.g. C:\)
    - System directories (%SystemRoot%, %ProgramFiles%, %APPDATA%, $Recycle.Bin, etc.)
    - User profile root itself (e.g. C:\Users\Alice)
    - Paths containing or inside Compass's own directories (data_dir, app_home)
    - Subfolders already covered by an existing monitored root (parents are allowed)
    """
    if not path or not path.strip():
        return PathValidationResult(is_valid=False, error="Path cannot be empty.")

    raw_path = path.strip()
    if not os.path.exists(raw_path):
        return PathValidationResult(is_valid=False, error=f"Directory does not exist: '{raw_path}'")

    if not os.path.isdir(raw_path):
        return PathValidationResult(is_valid=False, error=f"Path is not a directory: '{raw_path}'")

    canonical = os.path.realpath(os.path.abspath(raw_path))
    norm_canonical = os.path.normcase(canonical)

    # 1. Drive Root check (e.g. C:\, D:\)
    drive, rest = os.path.splitdrive(canonical)
    if rest in ("\\", "/", ""):
        return PathValidationResult(
            is_valid=False,
            error=f"Drive root ('{canonical}') cannot be monitored directly. Please select a specific subfolder."
        )

    # 2. Recycle Bin and System Volume Information
    parts_lower = [p.lower() for p in canonical.replace("/", "\\").split("\\") if p]
    if any(p in ("$recycle.bin", "system volume information") for p in parts_lower):
        return PathValidationResult(
            is_valid=False,
            error="Security restriction: Cannot monitor recycle bin or system volume folders."
        )

    # 3. Existing Monitored Roots Coverage
    if existing_roots is None:
        try:
            from backend.models.db import get_monitored_paths
            existing_roots = [m["path"] for m in get_monitored_paths()]
        except Exception:
            existing_roots = []

    for root in existing_roots:
        norm_root = os.path.normcase(os.path.realpath(root))
        if norm_canonical == norm_root:
            return PathValidationResult(
                is_valid=False,
                error=f"Directory is already monitored: '{canonical}'"
            )
        if norm_canonical.startswith(norm_root + os.path.sep):
            return PathValidationResult(
                is_valid=False,
                error=f"Path is already covered by monitored folder: '{root}'"
            )

    # 4. System Protected Directories
    import tempfile
    temp_dir = os.path.normcase(os.path.realpath(tempfile.gettempdir()))
    is_in_temp = norm_canonical.startswith(temp_dir + os.path.sep)

    protected_system_dirs = _get_system_protected_dirs()
    for sys_dir in protected_system_dirs:
        if norm_canonical == sys_dir or (not is_in_temp and norm_canonical.startswith(sys_dir + os.path.sep)):
            return PathValidationResult(
                is_valid=False,
                error=f"Security restriction: Cannot monitor system or application data directories ('{canonical}')."
            )

    # 5. User profile root itself (subfolders are allowed)
    user_profile = os.environ.get("USERPROFILE")
    if user_profile and os.path.exists(user_profile):
        norm_profile = os.path.normcase(os.path.realpath(user_profile))
        if norm_canonical == norm_profile:
            return PathValidationResult(
                is_valid=False,
                error="The user profile root folder cannot be monitored directly. Please select specific folders like Documents or Projects."
            )

    # 6. Compass's own data and application directories
    try:
        compass_dirs = [data_dir(), app_home()]
    except Exception:
        compass_dirs = []

    for c_dir in compass_dirs:
        if not c_dir:
            continue
        norm_c_dir = os.path.normcase(os.path.realpath(c_dir))
        # Inside Compass dir
        if norm_canonical == norm_c_dir or norm_canonical.startswith(norm_c_dir + os.path.sep):
            return PathValidationResult(
                is_valid=False,
                error="Cannot monitor Compass's internal data or profile directories."
            )
        # Contains Compass dir (parent of Compass dir)
        if norm_c_dir.startswith(norm_canonical + os.path.sep):
            return PathValidationResult(
                is_valid=False,
                error=f"Cannot monitor directory containing Compass's application data ('{c_dir}')."
            )

    return PathValidationResult(is_valid=True, canonical_path=canonical)
