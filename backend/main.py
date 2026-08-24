import os
import sys
import sqlite3
import platform
import logging
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure import paths work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.scanner.scanner import scan_directory
from backend.router.router import route_and_search
from backend.models.db import log_file_access, get_db_connection

app = FastAPI(title="Compass API", description="Personalized local search agent backend")

# 1. API Models
class ScanRequest(BaseModel):
    directory_path: str
    force: bool = False

class AccessRequest(BaseModel):
    filepath: str

# 2. REST Endpoints
@app.post("/api/scan")
def api_scan(req: ScanRequest):
    """
    Scans a directory path. Indexes files and syncs databases.
    """
    normalized_path = os.path.abspath(req.directory_path)
    if not os.path.exists(normalized_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Directory path does not exist: {req.directory_path}"
        )
        
    try:
        stats = scan_directory(normalized_path, force=req.force)
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error scanning directory {req.directory_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/search")
def api_search(query: str, limit: int = 10, personalize: bool = True):
    """
    Executes search query using dynamic router.
    """
    if not query.strip():
        return {
            "query": query,
            "strategy_chosen": "keyword",
            "latency_ms": 0.0,
            "results": []
        }
        
    try:
        res = route_and_search(query, limit=limit, personalize=personalize)
        return res
    except Exception as e:
        logger.error(f"Error searching for query '{query}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

def open_file_locally(filepath: str):
    """
    Launches the file in the default OS handler (association).
    """
    if not os.path.exists(filepath):
        logger.warning(f"File not found on disk for OS open: {filepath}")
        return False
        
    try:
        # Check platform and run native open command.
        # os.startfile is Windows-only and runs association matches.
        if platform.system() == "Windows":
            os.startfile(filepath)
            return True
        else:
            logger.error(f"Unsupported operating system: {platform.system()}. Compass is currently Windows-only.")
            return False
    except Exception as e:
        logger.error(f"Failed to open file locally {filepath}: {e}")
        return False

@app.post("/api/log-access")
def api_log_access(req: AccessRequest):
    """
    Logs user access pattern (frequency/recency signal) and opens the file locally.
    """
    normalized_path = os.path.abspath(req.filepath)
    
    # 1. Log access in SQLite database
    try:
        log_file_access(normalized_path)
    except Exception as e:
        logger.error(f"Failed to write access log for {normalized_path}: {e}")
        
    # 2. Trigger native OS default app opener
    opened = open_file_locally(normalized_path)
    
    return {
        "status": "success",
        "filepath": normalized_path,
        "launched": opened
    }

@app.get("/api/stats")
def api_stats():
    """
    Compiles database statistics for the frontend dashboard.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM files")
        total_files = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM query_log")
        total_queries = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(latency_ms) FROM query_log")
        avg_latency = cursor.fetchone()[0]
        avg_latency = round(avg_latency, 2) if avg_latency is not None else 0.0
        
    except Exception as e:
        logger.error(f"Error fetching DB stats: {e}")
        total_files = 0
        total_queries = 0
        avg_latency = 0.0
    finally:
        conn.close()
        
    return {
        "total_files": total_files,
        "total_queries": total_queries,
        "avg_latency_ms": avg_latency
    }

# 3. Mount Frontend static files
# We map the frontend root files (app.js, index.css) to be served statically under /static
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
os.makedirs(FRONTEND_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def read_root():
    """
    Serves the main frontend index HTML.
    """
    html_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(html_path):
        # Create a basic placeholder file just in case it is read before step 8 is written
        with open(html_path, "w") as f:
            f.write("<h1>Loading Compass...</h1>")
    return FileResponse(html_path)
