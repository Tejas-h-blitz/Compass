import sqlite3
import os
import sys
from typing import Dict, Any, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from backend.models.db import get_db_connection

def clean_fts_query(query: str) -> str:
    """
    Cleanses the query to prevent FTS5 syntax errors.
    Splits the query into alphanumeric terms and joins them with 'AND'.
    FTS5 can throw operational errors if users type special syntax characters
    like quotes, double dashes, asterisks, etc.
    """
    # Replace non-alphanumeric/non-space characters with spaces
    sanitized = "".join(c if c.isalnum() or c.isspace() else " " for c in query)
    # Split into words and filter out empty strings
    words = [w.strip() for w in sanitized.split() if w.strip()]
    
    if not words:
        return ""
    
    # We join with 'AND' to find documents containing all terms by default.
    # We also add a prefix wildcard '*' to each term to support partial matching
    # (e.g. "pyth" matches "python"). This improves lexical recall.
    # In FTS5, terms are formatted as: term1* AND term2*
    query_terms = [f"{w}*" for w in words]
    return " AND ".join(query_terms)

def keyword_search(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Performs lexical search using SQLite FTS5.
    Returns files ranked by normalized BM25 score.
    
    Tradeoff: FTS5 keyword search is extremely fast ('cheap path') compared
    to semantic search, with sub-millisecond execution times. We should use it
    for short queries and filename queries.
    """
    cleaned_query = clean_fts_query(query)
    if not cleaned_query:
        return []
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # FTS5 bm25() returns negative values where lower is better (more relevant).
        # We invert it (-bm25(files_fts)) to get positive scores where higher is better.
        sql = """
            SELECT 
                f.id, 
                f.filepath, 
                f.filename, 
                f.file_type, 
                f.file_size, 
                f.created_at, 
                f.modified_at, 
                -bm25(files_fts) as raw_score,
                f.content
            FROM files_fts
            JOIN files f ON f.id = files_fts.rowid
            WHERE files_fts MATCH ?
            ORDER BY raw_score DESC
            LIMIT ?
        """
        cursor.execute(sql, (cleaned_query, limit))
        rows = cursor.fetchall()
        
        if not rows:
            return []
            
        # Parse rows into dictionary objects
        results = []
        for r in rows:
            results.append({
                "id": r[0],
                "filepath": r[1],
                "filename": r[2],
                "file_type": r[3],
                "file_size": r[4],
                "created_at": r[5],
                "modified_at": r[6],
                "raw_score": r[7],
                "content_preview": r[8][:200] + "..." if len(r[8]) > 200 else r[8],
                "strategy": "keyword"
            })
            
        # Normalize scores to the range [0, 1] relative to the best match.
        # This normalization is required to make keyword scores comparable
        # and mergeable with semantic scores in hybrid routing.
        max_score = results[0]["raw_score"]
        for r in results:
            if max_score > 0:
                r["score"] = round(r["raw_score"] / max_score, 4)
            else:
                r["score"] = 1.0
                
        return results
        
    except sqlite3.OperationalError as e:
        # Handle cases where FTS5 query is still syntactically invalid despite cleaning
        print(f"FTS5 Operational Error: {e} with query: {cleaned_query}")
        return []
    finally:
        conn.close()
