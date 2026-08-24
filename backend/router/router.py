import os
import sys
import time
from typing import Dict, Any, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from backend.models.db import log_query_decision
from backend.search.keyword_search import keyword_search
from backend.search.semantic_search import semantic_search

# List of semantic markers that indicate the user is looking for a concept,
# topic, or abstract memory, rather than an exact file name or exact word.
SEMANTIC_MARKERS = [
    "that thing", "something about", "i remember", "looking for", 
    "concept of", "topic on", "idea behind", "details about", 
    "summarize", "find documents discussing"
]

# File extensions that we index and might match filename queries
KNOWN_EXTENSIONS = {
    ".pdf", ".docx", ".txt", ".py", ".md", ".json", ".js", 
    ".html", ".css", ".java", ".c", ".cpp", ".h", ".csv", 
    ".xml", ".ini", ".yaml", ".yml"
}

def classify_query(query: str) -> str:
    """
    Classifies a query to choose the optimal retrieval strategy.
    
    Rules for v1:
    - Ends in a known file extension (e.g. 'resume.pdf') OR is very short (<= 2 words) -> 'keyword'
    - Contains semantic trigger phrases (e.g. 'something about python') -> 'semantic'
    - Otherwise -> 'hybrid'
    """
    query_lower = query.lower().strip()
    words = query_lower.split()
    
    if not words:
        return "keyword"
        
    # Check if query ends with or looks like a file extension
    has_extension = False
    for ext in KNOWN_EXTENSIONS:
        if query_lower.endswith(ext) or f".{query_lower.split('.')[-1]}" in KNOWN_EXTENSIONS:
            has_extension = True
            break
            
    # Rule 1: Filename-like or very short query -> keyword path
    if has_extension or len(words) <= 2:
        return "keyword"
        
    # Rule 2: Query contains vague/descriptive semantic markers -> semantic path
    for marker in SEMANTIC_MARKERS:
        if marker in query_lower:
            return "semantic"
            
    # Rule 3: Ambiguous queries -> hybrid path
    return "hybrid"

def route_and_search(
    query: str, 
    limit: int = 10, 
    hybrid_weight: float = 0.5, 
    personalize: bool = True,
    force_strategy: str = None
) -> Dict[str, Any]:
    """
    Routes query, executes retrieval, merges results if hybrid, applies personalization,
    logs choice and performance, and slices to final limit.
    """
    start_time = time.perf_counter()
    
    # 1. Classify query or use forced strategy
    strategy = force_strategy if force_strategy else classify_query(query)
    
    # If personalizing, we retrieve more candidates so that files with high access
    # rates can boost/bubble up from lower base positions into the top list.
    candidate_limit = limit * 2 if personalize else limit
    results = []
    
    # 2. Execute retrieval based on selected strategy
    if strategy == "keyword":
        results = keyword_search(query, limit=candidate_limit)
        # Add explanations
        for r in results:
            r["explanation"] = f"Matched via FTS5 keyword search on filename or exact text content (score: {r['score']:.2f})."
            
    elif strategy == "semantic":
        results = semantic_search(query, limit=candidate_limit)
        # Add explanations
        for r in results:
            r["explanation"] = f"Matched concept/meaning via local semantic search (similarity: {r['score']:.2f})."
            
    elif strategy == "hybrid":
        # Run both paths (expanding retrieve window for better merge pool)
        kw_results = keyword_search(query, limit=candidate_limit)
        sem_results = semantic_search(query, limit=candidate_limit)
        
        # Merge results using weight parameter (default 50/50)
        # S_hybrid = w * S_kw + (1 - w) * S_sem
        merged_matches: Dict[str, Dict[str, Any]] = {}
        
        # Add keyword results
        for r in kw_results:
            filepath = r["filepath"]
            merged_matches[filepath] = {
                "doc": r,
                "kw_score": r["score"],
                "sem_score": 0.0,
                "sources": {"keyword"}
            }
            
        # Add or update semantic results
        for r in sem_results:
            filepath = r["filepath"]
            if filepath in merged_matches:
                merged_matches[filepath]["sem_score"] = r["score"]
                merged_matches[filepath]["sources"].add("semantic")
                # Keep the preview from semantic search if it has a matched chunk snippet, 
                # as sentence chunk matching is more specific than document preview
                merged_matches[filepath]["doc"]["content_preview"] = r["content_preview"]
            else:
                merged_matches[filepath] = {
                    "doc": r,
                    "kw_score": 0.0,
                    "sem_score": r["score"],
                    "sources": {"semantic"}
                }
                
        # Calculate final merged scores
        for filepath, match in merged_matches.items():
            kw_score = match["kw_score"]
            sem_score = match["sem_score"]
            
            # Hybrid score formula
            hybrid_score = (hybrid_weight * kw_score) + ((1.0 - hybrid_weight) * sem_score)
            
            doc = match["doc"]
            doc["score"] = round(hybrid_score, 4)
            doc["strategy"] = "hybrid"
            
            # Explain which strategies contributed
            sources = match["sources"]
            if "keyword" in sources and "semantic" in sources:
                doc["explanation"] = (
                    f"Hybrid match! Found by both keyword (weight: {hybrid_weight:.1f}, score: {kw_score:.2f}) "
                    f"and semantic (weight: {1.0 - hybrid_weight:.1f}, similarity: {sem_score:.2f})."
                )
            elif "keyword" in sources:
                doc["explanation"] = (
                    f"Hybrid match! Found only by keyword path "
                    f"(weight: {hybrid_weight:.1f}, score: {kw_score:.2f}, semantic: 0.00)."
                )
            else:
                doc["explanation"] = (
                    f"Hybrid match! Found only by semantic path "
                    f"(weight: {1.0 - hybrid_weight:.1f}, similarity: {sem_score:.2f}, keyword: 0.00)."
                )
                
            results.append(doc)
            
    # 3. Apply personalization boost if enabled
    if personalize:
        from backend.search.personalize import get_access_history, calculate_personalization_boost
        history, max_count = get_access_history()
        
        for r in results:
            base_score = r["score"]
            # Compute boost details based on frequency and recency decay
            p_boost = calculate_personalization_boost(r["filepath"], history, max_count)
            personal_score = p_boost["personal_score"]
            
            # Blend: S_final = 0.85 * S_base + 0.15 * S_personalization
            # Cold-start consideration: files with zero access history are not buried,
            # they are just scaled down by 15%, ensuring discoverability.
            final_score = (0.85 * base_score) + (0.15 * personal_score)
            r["score"] = round(final_score, 4)
            
            base_explanation = r["explanation"]
            if p_boost["count"] > 0:
                r["explanation"] = (
                    f"{base_explanation} [Personalized Boost: +{0.15 * personal_score:.2f} "
                    f"(base: {base_score:.2f}, opens: {p_boost['count']}, last accessed: {p_boost['days_ago']} days ago)]."
                )
            else:
                r["explanation"] = (
                    f"{base_explanation} [Personalized: Cold-start (base score scaled to {final_score:.2f})]."
                )
                
    # 4. Sort and slice to final limit
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:limit]
    
    latency_ms = (time.perf_counter() - start_time) * 1000
    
    # 5. Log query decision for objective evaluation
    log_query_decision(
        query=query,
        strategy=strategy,
        latency_ms=latency_ms,
        result_count=len(results)
    )
    
    return {
        "query": query,
        "strategy_chosen": strategy,
        "latency_ms": round(latency_ms, 2),
        "results": results
    }
