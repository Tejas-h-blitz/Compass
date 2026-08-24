import os
import sys

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.search.keyword_search import keyword_search

def test_query(query: str):
    print(f"\nSearching keyword: '{query}'...")
    results = keyword_search(query)
    print(f"Found {len(results)} results:")
    for idx, r in enumerate(results):
        print(f" {idx+1}. File: {r['filename']} (Type: {r['file_type']})")
        print(f"    Raw Score: {r['raw_score']:.4f} | Normalized Score: {r['score']:.4f}")
        print(f"    Preview: {r['content_preview']}")
    return results

def main():
    print("=== Testing Step 2: SQLite FTS5 Keyword Search ===")
    
    # 1. Search for a word only in doc1
    res1 = test_query("python")
    assert len(res1) > 0, "Should have found python intro file!"
    assert res1[0]["filename"] == "doc1_python_intro.txt", "Top result should be doc1!"
    assert res1[0]["score"] == 1.0, "Top result normalized score must be 1.0"
    
    # 2. Search for a word only in doc2
    res2 = test_query("retrieval")
    assert len(res2) > 0, "Should have found retrieval strategies docx!"
    assert res2[0]["filename"] == "doc2_search_strategies.docx", "Top result should be doc2!"
    assert res2[0]["score"] == 1.0, "Top result normalized score must be 1.0"
    
    # 3. Search for a word matching multiple files (e.g. "test")
    # doc1: "test document", doc2: "test document", doc3: "dummy test"
    res3 = test_query("test")
    assert len(res3) >= 2, f"Should match multiple files, found {len(res3)}"
    assert res3[0]["score"] == 1.0, "Top result normalized score must be 1.0"
    # Ensure scores are descending and normalized between 0 and 1
    for r in res3:
        assert 0.0 <= r["score"] <= 1.0, f"Score {r['score']} out of bounds!"
    
    # 4. Search for a query that does not exist
    res4 = test_query("nonexistentxyz")
    assert len(res4) == 0, f"Expected 0 results for nonexistent query, got {len(res4)}"
    
    # 5. Test partial prefix matching (wildcard in query parser)
    res5 = test_query("strat")
    assert len(res5) > 0, "Prefix matching failed for 'strat' (should match strategies)!"
    assert res5[0]["filename"] == "doc2_search_strategies.docx", "Prefix 'strat' should match doc2!"
    
    print("\n=== Step 2: ALL TESTS PASSED! ===")

if __name__ == "__main__":
    main()
