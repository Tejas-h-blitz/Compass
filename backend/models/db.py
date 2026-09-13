import sqlite3
import os
from typing import Dict, Any, List, Optional
import time

# Resolve the database path. We use a relative path from the workspace
# and make it absolute to ensure consistency across different execution contexts.
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
DB_PATH = os.path.join(DB_DIR, "compass.db")

def get_db_connection() -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.
    Enables FTS5 check and returns connection.
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # Enable foreign keys just in case we need referential integrity later
    conn.execute("PRAGMA foreign_keys = ON;")
    # Set journal mode to WAL for concurrency (good practice for local desktop apps)
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    """
    Initializes the database schema.
    Creates:
    - files: storing file metadata, size, timestamps, and full text content
    - files_fts: SQLite FTS5 virtual table for high-performance keyword search
    - access_log: records file open frequency and recency for personalization
    - query_log: records router decisions, latency, and result counts for evaluation
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Main files table
    # We use 'filepath' as unique index to lookup files easily.
    # We use REAL (float) for UNIX timestamps to simplify date math and comparisons.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            created_at REAL NOT NULL,
            modified_at REAL NOT NULL,
            indexed_at REAL NOT NULL,
            content TEXT NOT NULL
        );
    """)
    
    # 2. SQLite FTS5 Virtual Table for full-text keyword search.
    # Note: FTS5 is a standard, zero-dependency, and extremely fast search module
    # built directly into SQLite. It is perfect for a local Windows app as it avoids
    # external search engine dependencies like Elasticsearch.
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                filepath,
                filename,
                content,
                tokenize='unicode61'
            );
        """)
    except sqlite3.OperationalError as e:
        # FTS5 should be enabled on modern Python builds on Windows.
        # We raise a clear error if it is not, so the user knows immediately.
        raise RuntimeError(
            "SQLite FTS5 extension is not enabled in this Python installation. "
            "Please verify your Python distribution."
        ) from e

    # 3. Access log table
    # Tracks when a user opens/accesses a file from search results.
    # Used as the primary signal for frequency and recency personalization.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT NOT NULL,
            accessed_at REAL NOT NULL
        );
    """)
    
    # 4. Query log table
    # Tracks router decisions, query latency, and match counts.
    # This is critical for Step 6 (Evaluation) to compute average latency,
    # router routing accuracy, and compute savings.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            strategy TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            result_count INTEGER NOT NULL,
            timestamp REAL NOT NULL
        );
    """)
    
    # 5. Monitored horizons table
    # Stores user-approved directories across C: and D: drives for scoped indexing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitored_paths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            label TEXT,
            added_at REAL NOT NULL,
            last_scanned_at REAL
        );
    """)

    conn.commit()
    conn.close()

def insert_or_update_file(
    filepath: str, 
    filename: str, 
    file_type: str, 
    file_size: int, 
    created_at: float, 
    modified_at: float, 
    content: str
) -> int:
    """
    Inserts a new file index or updates an existing one.
    Also syncs the content with the FTS5 virtual table.
    Returns the file ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    indexed_at = time.time()
    
    try:
        # Check if file already exists in database
        cursor.execute("SELECT id FROM files WHERE filepath = ?", (filepath,))
        row = cursor.fetchone()
        
        if row:
            file_id = row[0]
            # Update files table
            cursor.execute("""
                UPDATE files 
                SET file_size = ?, created_at = ?, modified_at = ?, indexed_at = ?, content = ?
                WHERE id = ?
            """, (file_size, created_at, modified_at, indexed_at, content, file_id))
            
            # Update FTS5 table
            cursor.execute("""
                INSERT OR REPLACE INTO files_fts (rowid, filepath, filename, content)
                VALUES (?, ?, ?, ?)
            """, (file_id, filepath, filename, content))
        else:
            # Insert files table
            cursor.execute("""
                INSERT INTO files (filepath, filename, file_type, file_size, created_at, modified_at, indexed_at, content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (filepath, filename, file_type, file_size, created_at, modified_at, indexed_at, content))
            file_id = cursor.lastrowid
            
            # Insert FTS5 table
            cursor.execute("""
                INSERT INTO files_fts (rowid, filepath, filename, content)
                VALUES (?, ?, ?, ?)
            """, (file_id, filepath, filename, content))
            
        conn.commit()
        return file_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_file(filepath: str):
    """
    Deletes a file from the index.
    Keeps the main files table and FTS5 virtual table in sync.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM files WHERE filepath = ?", (filepath,))
        row = cursor.fetchone()
        if row:
            file_id = row[0]
            cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
            cursor.execute("DELETE FROM files_fts WHERE rowid = ?", (file_id,))
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_file_by_path(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves file metadata from database by absolute filepath.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filepath, filename, file_type, file_size, created_at, modified_at, indexed_at, content
        FROM files WHERE filepath = ?
    """, (filepath,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "filepath": row[1],
            "filename": row[2],
            "file_type": row[3],
            "file_size": row[4],
            "created_at": row[5],
            "modified_at": row[6],
            "indexed_at": row[7],
            "content": row[8]
        }
    return None

def log_query_decision(query: str, strategy: str, latency_ms: float, result_count: int):
    """
    Logs search queries and routing decision metrics.
    Essential for quantitative evaluation of router performance.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO query_log (query, strategy, latency_ms, result_count, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (query, strategy, latency_ms, result_count, time.time()))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error logging query: {e}")
    finally:
        conn.close()

def log_file_access(filepath: str):
    """
    Logs when a file is opened, used to compute recommendation frequency & recency.
    """
    norm_path = os.path.abspath(filepath)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO access_log (filepath, accessed_at)
            VALUES (?, ?)
        """, (norm_path, time.time()))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error logging file access: {e}")
    finally:
        conn.close()

# --- Monitored Horizons (Multi-Directory Management) ---

def add_monitored_path(path: str, label: Optional[str] = None) -> bool:
    """
    Registers a new monitored horizon directory path.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    norm_path = os.path.abspath(path)
    if not label:
        label = os.path.basename(norm_path) or norm_path

    try:
        cursor.execute("""
            INSERT OR IGNORE INTO monitored_paths (path, label, added_at)
            VALUES (?, ?, ?)
        """, (norm_path, label, time.time()))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error adding monitored path {path}: {e}")
        return False
    finally:
        conn.close()

def get_monitored_paths() -> List[Dict[str, Any]]:
    """
    Retrieves all user-monitored horizon directories and their file counts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, path, label, added_at, last_scanned_at
            FROM monitored_paths
            ORDER BY added_at ASC
        """)
        rows = cursor.fetchall()
        horizons = []
        for row in rows:
            p = row[1]
            sep = os.path.sep
            prefix = p if p.endswith(sep) else p + sep
            # Count files indexed under this path
            cursor.execute("SELECT COUNT(*) FROM files WHERE filepath LIKE ? OR filepath = ?", (prefix + "%", p))
            file_count = cursor.fetchone()[0]
            horizons.append({
                "id": row[0],
                "path": row[1],
                "label": row[2],
                "added_at": row[3],
                "last_scanned_at": row[4],
                "file_count": file_count
            })
        return horizons
    finally:
        conn.close()

def remove_monitored_path(path: str, prune_files: bool = True) -> bool:
    """
    Removes a monitored horizon directory and optionally prunes its indexed files.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    norm_path = os.path.abspath(path)
    try:
        cursor.execute("DELETE FROM monitored_paths WHERE path = ?", (norm_path,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if deleted and prune_files:
            prune_files_under_path(norm_path)
        return deleted
    except Exception as e:
        print(f"Error removing monitored path {path}: {e}")
        return False

def update_monitored_path_scanned(path: str):
    """
    Updates the last_scanned_at timestamp for a horizon.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    norm_path = os.path.abspath(path)
    try:
        cursor.execute("""
            UPDATE monitored_paths SET last_scanned_at = ? WHERE path = ?
        """, (time.time(), norm_path))
        conn.commit()
    finally:
        conn.close()

def prune_files_under_path(dir_path: str) -> int:
    """
    Removes all indexed files belonging to a specific directory path.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    norm_path = os.path.abspath(dir_path)
    sep = os.path.sep
    prefix = norm_path if norm_path.endswith(sep) else norm_path + sep

    try:
        cursor.execute("SELECT filepath FROM files WHERE filepath LIKE ? OR filepath = ?", (prefix + "%", norm_path))
        paths = [r[0] for r in cursor.fetchall()]
        for p in paths:
            delete_file(p)
            try:
                from backend.search.semantic_search import delete_file_embeddings
                delete_file_embeddings(p)
            except Exception:
                pass
        return len(paths)
    finally:
        conn.close()

def get_recent_and_frequent_files(limit: int = 8) -> List[Dict[str, Any]]:
    """
    Retrieves candidates for zero-query smart recommendations.
    Combines:
    1. Most frequently/recently accessed files from access_log
    2. Most recently modified files on disk from files table
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Candidate set 1: Files with access history
        cursor.execute("""
            SELECT f.filepath, f.filename, f.file_type, f.file_size, f.modified_at, 
                   COUNT(a.id) as open_count, MAX(a.accessed_at) as last_accessed,
                   substr(f.content, 1, 140) as preview
            FROM files f
            JOIN access_log a ON f.filepath = a.filepath
            GROUP BY f.filepath
            ORDER BY last_accessed DESC, open_count DESC
            LIMIT ?
        """, (limit,))
        access_rows = cursor.fetchall()
        
        seen_paths = set()
        candidates = []
        for r in access_rows:
            seen_paths.add(r[0])
            candidates.append({
                "filepath": r[0],
                "filename": r[1],
                "file_type": r[2],
                "file_size": r[3],
                "modified_at": r[4],
                "open_count": r[5],
                "last_accessed": r[6],
                "preview": r[7] or "",
                "source": "access_history"
            })
            
        # Candidate set 2: Recently modified files on disk to discover active files
        remaining = limit - len(candidates)
        if remaining > 0:
            cursor.execute("""
                SELECT filepath, filename, file_type, file_size, modified_at,
                       0 as open_count, NULL as last_accessed,
                       substr(content, 1, 140) as preview
                FROM files
                ORDER BY modified_at DESC
                LIMIT ?
            """, (limit * 2,))
            mod_rows = cursor.fetchall()
            for r in mod_rows:
                if r[0] not in seen_paths and len(candidates) < limit:
                    seen_paths.add(r[0])
                    candidates.append({
                        "filepath": r[0],
                        "filename": r[1],
                        "file_type": r[2],
                        "file_size": r[3],
                        "modified_at": r[4],
                        "open_count": 0,
                        "last_accessed": None,
                        "preview": r[7] or "",
                        "source": "recently_modified"
                    })
                    
        return candidates
    finally:
        conn.close()

