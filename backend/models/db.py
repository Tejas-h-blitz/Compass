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
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO access_log (filepath, accessed_at)
            VALUES (?, ?)
        """, (filepath, time.time()))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error logging file access: {e}")
    finally:
        conn.close()
