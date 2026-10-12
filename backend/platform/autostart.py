import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_VALUE_NAME = "Compass"

if sys.platform != "win32":
    def build_autostart_command(app_py_path: Optional[str] = None) -> str:
        raise NotImplementedError("Autostart is currently only implemented for Windows.")

    def is_enabled(key_path: str = DEFAULT_RUN_KEY, hive: Optional[int] = None) -> bool:
        raise NotImplementedError("Autostart is currently only implemented for Windows.")

    def enable(command: Optional[str] = None, key_path: str = DEFAULT_RUN_KEY, hive: Optional[int] = None) -> bool:
        raise NotImplementedError("Autostart is currently only implemented for Windows.")

    def disable(key_path: str = DEFAULT_RUN_KEY, hive: Optional[int] = None) -> bool:
        raise NotImplementedError("Autostart is currently only implemented for Windows.")

else:
    import winreg

    def build_autostart_command(app_py_path: Optional[str] = None) -> str:
        """
        Builds the shell command string for autostart.
        If running as a frozen executable (sys.frozen), returns:
          "<sys.executable>" --background
        If running from source, locates pythonw.exe in the current environment and returns:
          "<pythonw.exe>" "<app.py>" --background
        Quoting handles paths containing spaces.
        """
        if getattr(sys, "frozen", False):
            exe = os.path.abspath(sys.executable)
            return f'"{exe}" --background'

        if app_py_path is None:
            from backend.paths import repo_root
            app_py_path = os.path.join(repo_root(), "app.py")
        abs_app_py = os.path.abspath(app_py_path)

        # Look for pythonw.exe in the same directory as current python interpreter
        py_dir = os.path.dirname(sys.executable)
        pythonw_path = os.path.join(py_dir, "pythonw.exe")
        if not os.path.isfile(pythonw_path):
            pythonw_path = sys.executable

        abs_pythonw = os.path.abspath(pythonw_path)
        return f'"{abs_pythonw}" "{abs_app_py}" --background'

    def is_enabled(key_path: str = DEFAULT_RUN_KEY, hive: int = winreg.HKEY_CURRENT_USER) -> bool:
        """
        Checks whether the Compass autostart entry is present in the specified registry key.
        The registry is the single source of truth.
        """
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, APP_VALUE_NAME)
                return bool(val)
        except (FileNotFoundError, OSError):
            return False

    def enable(command: Optional[str] = None, key_path: str = DEFAULT_RUN_KEY, hive: int = winreg.HKEY_CURRENT_USER) -> bool:
        """
        Sets the Compass autostart value under the given registry key.
        """
        cmd_str = command if command is not None else build_autostart_command()
        try:
            with winreg.CreateKeyEx(hive, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, APP_VALUE_NAME, 0, winreg.REG_SZ, cmd_str)
                logger.info(f"Enabled autostart: {APP_VALUE_NAME} -> {cmd_str}")
                return True
        except Exception as e:
            logger.error(f"Failed to enable autostart in registry: {e}")
            return False

    def disable(key_path: str = DEFAULT_RUN_KEY, hive: int = winreg.HKEY_CURRENT_USER) -> bool:
        """
        Removes the Compass autostart value from the specified registry key.
        """
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, APP_VALUE_NAME)
                logger.info(f"Disabled autostart: removed {APP_VALUE_NAME} from registry")
                return True
        except FileNotFoundError:
            # Already disabled
            return True
        except Exception as e:
            logger.error(f"Failed to disable autostart in registry: {e}")
            return False
