import os
import sys
import sqlite3
import platform
import logging
from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
import urllib.parse

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
from backend.security.auth import (
    SESSION_COOKIE_NAME, consume_launch_code, verify_session
)

EXECUTABLE_BLOCKLIST = {
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe",
    ".js", ".jse", ".wsf", ".wsh", ".hta", ".msi", ".msp", ".scr",
    ".pif", ".lnk", ".url", ".reg", ".jar", ".cpl", ".dll", ".py"
}

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver"}
from backend.paths import get_runtime_port, set_runtime_port

app = FastAPI(title="Compass API", description="Personalized local search agent backend")

@app.middleware("http")
async def host_and_origin_security_middleware(request: Request, call_next):
    # 1. Host header validation (DNS-rebinding protection)
    host_header = request.headers.get("host", "")
    if host_header:
        host_parts = host_header.split(":")
        host_name = host_parts[0].lower()
        host_port = int(host_parts[1]) if len(host_parts) > 1 and host_parts[1].isdigit() else None
    else:
        host_name = ""
        host_port = None

    if not host_name or host_name not in ALLOWED_HOSTS:
        logger.warning(f"Rejected request with disallowed Host header: '{host_header}'")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"Disallowed Host header: {host_header}"}
        )

    runtime_port = get_runtime_port()
    if runtime_port is not None and host_port is not None and host_name != "testserver":
        if host_port != runtime_port:
            logger.warning(f"Rejected request with mismatched Host port: {host_port} != {runtime_port}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": f"Disallowed Host port: {host_port}"}
            )
        
    # 2. Origin header validation for state-changing operations
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin")
        if origin:
            parsed = urllib.parse.urlparse(origin)
            origin_host = (parsed.hostname or "").lower()
            origin_port = parsed.port
            if origin_host not in ALLOWED_HOSTS or origin_host != host_name:
                logger.warning(f"Rejected cross-origin {request.method} from origin: '{origin}' (Host: '{host_header}')")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": f"Cross-origin requests from '{origin}' are forbidden."}
                )
            if runtime_port is not None and origin_port is not None and origin_host != "testserver":
                if origin_port != runtime_port:
                    logger.warning(f"Rejected request with mismatched Origin port: {origin_port} != {runtime_port}")
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": f"Cross-origin port '{origin_port}' is forbidden."}
                    )
                
    return await call_next(request)

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
@app.get("/api/recommendations", dependencies=[Depends(verify_session)])
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

@app.get("/api/horizons", dependencies=[Depends(verify_session)])
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

@app.post("/api/horizons", dependencies=[Depends(verify_session)])
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

@app.delete("/api/horizons", dependencies=[Depends(verify_session)])
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

@app.post("/api/scan-all", dependencies=[Depends(verify_session)])
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
@app.post("/api/scan", dependencies=[Depends(verify_session)])
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

@app.get("/api/search", dependencies=[Depends(verify_session)])
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

@app.post("/api/log-access", dependencies=[Depends(verify_session)])
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

@app.get("/api/stats", dependencies=[Depends(verify_session)])
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
def read_root(request: Request, launch: Optional[str] = None):
    """
    Serves the main frontend index HTML.
    If a valid one-time launch code is provided in query params, sets the session cookie
    and redirects to clean '/' URL.
    """
    if launch:
        session_token = consume_launch_code(launch)
        if session_token:
            response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=session_token,
                httponly=True,
                samesite="strict",
                max_age=None  # Session cookie
            )
            return response
        else:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired launch code. Open Compass from the app window."}
            )

    html_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(html_path):
        with open(html_path, "w") as f:
            f.write("<h1>Loading Compass...</h1>")
    return FileResponse(html_path)
