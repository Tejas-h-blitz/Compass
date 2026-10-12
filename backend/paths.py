import os
import sys
import socket
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

def repo_root() -> str:
    """Returns the absolute path to the Compass repository root directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def data_dir() -> str:
    """
    Returns the path to the Compass data directory.
    Uses COMPASS_DATA_DIR environment variable if set, otherwise defaults
    to the repo's data/ directory.
    """
    custom = os.environ.get("COMPASS_DATA_DIR")
    if custom:
        path = os.path.abspath(custom)
    else:
        path = os.path.join(repo_root(), "data")
    os.makedirs(path, exist_ok=True)
    return path

def app_home() -> str:
    """
    Returns the persistent application directory under %LOCALAPPDATA%\\Compass.
    Created on demand.
    """
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            local_app_data = os.path.expanduser("~\\AppData\\Local")
        home = os.path.join(local_app_data, "Compass")
    else:
        home = os.path.expanduser("~/.compass")
    os.makedirs(home, exist_ok=True)
    return home

def logs_dir() -> str:
    """Returns the path to the logs directory under app_home()."""
    path = os.path.join(app_home(), "logs")
    os.makedirs(path, exist_ok=True)
    return path

def edge_profile_dir() -> str:
    """Returns the path to the dedicated Edge browser profile directory."""
    path = os.path.join(app_home(), "edge-profile")
    os.makedirs(path, exist_ok=True)
    return path

def settings_path() -> str:
    """Returns the path to the user settings.json file."""
    return os.path.join(app_home(), "settings.json")

class _StdioToLogFile:
    """Redirects stdout/stderr writes to the log file when running under pythonw.exe."""
    def __init__(self, filepath: str):
        self.filepath = filepath

    def write(self, text: str):
        if text:
            try:
                with open(self.filepath, "a", encoding="utf-8", errors="replace") as f:
                    f.write(text)
            except Exception:
                pass

    def flush(self):
        pass

def setup_file_logging() -> str:
    """
    Configures the root logger with a RotatingFileHandler in %LOCALAPPDATA%\\Compass\\logs\\compass.log
    (1 MB x 3 backups).
    Redirects sys.stdout and sys.stderr if None (pythonw mode).
    Routes Uvicorn loggers into the same handlers to prevent formatter crashes without a console.
    Returns the path to the log file.
    """
    log_file = os.path.join(logs_dir(), "compass.log")
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Avoid duplicate file handlers if setup_file_logging is called multiple times
    has_file_handler = any(
        isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == os.path.abspath(log_file)
        for h in root_logger.handlers
    )
    
    if not has_file_handler:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1_048_576,  # 1 MB
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)

    # If running with a console, also keep a stream handler on stdout
    if sys.stdout is not None:
        has_stream_handler = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
            for h in root_logger.handlers
        )
        if not has_stream_handler:
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = logging.Formatter("%(levelname)s: %(message)s")
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(logging.INFO)
            root_logger.addHandler(console_handler)

    # In pythonw.exe, sys.stdout and sys.stderr are None
    if sys.stdout is None:
        sys.stdout = _StdioToLogFile(log_file)
    if sys.stderr is None:
        sys.stderr = _StdioToLogFile(log_file)

    # Route Uvicorn loggers into root logger
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        u_log = logging.getLogger(name)
        u_log.handlers = []
        u_log.propagate = True

    return log_file

def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Checks whether the specified port is available for binding on host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False

def choose_port(preferred: int = 8000, host: str = "127.0.0.1") -> int:
    """
    Returns preferred port if free on host; otherwise binds to an ephemeral
    free port allocated by the operating system and returns it.
    """
    if is_port_available(preferred, host):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]

_RUNTIME_PORT: Optional[int] = None

def set_runtime_port(port: int) -> None:
    """Sets the runtime port Compass is listening on."""
    global _RUNTIME_PORT
    _RUNTIME_PORT = port

def get_runtime_port() -> int:
    """Returns the current runtime port or defaults to 8000."""
    global _RUNTIME_PORT
    return _RUNTIME_PORT if _RUNTIME_PORT is not None else 8000

