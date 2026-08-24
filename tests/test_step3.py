import os
import sys

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.search.semantic_search import semantic_search

def test_semantic_query(query: str):
    print(f"\nSearching semantic: '{query}'...")
    results = semantic_search(query, limit=5)
    print(f"Found {len(results)} results:")
    for idx, r in enumerate(results):
        print(f" {idx+1}. File: {r['filename']} (Type: {r['file_type']})")
        print(f"    Similarity Score: {r['score']:.4f}")
        print(f"    Preview: {r['content_preview']}")
    return results

def main():
    print("=== Testing Step 3: Semantic Search (ChromaDB) ===")
    
    # 1. Query matching python conceptually
    res1 = test_semantic_query("interpreted programming languages")
    assert len(res1) > 0, "Should return semantic search results!"
    assert res1[0]["filename"] == "doc1_python_intro.txt", "Top match should be doc1 (Python intro)!"
    assert 0.0 <= res1[0]["score"] <= 1.0, f"Similarity score {res1[0]['score']} out of bounds!"
    
    # 2. Query matching search strategies conceptually
    res2 = test_semantic_query("vector representations and document matching")
    assert len(res2) > 0, "Should return semantic search results!"
    assert res2[0]["filename"] == "doc2_search_strategies.docx", "Top match should be doc2 (search strategies)!"
    assert 0.0 <= res2[0]["score"] <= 1.0, f"Similarity score {res2[0]['score']} out of bounds!"
    
    # 3. Query that is ambiguous
    res3 = test_semantic_query("indexing files and searching content")
    assert len(res3) >= 2, f"Should return matches from multiple documents, got {len(res3)}"
    # Check that results are sorted descending
    for i in range(len(res3) - 1):
        assert res3[i]["score"] >= res3[i+1]["score"], "Results are not sorted by score descending!"
        
    print("\n=== Step 3: ALL TESTS PASSED! ===")

if __name__ == "__main__":
    main()
