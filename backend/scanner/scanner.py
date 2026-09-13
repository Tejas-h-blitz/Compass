import os
import sys
import re
import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# Setup simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Ensure the parent directory of backend is on the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from backend.models.db import (
    insert_or_update_file, get_file_by_path, delete_file, 
    get_monitored_paths, update_monitored_path_scanned
)

# --- Security-by-Design Guardrails ---
# Directories that must NEVER be scanned under any circumstances (defense-in-depth)
SECURITY_BLACKLIST_DIRS = {
    '.ssh', '.aws', '.git', 'appdata', 'windows', 'program files',
    'program files (x86)', '$recycle.bin', 'system volume information',
    'node_modules', '.venv', 'venv', '__pycache__', 'env', '.next',
    'dist', 'build', '.idea', '.vscode', '.config', 'cookies',
    'credentials', 'recovery'
}

# File extensions that contain keys, certificates, or sensitive credentials
SECURITY_BLACKLIST_EXTS = {
    '.env', '.pem', '.key', '.kdbx', '.pfx', '.p12', '.credentials',
    '.crt', '.csr', '.sqlite3-shm', '.wallet', '.secret'
}

# Specific sensitive filenames
SECURITY_BLACKLIST_FILENAMES = {
    'id_rsa', 'id_ed25519', 'id_dsa', 'id_ecdsa', '.git-credentials',
    '.bash_history', 'wp-config.php', 'passwd', 'shadow', 'known_hosts',
    'authorized_keys'
}

# Regex patterns for sanitizing secrets and API keys from text before storage/embeddings
API_KEY_PATTERNS = [
    (re.compile(r'-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----'), '[REDACTED_PRIVATE_KEY]'),
    (re.compile(r'\b(sk-[a-zA-Z0-9_\-]{20,})\b'), '[REDACTED_API_KEY]'),
    (re.compile(r'\b(AIzaSy[a-zA-Z0-9_\-]{33})\b'), '[REDACTED_API_KEY]'),
    (re.compile(r'\b(ghp_[a-zA-Z0-9]{36})\b'), '[REDACTED_GITHUB_TOKEN]'),
    (re.compile(r'\b(AKIA[0-9A-Z]{16})\b'), '[REDACTED_AWS_KEY]'),
    (re.compile(r'(?i)\b(password|secret|token|api_key|apikey|bearer)\s*[:=]\s*["\']([^"\']{6,})["\']'), r'\1: "[REDACTED_SECRET]"')
]

def is_path_security_blacklisted(filepath: str) -> bool:
    """
    Evaluates whether a file path or any of its parent directories match
    the security blacklists. Prevents unauthorized indexing of private keys,
    passwords, environment files, or system directories.
    """
    path_obj = Path(filepath)
    filename = path_obj.name.lower()
    
    if filename in SECURITY_BLACKLIST_FILENAMES:
        return True
    if filename.startswith("~$") or filename.startswith(".~"):
        return True
    if filename.startswith(".env") or filename.endswith(".env"):
        return True
    if path_obj.suffix.lower() in SECURITY_BLACKLIST_EXTS:
        return True
        
    for part in path_obj.parts:
        if part.lower() in SECURITY_BLACKLIST_DIRS:
            return True
            
    return False

def sanitize_content(content: str) -> str:
    """
    Scans extracted document text for API keys, private keys, and secrets,
    redacting them before they can be stored in SQLite or embedded in ChromaDB.
    """
    if not content:
        return ""
    sanitized = content
    for pattern, replacement in API_KEY_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized

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
        
    filename = path_obj.name
    file_type = path_obj.suffix.lower()

    # Security check: verify against sensitive extensions, keys, and system directories
    if is_path_security_blacklisted(filepath):
        logger.info(f"Skipping security-blacklisted file: {filename}")
        return False

    # Check if the file type is in our supported list
    all_supported = TEXT_EXTENSIONS.union(PDF_EXTENSIONS).union(DOCX_EXTENSIONS)
    if file_type not in all_supported:
        return False

    try:
        # Get basic OS file metadata
        stat = path_obj.stat()
        file_size = stat.st_size
        created_at = stat.st_ctime
        modified_at = stat.st_mtime
    except (PermissionError, OSError) as e:
        logger.warning(f"Skipping inaccessible file {filepath}: {e}")
        return False
        
    # Skip files larger than 10MB to avoid high CPU/memory consumption and potential crashes
    if file_size > 10 * 1024 * 1024:
        logger.warning(f"Skipping file {filename}: size exceeds 10MB limit ({file_size} bytes)")
        return False
        
    # Check if the file is already indexed and whether it has been modified.
    existing_file = get_file_by_path(filepath)
    if existing_file and not force:
        if abs(existing_file["modified_at"] - modified_at) < 0.01:
            return False
            
    # Extract text content
    try:
        content = extract_text(filepath, file_type)
    except Exception as e:
        logger.error(f"Failed to extract text from {filepath}: {e}")
        return False

    # Sanitize content: scrub API keys, tokens, and private keys before storage/embeddings
    content = sanitize_content(content)
        
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
    
    # 1. Walk directory safely without following symlinks/junction loops
    for root, dirs, files in os.walk(directory_path, followlinks=False):
        # In-place modify dirs to avoid scanning hidden or heavy developer/system folders
        dirs[:] = [
            d for d in dirs 
            if d.lower() not in SECURITY_BLACKLIST_DIRS 
            and not (d.startswith(".") and d not in {".", ".."})
        ]
        for file in files:
            filepath = os.path.join(root, file)
            normalized_path = os.path.abspath(filepath)
            
            # Security guardrail
            if is_path_security_blacklisted(normalized_path):
                continue

            found_filepaths.add(normalized_path)
            scanned_count += 1
            
            try:
                updated = scan_file(normalized_path, force=force)
                if updated:
                    updated_count += 1
            except Exception as e:
                logger.error(f"Error scanning file {normalized_path}: {e}")
                
    # 2. Prune files that were deleted from disk
    from backend.models.db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    pruned_count = 0
    abs_dir_prefix = os.path.abspath(directory_path)
    sep = os.path.sep
    prefix_query = abs_dir_prefix if abs_dir_prefix.endswith(sep) else abs_dir_prefix + sep
    
    cursor.execute("SELECT filepath FROM files WHERE filepath LIKE ?", (prefix_query + "%",))
    db_paths = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    for db_path in db_paths:
        if db_path not in found_filepaths:
            try:
                delete_file(db_path)
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

def scan_all_monitored(force: bool = False) -> Dict[str, Any]:
    """
    Iterates over all user-monitored horizon folders and updates their indices.
    """
    horizons = get_monitored_paths()
    total_scanned = 0
    total_updated = 0
    total_pruned = 0
    
    for h in horizons:
        path = h["path"]
        if os.path.exists(path):
            stats = scan_directory(path, force=force)
            total_scanned += stats["scanned"]
            total_updated += stats["updated"]
            total_pruned += stats["pruned"]
            update_monitored_path_scanned(path)
            
    return {
        "horizons_scanned": len(horizons),
        "scanned": total_scanned,
        "updated": total_updated,
        "pruned": total_pruned
    }

