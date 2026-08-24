import os
import sys
import time
import sqlite3
from pathlib import Path

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.models.db import init_db, get_db_connection, get_file_by_path
from backend.scanner.scanner import scan_directory

TEST_CORPUS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "test_corpus"))

def main():
    print("=== Testing Step 1: SQLite Schema & Scanner ===")
    
    # 1. Initialize Database
    print("\n[1/5] Initializing SQLite database...")
    init_db()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Initialized tables in SQLite: {tables}")
    assert "files" in tables, "Table 'files' is missing!"
    assert "files_fts" in tables, "Table 'files_fts' is missing!"
    assert "access_log" in tables, "Table 'access_log' is missing!"
    assert "query_log" in tables, "Table 'query_log' is missing!"
    conn.close()
    
    # 2. Run Scanner on Test Corpus (First Scan)
    print("\n[2/5] Running scanner on test corpus (first run)...")
    stats = scan_directory(TEST_CORPUS_DIR)
    print(f"Scan statistics: {stats}")
    assert stats["scanned"] == 3, f"Expected 3 files, got {stats['scanned']}"
    assert stats["updated"] == 3, f"Expected all 3 files to be updated, got {stats['updated']}"
    assert stats["pruned"] == 0, f"Expected 0 pruned files, got {stats['pruned']}"
    
    # Verify content in database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filepath, filename, file_type, file_size, length(content) FROM files")
    files = cursor.fetchall()
    print("\nIndexed files in SQLite:")
    for f in files:
        print(f" - Path: {f[0]}\n   Name: {f[1]} | Type: {f[2]} | Size: {f[3]} bytes | Text extracted: {f[4]} chars")
    conn.close()
    
    # Check text extraction correctness
    doc1 = get_file_by_path(os.path.join(TEST_CORPUS_DIR, "doc1_python_intro.txt"))
    assert doc1 is not None, "doc1 not found in database!"
    assert "Python" in doc1["content"], "Failed to extract text from TXT!"
    
    doc2 = get_file_by_path(os.path.join(TEST_CORPUS_DIR, "doc2_search_strategies.docx"))
    assert doc2 is not None, "doc2 not found in database!"
    assert "semantic search" in doc2["content"].lower(), "Failed to extract text from DOCX!"
    
    doc3 = get_file_by_path(os.path.join(TEST_CORPUS_DIR, "doc3_dummy_test.pdf"))
    assert doc3 is not None, "doc3 not found in database!"
    # Note: dummy.pdf has some text like "Dummy PDF file"
    assert len(doc3["content"].strip()) > 0, "PDF content extraction is empty!"
    print("Text extraction successfully verified for TXT, DOCX, and PDF!")
    
    # 3. Run Scanner Again (No Modifications)
    print("\n[3/5] Running scanner again without file changes...")
    stats2 = scan_directory(TEST_CORPUS_DIR)
    print(f"Scan statistics (second run): {stats2}")
    assert stats2["scanned"] == 3, f"Expected 3 files, got {stats2['scanned']}"
    assert stats2["updated"] == 0, f"Expected 0 updated files (cached), got {stats2['updated']}"
    print("Modified-time check caching works successfully!")
    
    # 4. Modify a file and run scan
    print("\n[4/5] Modifying a file and running scanner...")
    txt_path = os.path.join(TEST_CORPUS_DIR, "doc1_python_intro.txt")
    # Touch the file: read and append a newline to change modified time
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    time.sleep(1) # Ensure modified time is different by at least 1s
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content + "\n# Modified for test")
        
    stats3 = scan_directory(TEST_CORPUS_DIR)
    print(f"Scan statistics (third run): {stats3}")
    assert stats3["updated"] == 1, f"Expected 1 updated file, got {stats3['updated']}"
    
    # Restore file
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content)
    scan_directory(TEST_CORPUS_DIR)
    print("File modification detection verified!")
    
    # 5. Create a temporary file, scan it, delete it, and verify pruning
    print("\n[5/5] Testing file deletion pruning...")
    temp_path = os.path.join(TEST_CORPUS_DIR, "temp_delete_test.txt")
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write("Temp file to test pruning")
        
    stats_temp = scan_directory(TEST_CORPUS_DIR)
    assert stats_temp["updated"] == 1, "Temp file was not indexed!"
    
    # Now delete it
    os.remove(temp_path)
    stats_pruned = scan_directory(TEST_CORPUS_DIR)
    print(f"Scan statistics after deletion: {stats_pruned}")
    assert stats_pruned["pruned"] == 1, f"Expected 1 pruned file, got {stats_pruned['pruned']}"
    
    # Verify it is deleted from the DB
    assert get_file_by_path(temp_path) is None, "Deleted file still exists in database!"
    print("File pruning works successfully!")
    
    print("\n=== Step 1: ALL TESTS PASSED! ===")

if __name__ == "__main__":
    main()
