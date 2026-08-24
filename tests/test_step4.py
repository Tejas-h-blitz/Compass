import os
import sys
import sqlite3

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.router.router import classify_query, route_and_search
from backend.models.db import get_db_connection

def test_router_query(query: str):
    print(f"\nRouting query: '{query}'...")
    res = route_and_search(query)
    print(f"Chosen Strategy: {res['strategy_chosen']}")
    print(f"Latency: {res['latency_ms']:.2f} ms")
    print(f"Found {len(res['results'])} results:")
    for idx, r in enumerate(res['results']):
        print(f" {idx+1}. File: {r['filename']} (Type: {r['file_type']})")
        print(f"    Merged Score: {r['score']:.4f}")
        print(f"    Explanation: {r['explanation']}")
        print(f"    Preview: {r['content_preview']}")
    return res

def main():
    print("=== Testing Step 4: Router, Classification, & Logging ===")
    
    # 1. Test query classification rules
    print("\n[1/4] Verifying classifier rules...")
    assert classify_query("doc3_dummy_test.pdf") == "keyword"
    assert classify_query("python") == "keyword"
    assert classify_query("programming language") == "keyword"
    assert classify_query("something about python") == "semantic"
    assert classify_query("that thing about search strategies") == "semantic"
    assert classify_query("what is the best search strategy for files") == "hybrid"
    print("Classification rules verified successfully!")
    
    # Clear query logs for a clean check
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM query_log")
    conn.commit()
    conn.close()
    
    # 2. Test keyword path end-to-end
    print("\n[2/4] Verifying keyword path...")
    res_kw = test_router_query("python")
    assert res_kw["strategy_chosen"] == "keyword"
    assert len(res_kw["results"]) > 0
    assert "keyword" in res_kw["results"][0]["explanation"]
    
    # Verify log entry in SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT query, strategy, latency_ms, result_count FROM query_log WHERE query = 'python'")
    log = cursor.fetchone()
    conn.close()
    assert log is not None, "Keyword search was not logged!"
    print(f"Logged entry: Query='{log[0]}', Strategy='{log[1]}', Latency={log[2]:.2f}ms, Results={log[3]}")
    
    # 3. Test semantic path end-to-end
    print("\n[3/4] Verifying semantic path...")
    res_sem = test_router_query("something about search strategies")
    assert res_sem["strategy_chosen"] == "semantic"
    assert len(res_sem["results"]) > 0
    assert "semantic" in res_sem["results"][0]["explanation"]
    
    # Verify log entry in SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT query, strategy, latency_ms, result_count FROM query_log WHERE query = 'something about search strategies'")
    log = cursor.fetchone()
    conn.close()
    assert log is not None, "Semantic search was not logged!"
    print(f"Logged entry: Query='{log[0]}', Strategy='{log[1]}', Latency={log[2]:.2f}ms, Results={log[3]}")
    
    # 4. Test hybrid path end-to-end
    print("\n[4/4] Verifying hybrid path...")
    res_hy = test_router_query("introduction to search models")
    assert res_hy["strategy_chosen"] == "hybrid"
    assert len(res_hy["results"]) > 0
    
    # Let's inspect hybrid merge results
    # Each result should have a combined score
    first_result = res_hy["results"][0]
    assert 0.0 <= first_result["score"] <= 1.0
    assert "hybrid" in first_result["strategy"]
    assert "Hybrid match" in first_result["explanation"]
    
    # Verify log entry in SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT query, strategy, latency_ms, result_count FROM query_log WHERE query = 'introduction to search models'")
    log = cursor.fetchone()
    conn.close()
    assert log is not None, "Hybrid search was not logged!"
    print(f"Logged entry: Query='{log[0]}', Strategy='{log[1]}', Latency={log[2]:.2f}ms, Results={log[3]}")
    
    print("\n=== Step 4: ALL TESTS PASSED! ===")

if __name__ == "__main__":
    main()
