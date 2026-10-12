import os
import json
import logging
from typing import Any, Dict, Optional
from backend.paths import settings_path as get_default_settings_path

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "hotkey": "ctrl+alt+space"
}

def load_settings(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads application settings from settings.json.
    If the file does not exist, writes and returns DEFAULT_SETTINGS.
    If the file is corrupt/unparseable, renames it to .bak, writes DEFAULT_SETTINGS,
    and logs a warning.
    """
    target_path = path if path is not None else get_default_settings_path()
    if not os.path.exists(target_path):
        save_settings(DEFAULT_SETTINGS, target_path)
        return dict(DEFAULT_SETTINGS)

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Settings file content is not a JSON object")
        # Ensure all default keys exist
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        return merged
    except Exception as e:
        logger.warning(f"Corrupt settings file detected at '{target_path}': {e}. Backing up to .bak and restoring defaults.")
        bak_path = target_path + ".bak"
        try:
            if os.path.exists(bak_path):
                os.remove(bak_path)
            os.replace(target_path, bak_path)
        except Exception as rename_err:
            logger.error(f"Failed to backup corrupt settings file: {rename_err}")

        save_settings(DEFAULT_SETTINGS, target_path)
        return dict(DEFAULT_SETTINGS)

def save_settings(settings: Dict[str, Any], path: Optional[str] = None) -> None:
    """
    Atomically writes settings dictionary to settings.json using a temporary file
    and os.replace.
    """
    target_path = path if path is not None else get_default_settings_path()
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    temp_path = f"{target_path}.tmp.{os.getpid()}"

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, target_path)
    except Exception as e:
        logger.error(f"Failed to atomically save settings to '{target_path}': {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise

def get_setting(key: str, default: Any = None, path: Optional[str] = None) -> Any:
    """Retrieves a single setting value, falling back to default if absent."""
    settings = load_settings(path)
    return settings.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))
