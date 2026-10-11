import os
import sys
import subprocess

def open_file(path: str) -> None:
    """
    Opens a file using the OS default application association.
    Windows implementation invokes os.startfile.
    """
    if sys.platform == "win32":
        os.startfile(path)
    else:
        raise NotImplementedError(
            f"open_file is not supported on platform '{sys.platform}'. "
            "A macOS/Linux native opener will be provided in a future platform port."
        )

def reveal_in_folder(path: str) -> None:
    """
    Reveals the file in the OS file manager (Windows Explorer) with the file selected.
    Uses an explicit argument list with shell=False.
    """
    if sys.platform == "win32":
        normalized = os.path.normpath(path)
        subprocess.run(["explorer", f"/select,{normalized}"], shell=False, check=False)
    else:
        raise NotImplementedError(
            f"reveal_in_folder is not supported on platform '{sys.platform}'. "
            "A macOS/Linux native file manager reveal will be provided in a future platform port."
        )
