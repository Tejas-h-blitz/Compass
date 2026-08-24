import os
import sys
import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# Setup simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Ensure the parent directory of backend is on the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from backend.models.db import insert_or_update_file, get_file_by_path, delete_file

# Supported file extensions for text extraction
# Keeping scope strictly constrained to txt, docx, pdf, and plain text/code files
TEXT_EXTENSIONS = {
    ".txt", ".py", ".md", ".json", ".js", ".html", ".css", ".java", ".c", ".cpp", ".h", ".csv", ".xml", ".ini", ".yaml", ".yml"
}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}

def extract_text(filepath: str, extension: str) -> str:
    """
    Extracts text content based on file extension.
    Gracefully handles file encoding and formats.
    """
    if extension in TEXT_EXTENSIONS:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback to reading with errors ignored (common for system/config text files)
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
                
    elif extension in PDF_EXTENSIONS:
        # Import pypdf locally so it is only loaded if needed
        import pypdf
        text = []
        with open(filepath, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text.append(t)
        return "\n".join(text)
        
    elif extension in DOCX_EXTENSIONS:
        import docx
        doc = docx.Document(filepath)
        text = [p.text for p in doc.paragraphs]
        return "\n".join(text)
        
    return ""

def scan_file(filepath: str, force: bool = False) -> bool:
    """
    Scans a single file. Reads metadata and text content, updates SQLite,
    and updates ChromaDB embeddings (if the semantic search package is ready).
    Returns True if the file was updated/indexed, False if skipped (unchanged).
    """
    path_obj = Path(filepath)
    if not path_obj.exists():
        return False
        
    # Get basic OS file metadata
    stat = path_obj.stat()
    file_size = stat.st_size
    created_at = stat.st_ctime
    modified_at = stat.st_mtime
    filename = path_obj.name
    file_type = path_obj.suffix.lower()
    
    # Check if the file type is in our supported list
    all_supported = TEXT_EXTENSIONS.union(PDF_EXTENSIONS).union(DOCX_EXTENSIONS)
    if file_type not in all_supported:
        return False
        
    # Skip files larger than 10MB to avoid high CPU/memory consumption and potential crashes
    if file_size > 10 * 1024 * 1024:
        logger.warning(f"Skipping file {filename}: size exceeds 10MB limit ({file_size} bytes)")
        return False
        
    # Check if the file is already indexed and whether it has been modified.
    # This is a critical optimization preventing redundant heavy text extraction
    # and embedding computations for thousands of unchanged files.
    existing_file = get_file_by_path(filepath)
    if existing_file and not force:
        # Compare modified time in db vs current OS modified time
        # We allow a tiny precision delta (0.01s) due to float precision differences
        if abs(existing_file["modified_at"] - modified_at) < 0.01:
            return False
            
    # Extract text content
    try:
        content = extract_text(filepath, file_type)
    except Exception as e:
        # Non-negotiable standard: unreadable or corrupted files must not crash the indexer.
        # We log and skip.
        logger.error(f"Failed to extract text from {filepath}: {e}")
        return False
        
    # Save/update SQLite index
    try:
        insert_or_update_file(
            filepath=filepath,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            created_at=created_at,
            modified_at=modified_at,
            content=content
        )
        logger.info(f"Indexed SQLite for: {filename}")
    except Exception as e:
        logger.error(f"Failed to write metadata/content to SQLite for {filepath}: {e}")
        return False
        
    # Update semantic search embeddings in ChromaDB if semantic_search module is available
    try:
        from backend.search.semantic_search import upsert_file_embeddings
        upsert_file_embeddings(filepath, filename, content)
        logger.info(f"Indexed embeddings in ChromaDB for: {filename}")
    except ImportError:
        # This will happen in Step 1 before Step 3 is completed.
        # We catch the ImportError to keep Step 1 testable standalone.
        logger.debug(f"ChromaDB indexing skipped for {filename} (semantic search module not ready yet)")
    except Exception as e:
        logger.error(f"Failed to write embeddings to ChromaDB for {filepath}: {e}")
        
    return True

def scan_directory(directory_path: str, force: bool = False) -> Dict[str, int]:
    """
    Recursively scans all files in a directory.
    Prunes files from the SQLite index that no longer exist in the directory.
    """
    target_dir = Path(directory_path)
    if not target_dir.exists() or not target_dir.is_dir():
        logger.error(f"Invalid directory path: {directory_path}")
        return {"scanned": 0, "updated": 0, "pruned": 0}
        
    logger.info(f"Starting scan of directory: {directory_path}")
    start_time = time.time()
    
    scanned_count = 0
    updated_count = 0
    found_filepaths = set()
    
    # 1. Walk directory and index/update files
    for root, dirs, files in os.walk(directory_path):
        # In-place modify dirs to avoid scanning hidden or heavy developer folders
        dirs[:] = [d for d in dirs if d not in {
            '.git', 'node_modules', '.venv', 'venv', '__pycache__', 
            'env', '.next', 'dist', 'build', '.idea', '.vscode'
        }]
        for file in files:
            filepath = os.path.join(root, file)
            normalized_path = os.path.abspath(filepath)
            found_filepaths.add(normalized_path)
            scanned_count += 1
            
            try:
                updated = scan_file(normalized_path, force=force)
                if updated:
                    updated_count += 1
            except Exception as e:
                logger.error(f"Error scanning file {normalized_path}: {e}")
                
    # 2. Prune files that were deleted from disk
    # Query database for all files starting with directory_path
    from backend.models.db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    pruned_count = 0
    abs_dir_prefix = os.path.abspath(directory_path)
    
    # Select all indexed files starting with the directory path to check for removal
    # To prevent partial matches (e.g. C:\temp matches C:\temp_new), we append a separator
    sep = os.path.sep
    prefix_query = abs_dir_prefix if abs_dir_prefix.endswith(sep) else abs_dir_prefix + sep
    
    cursor.execute("SELECT filepath FROM files WHERE filepath LIKE ?", (prefix_query + "%",))
    db_paths = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    for db_path in db_paths:
        if db_path not in found_filepaths:
            # File no longer exists, delete it
            try:
                delete_file(db_path)
                # Also prune ChromaDB embeddings if available
                try:
                    from backend.search.semantic_search import delete_file_embeddings
                    delete_file_embeddings(db_path)
                except ImportError:
                    pass
                pruned_count += 1
                logger.info(f"Pruned deleted file from index: {db_path}")
            except Exception as e:
                logger.error(f"Failed to prune file {db_path}: {e}")
                
    elapsed = time.time() - start_time
    logger.info(f"Scan complete in {elapsed:.2f}s. Scanned: {scanned_count}, Updated: {updated_count}, Pruned: {pruned_count}")
    
    return {
        "scanned": scanned_count,
        "updated": updated_count,
        "pruned": pruned_count
    }
