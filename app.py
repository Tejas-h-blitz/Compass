import os
import sys
import time
import threading
import uvicorn
import webview

# Ensure the root folder is on the python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from backend.main import app
from backend.models.db import init_db
from backend.security.auth import generate_launch_code

def start_api_server():
    """
    Runs the FastAPI backend server using Uvicorn in a daemon thread.
    Bound explicitly to 127.0.0.1.
    """
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

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

    # 1. Ensure the SQLite database and tables exist
    print("Initializing SQLite database...")
    init_db()
    
    # 2. Spin up the FastAPI backend in a background thread.
    # Daemon thread ensures that closing the main UI window shuts down the server.
    print("Launching Uvicorn server thread...")
    server_thread = threading.Thread(target=start_api_server, daemon=True)
    server_thread.start()
    
    # Allow uvicorn to bind to port 8000 before opening the browser window
    time.sleep(1.5)
    
    # Generate one-time single-use launch code for session initialization
    launch_code = generate_launch_code()
    launch_url = f"http://127.0.0.1:8000/?launch={launch_code}"
    
    if args.app or args.browser:
        launched_app = False
        if args.app:
            import subprocess
            import platform
            if platform.system() == "Windows":
                try:
                    print("Launching Compass in standalone App Mode via Microsoft Edge...")
                    subprocess.Popen(f'start msedge --app="{launch_url}"', shell=True)
                    launched_app = True
                except Exception:
                    pass
        
        if not launched_app:
            print("Opening Compass in default system web browser...")
            webbrowser.open(launch_url)
            
        print("Compass application running at http://127.0.0.1:8000/")
        print("Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping Compass application...")
    else:
        # 3. Start pywebview client desktop window.
        print("Starting pywebview native window loop...")
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
