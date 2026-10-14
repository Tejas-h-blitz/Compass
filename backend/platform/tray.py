import os
import sys
import logging
import threading
import subprocess
from typing import Optional, Callable
from PIL import Image, ImageDraw
import pystray

logger = logging.getLogger(__name__)

_tray_icon: Optional[pystray.Icon] = None

if sys.platform != "win32":
    def run_tray(*args, **kwargs):
        raise NotImplementedError("System tray is currently only implemented for Windows.")

    def stop_tray():
        pass

    def show_notification(title: str, message: str):
        pass

else:
    from backend.paths import logs_dir
    try:
        from backend.platform.autostart import (
            is_enabled as is_autostart_enabled,
            enable as enable_autostart,
            disable as disable_autostart
        )
    except ImportError:
        def is_autostart_enabled():
            return False
        def enable_autostart():
            return False
        def disable_autostart():
            return False

    def create_compass_icon() -> Image.Image:
        """
        Draws the Compass system tray icon programmatically with Pillow.
        Renders a transparent 64x64 RGBA canvas with an accent-blue ring (#3b82f6)
        and a two-tone directional compass needle.
        """
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Outer compass ring in accent blue (#3b82f6)
        draw.ellipse([4, 4, 59, 59], outline=(59, 130, 246, 255), width=3)

        # Compass cardinal tick marks
        draw.line([(32, 7), (32, 11)], fill=(59, 130, 246, 255), width=2)
        draw.line([(32, 53), (32, 57)], fill=(148, 163, 184, 255), width=2)
        draw.line([(7, 32), (11, 32)], fill=(148, 163, 184, 255), width=2)
        draw.line([(53, 32), (57, 32)], fill=(148, 163, 184, 255), width=2)

        # North-pointing needle (Blue tones)
        draw.polygon([(32, 12), (26, 32), (32, 28)], fill=(59, 130, 246, 255))
        draw.polygon([(32, 12), (38, 32), (32, 28)], fill=(96, 165, 250, 255))

        # South-pointing needle (Silver / Slate tones)
        draw.polygon([(32, 52), (26, 32), (32, 36)], fill=(148, 163, 184, 255))
        draw.polygon([(32, 52), (38, 32), (32, 36)], fill=(203, 213, 225, 255))

        # Center pivot
        draw.ellipse([29, 29, 35, 35], fill=(255, 255, 255, 255))
        draw.ellipse([30, 30, 34, 34], fill=(15, 23, 42, 255))

        return img

    def get_indexed_files_count() -> int:
        """Reads indexed file count from SQLite in a read-only query; tolerates errors."""
        try:
            from backend.models.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM files")
            row = cursor.fetchone()
            conn.close()
            return int(row[0]) if row else 0
        except Exception as e:
            logger.debug(f"Could not read indexed files count for tooltip: {e}")
            return 0

    def get_tooltip_text() -> str:
        try:
            from backend.indexing.status import global_indexing_status
            status = global_indexing_status
            if status.state in ("indexing", "reconciling") and status.total_expected > 0:
                return f"Compass: indexing {status.processed} of {status.total_expected}"
            count = get_indexed_files_count()
            return f"Compass: {count} files indexed"
        except Exception as e:
            logger.debug(f"Could not format tooltip text: {e}")
            count = get_indexed_files_count()
            return f"Compass: {count} files indexed"

    def is_indexing_paused() -> bool:
        try:
            from backend.indexing.service import global_indexing_service
            return global_indexing_service.is_paused()
        except Exception:
            return False

    def show_notification(title: str, message: str) -> None:
        """Displays a Windows tray notification bubble if tray is active."""
        global _tray_icon
        if _tray_icon:
            try:
                _tray_icon.notify(message, title)
            except Exception as e:
                logger.warning(f"Could not display tray notification: {e}")

    def run_tray(
        on_open_callback: Callable[[], None],
        on_quit_callback: Callable[[], None],
        on_switch_mode_callback: Optional[Callable[[], None]] = None
    ) -> None:
        """
        Creates and runs the system tray icon on the current (main) thread.
        Blocks until icon.stop() is called.
        All menu click handlers spawn daemon threads to return quickly.
        """
        global _tray_icon

        def _on_open_clicked(icon, item):
            threading.Thread(target=on_open_callback, daemon=True, name="TrayOpenWorker").start()

        def _on_rescan_clicked(icon, item):
            def _rescan():
                logger.info("Tray triggered folder rescan via IndexingService...")
                try:
                    from backend.indexing.service import global_indexing_service
                    global_indexing_service.rescan(force=False)
                    if _tray_icon:
                        _tray_icon.title = get_tooltip_text()
                except Exception as e:
                    logger.error(f"Error during tray-initiated rescan: {e}")
            threading.Thread(target=_rescan, daemon=True, name="TrayRescanWorker").start()

        def _on_toggle_pause(icon, item):
            def _toggle():
                try:
                    from backend.indexing.service import global_indexing_service
                    if global_indexing_service.is_paused():
                        global_indexing_service.resume()
                        logger.info("Tray: Resumed indexing.")
                    else:
                        global_indexing_service.pause()
                        logger.info("Tray: Paused indexing.")
                    if _tray_icon:
                        _tray_icon.title = get_tooltip_text()
                except Exception as e:
                    logger.error(f"Error toggling indexing pause from tray: {e}")
            threading.Thread(target=_toggle, daemon=True, name="TrayTogglePauseWorker").start()

        def _on_toggle_autostart(icon, item):
            current = is_autostart_enabled()
            if current:
                disable_autostart()
            else:
                enable_autostart()

        def _on_open_logs_clicked(icon, item):
            def _open_logs():
                log_folder = logs_dir()
                try:
                    os.startfile(log_folder)
                except Exception:
                    subprocess.Popen(["explorer", log_folder])
            threading.Thread(target=_open_logs, daemon=True, name="TrayOpenLogsWorker").start()

        def _on_switch_mode_clicked(icon, item):
            if on_switch_mode_callback:
                threading.Thread(target=on_switch_mode_callback, daemon=True, name="TraySwitchModeWorker").start()

        def _on_quit_clicked(icon, item):
            threading.Thread(target=on_quit_callback, daemon=True, name="TrayQuitWorker").start()

        def _pause_resume_title(item) -> str:
            return "Resume indexing" if is_indexing_paused() else "Pause indexing"

        def _mode_title(item) -> str:
            from backend.paths import data_dir, app_home
            curr = os.path.normcase(os.path.realpath(data_dir()))
            demo = os.path.normcase(os.path.realpath(os.path.join(app_home(), "demo")))
            return "Switch to normal mode" if curr == demo else "Switch to demo mode"

        menu_items = [
            pystray.MenuItem("Open Compass", _on_open_clicked, default=True),
            pystray.MenuItem("Rescan folders", _on_rescan_clicked),
            pystray.MenuItem(_pause_resume_title, _on_toggle_pause),
            pystray.MenuItem(_mode_title, _on_switch_mode_clicked),
            pystray.MenuItem("Start with Windows", _on_toggle_autostart, checked=lambda item: is_autostart_enabled()),
            pystray.MenuItem("Open logs folder", _on_open_logs_clicked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Compass", _on_quit_clicked)
        ]

        menu = pystray.Menu(*menu_items)

        icon_image = create_compass_icon()
        tooltip = get_tooltip_text()

        _tray_icon = pystray.Icon("Compass", icon_image, tooltip, menu)
        logger.info("Starting Compass system tray icon...")
        _tray_icon.run()
        logger.info("System tray icon stopped.")

    def stop_tray() -> None:
        """Stops the system tray loop."""
        global _tray_icon
        if _tray_icon:
            try:
                _tray_icon.stop()
            except Exception as e:
                logger.warning(f"Error stopping tray icon: {e}")
            _tray_icon = None
