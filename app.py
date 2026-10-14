import os
import sys

# Ensure root folder is on python path and change directory early to repo root
_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
os.chdir(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import time
import threading
import logging
from typing import Optional
import uvicorn

from backend.paths import setup_file_logging, choose_port
from backend.main import app, set_runtime_port
from backend.models.db import init_db
from backend.platform.single_instance import SingleInstance
from backend.platform.window import show_or_open, terminate_browser_process
from backend.platform.tray import run_tray, stop_tray

# Configure file logging and stdio redirection early
setup_file_logging()
logger = logging.getLogger("compass.app")

_server_instance: Optional[uvicorn.Server] = None
_server_thread: Optional[threading.Thread] = None
_single_instance: Optional[SingleInstance] = None

def start_api_server(port: int):
    """
    Runs the FastAPI backend server using Uvicorn in a daemon thread.
    Bound explicitly to 127.0.0.1 and the chosen runtime port.
    Uses log_config=None so that logging routes cleanly into root handlers.
    """
    global _server_instance
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        log_config=None
    )
    _server_instance = uvicorn.Server(config)
    _server_instance.run()

def shutdown_application():
    """
    Orchestrates clean graceful shutdown of the Compass background shell.
    Enforces a strict 5-second watchdog timer before hard-exiting with os._exit(0).
    """
    logger.info("Initiating Compass clean shutdown...")
    start_time = time.time()

    def _force_exit_watchdog():
        time.sleep(5.0)
        logger.warning("Shutdown exceeded 5-second deadline; forcing exit via os._exit(0)")
        os._exit(0)

    threading.Thread(target=_force_exit_watchdog, daemon=True, name="ShutdownWatchdog").start()

    # 1. Stop single instance listener and release mutex
    global _single_instance
    if _single_instance:
        try:
            _single_instance.close()
        except Exception as e:
            logger.warning(f"Error closing single instance: {e}")
        _single_instance = None

    # 2. Stop hotkey listener (Task 5)
    try:
        from backend.platform.hotkey import stop_hotkey_listener
        stop_hotkey_listener()
    except Exception:
        pass

    # 3. Terminate dedicated browser process if running
    try:
        terminate_browser_process()
    except Exception as e:
        logger.warning(f"Error terminating browser: {e}")

    # 4. Stop Indexing Service promptly
    try:
        from backend.indexing.service import global_indexing_service
        global_indexing_service.stop(timeout=2.0)
    except Exception as e:
        logger.warning(f"Error stopping indexing service: {e}")

    # 5. Stop Uvicorn server and wait for thread
    global _server_instance, _server_thread
    if _server_instance:
        _server_instance.should_exit = True
    if _server_thread and _server_thread.is_alive():
        _server_thread.join(timeout=2.0)

    # 6. Stop system tray
    try:
        stop_tray()
    except Exception as e:
        logger.warning(f"Error stopping tray: {e}")

    logger.info(f"Compass shutdown completed cleanly in {time.time() - start_time:.2f}s.")

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Compass - Agentic Desktop Search")
    parser.add_argument(
        "--browser", "-b",
        action="store_true",
        help="Launch application in default system web browser"
    )
    parser.add_argument(
        "--app", "-a",
        action="store_true",
        help="Launch application in standalone desktop window (App Mode)"
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="Launch application silently into system tray (no window displayed)"
    )
    args = parser.parse_args()

    # 1. Single Instance Check via named mutex
    global _single_instance
    _single_instance = SingleInstance()
    if not _single_instance.acquire():
        logger.info("Another Compass instance is already running. Signaling show window and exiting.")
        _single_instance.signal_existing_instance()
        _single_instance.close()
        sys.exit(0)

    # 2. Pick runtime port and notify Host/Origin middleware
    runtime_port = choose_port(preferred=8000)
    set_runtime_port(runtime_port)
    logger.info(f"Primary instance acquired. Selected runtime port: {runtime_port}")

    # 3. Ensure SQLite schema exists (lightweight schema check, no scan, no model preload)
    init_db()

    # 4. Start incremental live indexing service
    try:
        from backend.indexing.service import global_indexing_service
        global_indexing_service.is_background_mode = bool(args.background)
        global_indexing_service.startup_delay = 45.0 if args.background else 3.0
        global_indexing_service.start()
    except Exception as e:
        logger.error(f"Failed to start indexing service: {e}")

    # 5. Start show-event listener thread
    _single_instance.start_listener(lambda: show_or_open(runtime_port))

    # 6. Spin up Uvicorn in background daemon thread
    global _server_thread
    _server_thread = threading.Thread(target=start_api_server, args=(runtime_port,), daemon=True, name="CompassUvicornServer")
    _server_thread.start()

    # Allow uvicorn to bind before attempting window launch
    time.sleep(0.5)

    # 6. Window launch behavior
    # Startup modes:
    # --background: tray only, no window
    # --app or no flag: tray + open window
    # --browser: open in system browser
    if not args.background:
        if args.browser:
            import webbrowser
            from backend.security.auth import mint_launch_url
            webbrowser.open(mint_launch_url(runtime_port))
        else:
            show_or_open(runtime_port)

    # 7. Start global hotkey (Task 5 hook if available)
    try:
        from backend.platform.hotkey import start_hotkey_listener
        start_hotkey_listener(lambda: show_or_open(runtime_port))
    except Exception as e:
        logger.debug(f"Hotkey not initialized yet: {e}")

    # 8. Start system tray on main thread (blocks until Quit clicked or stop_tray called)
    run_tray(
        on_open_callback=lambda: show_or_open(runtime_port),
        on_quit_callback=shutdown_application
    )

if __name__ == "__main__":
    main()
