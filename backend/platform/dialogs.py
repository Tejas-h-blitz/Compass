import sys
import logging
import threading
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

_dialog_lock = threading.Lock()

if sys.platform != "win32":
    def pick_folder(title: str = "Select folder to monitor") -> Optional[str]:
        raise NotImplementedError("Folder picker dialog is currently only implemented for Windows.")
else:
    def pick_folder(title: str = "Select folder to monitor") -> Optional[str]:
        """
        Opens a native Windows folder browser dialog using PowerShell System.Windows.Forms.
        Thread-safe: guarded by a lock so only one dialog can be open at a time.
        Returns the chosen absolute path or None if cancelled.
        """
        if not _dialog_lock.acquire(blocking=False):
            logger.warning("Folder dialog is already open; refusing concurrent dialog.")
            return None

        try:
            # PowerShell STA script creating System.Windows.Forms.FolderBrowserDialog
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
                f"$dialog.Description = '{title}'; "
                "$dialog.ShowNewFolderButton = $true; "
                "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
                "    Write-Output $dialog.SelectedPath "
                "}"
            )

            cmd = ["powershell.exe", "-NoProfile", "-STA", "-Command", ps_script]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=False,
                timeout=120  # generous 2-minute user selection window
            )

            if res.returncode == 0:
                selected = res.stdout.strip()
                if selected:
                    return selected
            return None
        except subprocess.TimeoutExpired:
            logger.warning("Folder dialog timed out.")
            return None
        except Exception as e:
            logger.error(f"Error opening folder picker dialog: {e}")
            return None
        finally:
            _dialog_lock.release()
