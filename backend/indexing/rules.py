import os
from typing import Optional, List, Set
from pathlib import Path
from backend.paths import data_dir, app_home

IGNORED_DIR_NAMES: Set[str] = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "env",
    ".next", "dist", "build", ".idea", ".vscode", "$recycle.bin",
    "system volume information", ".ssh", ".aws"
}

TEMP_FILE_PREFIXES = ("~$", ".~lock.")
TEMP_FILE_SUFFIXES = (".tmp", ".crdownload", ".part", ".partial")
EXACT_IGNORED_FILENAMES: Set[str] = {"thumbs.db", "desktop.ini"}

SUPPORTED_EXTENSIONS: Set[str] = {
    ".txt", ".md", ".pdf", ".docx", ".py", ".js", ".ts",
    ".html", ".css", ".java", ".c", ".cpp", ".h", ".json",
    ".yaml", ".yml", ".csv"
}

def is_within_directory(child_path: str, parent_path: str) -> bool:
    """Returns True if child_path is inside or equal to parent_path."""
    norm_child = os.path.normcase(os.path.abspath(child_path))
    norm_parent = os.path.normcase(os.path.abspath(parent_path))
    if norm_child == norm_parent:
        return True
    prefix = norm_parent if norm_parent.endswith(os.path.sep) else norm_parent + os.path.sep
    return norm_child.startswith(prefix)

def should_ignore(
    path: str,
    roots: Optional[List[str]] = None,
    protected_dirs: Optional[List[str]] = None,
    is_dir: Optional[bool] = None
) -> bool:
    """
    Pure filtering logic determining whether a path should be excluded from indexing.
    Excludes:
    - Anything inside Compass's own data_dir() or app_home() (prevents infinite index loops)
    - Blacklisted directory names (.git, node_modules, .venv, etc.)
    - Temp/lock/partial files (~$*, *.tmp, *.crdownload, *.part, Thumbs.db, desktop.ini)
    - Files with unsupported extensions
    - Symlinks / junction points
    """
    if not path or not path.strip():
        return True

    norm_path = os.path.normcase(os.path.abspath(path))

    # 1. Protect Compass data and application home directories
    if protected_dirs is None:
        try:
            protected_dirs = [data_dir(), app_home()]
        except Exception:
            protected_dirs = []

    for p in protected_dirs:
        if p and is_within_directory(norm_path, p):
            return True

    # 2. Check for symlinks/junctions
    try:
        if os.path.islink(path):
            return True
    except Exception:
        pass

    path_obj = Path(norm_path)

    # 3. Check directory parts
    parts_to_check = path_obj.parts
    if roots:
        for r in roots:
            norm_r = os.path.normcase(os.path.abspath(r))
            if norm_path == norm_r or norm_path.startswith(norm_r.rstrip(os.path.sep) + os.path.sep):
                rel = os.path.relpath(norm_path, norm_r)
                parts_to_check = Path(rel).parts
                break

    for part in parts_to_check:
        clean_part = part.rstrip(os.path.sep).lower()
        if clean_part in IGNORED_DIR_NAMES:
            return True

    # Determine if this is a directory
    if is_dir is None:
        try:
            is_dir = os.path.isdir(path)
        except Exception:
            is_dir = False

    if is_dir:
        # Directory names were checked; directory itself is not rejected by extension
        return False

    # 4. File-specific checks
    filename = path_obj.name.lower()
    if not filename:
        return True

    # Exact filename match
    if filename in EXACT_IGNORED_FILENAMES:
        return True

    # Temporary / lock prefixes
    for prefix in TEMP_FILE_PREFIXES:
        if filename.startswith(prefix):
            return True

    # Partial / temp suffixes
    for suffix in TEMP_FILE_SUFFIXES:
        if filename.endswith(suffix):
            return True

    # Hidden dotfiles (e.g. .DS_Store, .gitignore) unless supported extension like .yaml/.json
    if filename.startswith(".") and not any(filename.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        return True

    # 5. Extension check
    suffix = path_obj.suffix.lower()
    if not suffix or suffix not in SUPPORTED_EXTENSIONS:
        return True

    return False
