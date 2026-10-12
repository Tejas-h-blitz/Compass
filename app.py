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
import webview

from backend.paths import setup_file_logging, choose_port
from backend.main import app, set_runtime_port
from backend.models.db import init_db
from backend.security.auth import mint_launch_url

# Configure file logging and stdio redirection early
setup_file_logging()
logger = logging.getLogger("compass.app")

_server_instance: Optional[uvicorn.Server] = None

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

def main():
    import argparse
    import webbrowser

    parser = argparse.ArgumentParser(description="Compass - Agentic Desktop Search")
    parser.add_argument(
        "--browser", "-b",
        action="store_true",
        help="Launch application in default system web browser instead of native pywebview window"
    )
    parser.add_argument(
        "--app", "-a",
        action="store_true",
        help="Launch application in standalone browser window (App Mode) to look like a desktop application"
    )
    args = parser.parse_args()

    # Determine runtime port and notify Host/Origin middleware
    runtime_port = choose_port(preferred=8000)
    set_runtime_port(runtime_port)
    logger.info(f"Selected runtime port: {runtime_port}")

    # 1. Ensure the SQLite database and tables exist
    logger.info("Initializing SQLite database...")
    init_db()
    
    # 2. Spin up the FastAPI backend in a background thread.
    logger.info(f"Launching Uvicorn server thread on 127.0.0.1:{runtime_port}...")
    server_thread = threading.Thread(target=start_api_server, args=(runtime_port,), daemon=True)
    server_thread.start()
    
    # Allow uvicorn to bind before opening browser
    time.sleep(1.0)
    
    # Generate fresh one-time launch code and URL
    launch_url = mint_launch_url(runtime_port)
    
    if args.app or args.browser:
        launched_app = False
        if args.app:
            import subprocess
            import platform
            if platform.system() == "Windows":
                try:
                    logger.info("Launching Compass in standalone App Mode via Microsoft Edge...")
                    subprocess.Popen(f'start msedge --app="{launch_url}"', shell=True)
                    launched_app = True
                except Exception as e:
                    logger.warning(f"Failed to launch Edge: {e}")
        
        if not launched_app:
            logger.info("Opening Compass in default system web browser...")
            webbrowser.open(launch_url)
            
        print(f"Compass application running at http://127.0.0.1:{runtime_port}/")
        print("Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping Compass application...")
    else:
        # 3. Start pywebview client desktop window.
        logger.info("Starting pywebview native window loop...")
        webview.create_window(
            title="Compass - Agentic Desktop Search",
            url=launch_url,
            width=1050,
            height=750,
            resizable=True
        )
        
        # Start native UI window loop. Blocks execution until window is closed.
        webview.start()
        print("Compass application exited.")

if __name__ == "__main__":
    main()
