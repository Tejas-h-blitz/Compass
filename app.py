import os
import sys

# Ensure root folder is on python path and change directory early to repo root
_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
os.chdir(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Early mode detection (normal vs demo) before data_dir() is called anywhere
import json
_is_demo_mode_active = "--demo" in sys.argv
if not _is_demo_mode_active:
    try:
        if sys.platform == "win32":
            _home = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")), "Compass")
        else:
            _home = os.path.expanduser("~/.compass")
        _sf = os.path.join(_home, "settings.json")
        if os.path.exists(_sf):
            with open(_sf, "r", encoding="utf-8") as _f:
                _s = json.load(_f)
                if _s.get("mode") == "demo":
                    _is_demo_mode_active = True
    except Exception:
        pass

if _is_demo_mode_active:
    if sys.platform == "win32":
        _demo_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")), "Compass", "demo")
    else:
        _demo_dir = os.path.expanduser("~/.compass/demo")
    os.environ["COMPASS_DATA_DIR"] = _demo_dir

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
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Launch application in isolated Demo Mode using bundled sample corpus"
    )
    args = parser.parse_args()

    # 1. Single Instance Check via named mutex (retry up to 10s to avoid race when restarting)
    global _single_instance
    _single_instance = SingleInstance()
    if not _single_instance.acquire(timeout=10.0):
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

    # 4. If running in Demo Mode, provision sample corpus and setup monitored root
    if _is_demo_mode_active or args.demo:
        try:
            from backend.demo import setup_demo_corpus_if_needed
            setup_demo_corpus_if_needed()
            logger.info("Demo corpus checked and initialized.")
        except Exception as e:
            logger.error(f"Failed to setup demo corpus: {e}")

    # 5. Start incremental live indexing service
    try:
        from backend.indexing.service import global_indexing_service
        global_indexing_service.is_background_mode = bool(args.background)
        global_indexing_service.startup_delay = 45.0 if args.background else 3.0
        global_indexing_service.start()
    except Exception as e:
        logger.error(f"Failed to start indexing service: {e}")

    # 6. Start show-event listener thread
    _single_instance.start_listener(lambda: show_or_open(runtime_port))

    # 7. Spin up Uvicorn in background daemon thread
    global _server_thread
    _server_thread = threading.Thread(target=start_api_server, args=(runtime_port,), daemon=True, name="CompassUvicornServer")
    _server_thread.start()

    # Allow uvicorn to bind before attempting window launch
    time.sleep(0.5)

    # 8. Window launch behavior
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

    # 9. Start global hotkey (Task 5 hook if available)
    try:
        from backend.platform.hotkey import start_hotkey_listener
        start_hotkey_listener(lambda: show_or_open(runtime_port))
    except Exception as e:
        logger.debug(f"Hotkey not initialized yet: {e}")

    # 10. Start system tray on main thread (blocks until Quit clicked or stop_tray called)
    def _switch_mode_action():
        from backend.main import restart_compass_process
        from backend.demo import is_demo_mode
        target_mode = "normal" if is_demo_mode() else "demo"
        restart_compass_process(target_mode)

    run_tray(
        on_open_callback=lambda: show_or_open(runtime_port),
        on_quit_callback=shutdown_application,
        on_switch_mode_callback=_switch_mode_action
    )

if __name__ == "__main__":
    main()
