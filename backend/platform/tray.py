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
        count = get_indexed_files_count()
        return f"Compass: {count} files indexed"

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
        on_quit_callback: Callable[[], None]
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
                logger.info("Tray triggered folder rescan...")
                try:
                    from backend.scanner.scanner import scan_all_monitored
                    stats = scan_all_monitored(force=False)
                    logger.info(f"Rescan completed: {stats}")
                    if _tray_icon:
                        _tray_icon.title = get_tooltip_text()
                except Exception as e:
                    logger.error(f"Error during tray-initiated rescan: {e}")
            threading.Thread(target=_rescan, daemon=True, name="TrayRescanWorker").start()

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

        def _on_quit_clicked(icon, item):
            threading.Thread(target=on_quit_callback, daemon=True, name="TrayQuitWorker").start()

        menu = pystray.Menu(
            pystray.MenuItem("Open Compass", _on_open_clicked, default=True),
            pystray.MenuItem("Rescan folders", _on_rescan_clicked),
            pystray.MenuItem("Start with Windows", _on_toggle_autostart, checked=lambda item: is_autostart_enabled()),
            pystray.MenuItem("Open logs folder", _on_open_logs_clicked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Compass", _on_quit_clicked)
        )

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
