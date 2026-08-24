import os
import sys
import time
import sqlite3
from typing import List

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.models.db import get_db_connection, log_file_access
from backend.router.router import route_and_search
from backend.search.personalize import get_access_history, calculate_personalization_boost

TEST_CORPUS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "test_corpus"))

def clear_access_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM access_log")
    conn.commit()
    conn.close()
    print("Cleared access logs.")

def insert_mock_access(filepath: str, timestamp: float):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO access_log (filepath, accessed_at) VALUES (?, ?)", (filepath, timestamp))
    conn.commit()
    conn.close()

def main():
    print("=== Testing Step 5: Personalization & Ablation Toggle ===")
    
    # 1. Clear existing access logs and run search
    clear_access_logs()
    
    # Files
    doc1_path = os.path.abspath(os.path.join(TEST_CORPUS_DIR, "doc1_python_intro.txt"))
    doc2_path = os.path.abspath(os.path.join(TEST_CORPUS_DIR, "doc2_search_strategies.docx"))
    
    # 2. Run query with personalize=True on empty logs (Cold Start verification)
    print("\n[1/3] Running search under Cold-Start conditions (no access logs)...")
    res_cold = route_and_search("python", personalize=True)
    results_cold = res_cold["results"]
    assert len(results_cold) > 0, "No results returned!"
    first_res = results_cold[0]
    print(f"Cold-Start Match: {first_res['filename']} | Score: {first_res['score']:.4f}")
    assert "Cold-start" in first_res["explanation"], "Explanation should note cold-start!"
    # Ensure score is discounted by 15% (i.e. base score * 0.85)
    # The base score for doc1 in step 2 was 1.0, so cold score should be 1.0 * 0.85 = 0.85
    print(f"Cold score: {first_res['score']:.4f} (expected: ~0.8500)")
    assert abs(first_res["score"] - 0.85) < 0.01
    
    # 3. Simulate access history for frequency and recency tests
    print("\n[2/3] Simulating user file-access patterns in SQLite log...")
    now = time.time()
    
    # doc2_search_strategies.docx: accessed 3 times (high frequency), but in the past:
    # 10 days ago (t = 10)
    print("Logging 3 accesses to doc2 (Search Strategies) from 10 days ago...")
    for _ in range(3):
        insert_mock_access(doc2_path, now - (10.0 * 86400.0))
        
    # doc1_python_intro.txt: accessed 1 time (lower frequency), but very recently:
    # 1 hour ago (t = 1/24 days)
    print("Logging 1 access to doc1 (Python Intro) from 1 hour ago...")
    insert_mock_access(doc1_path, now - 3600.0)
    
    # Verify calculated personalization boosts
    history, max_count = get_access_history()
    print(f"Logged Access History: {history} | Max Count: {max_count}")
    assert max_count == 3
    
    boost_doc1 = calculate_personalization_boost(doc1_path, history, max_count, current_time=now)
    boost_doc2 = calculate_personalization_boost(doc2_path, history, max_count, current_time=now)
    
    print("\nBoost calculations:")
    print(f" doc1 (Python Intro - 1 open, 1 hr ago):")
    print(f"   Frequency Score (1/3) : {boost_doc1['freq_score']:.4f}")
    print(f"   Recency Score (~0 days): {boost_doc1['rec_score']:.4f}")
    print(f"   Personal Score        : {boost_doc1['personal_score']:.4f}")
    
    print(f" doc2 (Search Strategies - 3 opens, 10 days ago):")
    print(f"   Frequency Score (3/3) : {boost_doc2['freq_score']:.4f}")
    print(f"   Recency Score (10 days): {boost_doc2['rec_score']:.4f}")
    print(f"   Personal Score        : {boost_doc2['personal_score']:.4f}")
    
    # Recency of doc1 (~1.0) should be much higher than doc2 (decayed over 10 days)
    assert boost_doc1["rec_score"] > boost_doc2["rec_score"]
    # Frequency of doc2 (1.0) should be higher than doc1 (0.33)
    assert boost_doc2["freq_score"] > boost_doc1["freq_score"]
    
    # 4. Compare search outputs with and without personalization (Ablation testing)
    print("\n[3/3] Running search comparison (personalize=True vs personalize=False)...")
    
    # Run query "search" which has doc2 as top FTS match and doc1 as lower match.
    # Let's run with personalization off
    res_no_pers = route_and_search("search", personalize=False)
    print("\nWithout Personalization (Base FTS5 ranking):")
    for idx, r in enumerate(res_no_pers["results"]):
        print(f" {idx+1}. {r['filename']} | Score: {r['score']:.4f}")
        
    # Run with personalization on
    res_pers = route_and_search("search", personalize=True)
    print("\nWith Personalization (Boosted ranking):")
    for idx, r in enumerate(res_pers["results"]):
        print(f" {idx+1}. {r['filename']} | Score: {r['score']:.4f}")
        print(f"    Details: {r['explanation']}")
        
    # Ensure that personalization score modified the ranking/scores properly
    # Check that score in personalized list is a blended float
    assert res_pers["results"][0]["score"] != res_no_pers["results"][0]["score"]
    
    print("\n=== Step 5: ALL TESTS PASSED! ===")

if __name__ == "__main__":
    main()
