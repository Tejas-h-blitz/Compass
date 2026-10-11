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

from typing import Optional, List
# Ensure import paths work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.scanner.scanner import scan_directory, scan_all_monitored, is_path_security_blacklisted
from backend.router.router import route_and_search
from backend.models.db import (
    log_file_access, get_db_connection, add_monitored_path, 
    get_monitored_paths, remove_monitored_path
)
from backend.search.recommend import get_smart_recommendations
from backend.platform.launcher import open_file, reveal_in_folder

EXECUTABLE_BLOCKLIST = {
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe",
    ".js", ".jse", ".wsf", ".wsh", ".hta", ".msi", ".msp", ".scr",
    ".pif", ".lnk", ".url", ".reg", ".jar", ".cpl", ".dll", ".py"
}

app = FastAPI(title="Compass API", description="Personalized local search agent backend")

# 1. API Models
class ScanRequest(BaseModel):
    directory_path: str
    force: bool = False

class AccessRequest(BaseModel):
    filepath: str

class HorizonRequest(BaseModel):
    path: str
    label: Optional[str] = None

# 2. REST Endpoints
@app.get("/api/recommendations")
def api_recommendations(limit: int = 6):
    """
    Returns smart zero-query file recommendations based on frequency-recency decay
    and recently modified documents.
    """
    try:
        recs = get_smart_recommendations(limit=limit)
        return {
            "status": "success",
            "recommendations": recs
        }
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/horizons")
def api_get_horizons():
    """
    Lists all registered monitored horizons and their file counts.
    """
    try:
        return {
            "status": "success",
            "horizons": get_monitored_paths()
        }
    except Exception as e:
        logger.error(f"Error fetching horizons: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/api/horizons")
def api_add_horizon(req: HorizonRequest):
    """
    Adds a folder to monitored horizons and triggers an immediate safe scan.
    """
    norm_path = os.path.abspath(req.path)
    if not os.path.exists(norm_path) or not os.path.isdir(norm_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Directory does not exist: {req.path}"
        )
    
    if is_path_security_blacklisted(norm_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Security restriction: Cannot monitor protected system, credential, or secret directories."
        )
        
    add_monitored_path(norm_path, req.label)
    stats = scan_directory(norm_path)
    return {
        "status": "success",
        "path": norm_path,
        "stats": stats,
        "horizons": get_monitored_paths()
    }

@app.delete("/api/horizons")
def api_remove_horizon(path: str):
    """
    Removes a folder from monitored horizons and cleans up its index.
    """
    norm_path = os.path.abspath(path)
    success = remove_monitored_path(norm_path)
    return {
        "status": "success" if success else "not_found",
        "horizons": get_monitored_paths()
    }

@app.post("/api/scan-all")
def api_scan_all(force: bool = False):
    """
    Scans all registered horizons.
    """
    try:
        stats = scan_all_monitored(force=force)
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error scanning all horizons: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
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

@app.post("/api/log-access")
def api_log_access(req: AccessRequest):
    """
    Validates file launch request against indexed files, disk existence, monitored paths,
    and executable blocklists. On validation success, logs access and launches or reveals the file.
    """
    # 1. Normalize the path (resolve symlinks, relative traversal, and casing)
    normalized_path = os.path.normcase(os.path.realpath(req.filepath))
    
    # 2. Verify file exists on disk
    if not os.path.exists(normalized_path) or not os.path.isfile(normalized_path):
        logger.warning(f"Rejected access: file does not exist on disk: {req.filepath}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File does not exist on disk."
        )
        
    # Verify file is stored in the files index
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filepath FROM files")
    rows = cursor.fetchall()
    conn.close()
    
    matched_db_filepath = None
    for (db_p,) in rows:
        if os.path.normcase(os.path.realpath(db_p)) == normalized_path:
            matched_db_filepath = db_p
            break
            
    if not matched_db_filepath:
        logger.warning(f"Rejected access: file is not indexed in Compass: {req.filepath}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File is not indexed in Compass."
        )
        
    # 3. Verify file is inside a registered monitored path
    monitored = get_monitored_paths()
    is_monitored = False
    for m in monitored:
        m_path = m.get("path", "")
        if m_path:
            norm_m = os.path.normcase(os.path.realpath(m_path))
            try:
                if os.path.commonpath([normalized_path, norm_m]) == norm_m:
                    is_monitored = True
                    break
            except ValueError:
                # Paths on different drives
                continue
                
    if not is_monitored:
        logger.warning(f"Rejected access: file is outside monitored paths: {req.filepath}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="File is outside registered monitored paths."
        )
        
    # 4. Check executable / script blocklist
    _, ext = os.path.splitext(normalized_path)
    is_blocked = ext.lower() in EXECUTABLE_BLOCKLIST
    
    # 5. Log access only after validation succeeds
    try:
        log_file_access(matched_db_filepath)
    except Exception as e:
        logger.error(f"Failed to write access log for {matched_db_filepath}: {e}")
        
    # 6. Execute launch or reveal
    if is_blocked:
        reveal_in_folder(matched_db_filepath)
        return {
            "status": "revealed",
            "action": "revealed",
            "filepath": matched_db_filepath,
            "launched": False,
            "revealed": True,
            "message": "File revealed in folder because executable/script types cannot be directly launched."
        }
    else:
        open_file(matched_db_filepath)
        return {
            "status": "success",
            "action": "launched",
            "filepath": matched_db_filepath,
            "launched": True,
            "revealed": False,
            "message": "File launched successfully."
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
