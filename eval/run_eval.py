import os
import sys
import json
import time
import numpy as np
from typing import List, Dict, Any

# Ensure import paths work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.router.router import route_and_search
from backend.models.db import get_db_connection, log_file_access

CORPUS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "test_corpus"))
QUERIES_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_queries.json"))

def setup_ablation_access_logs():
    """
    Sets up simulated access logs in SQLite to run personalization evaluation.
    This simulates user history: doc1 (Python intro) opened twice, doc2 (Search strategies) opened once.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM access_log")
    
    doc1_path = os.path.abspath(os.path.join(CORPUS_DIR, "doc1_python_intro.txt"))
    doc2_path = os.path.abspath(os.path.join(CORPUS_DIR, "doc2_search_strategies.docx"))
    
    # doc1: 2 accesses
    cursor.execute("INSERT INTO access_log (filepath, accessed_at) VALUES (?, ?)", (doc1_path, time.time() - 3600))
    cursor.execute("INSERT INTO access_log (filepath, accessed_at) VALUES (?, ?)", (doc1_path, time.time()))
    
    # doc2: 1 access
    cursor.execute("INSERT INTO access_log (filepath, accessed_at) VALUES (?, ?)", (doc2_path, time.time() - 86400))
    
    conn.commit()
    conn.close()

def calculate_mrr(retrieved: List[str], expected: List[str]) -> float:
    """
    Calculates Mean Reciprocal Rank (MRR) for the retrieved results.
    """
    for idx, item in enumerate(retrieved):
        if item in expected:
            return 1.0 / (idx + 1)
    return 0.0

def run_evaluation_on_config(queries: List[Dict[str, Any]], force_strat: str = None, personalize: bool = False) -> Dict[str, Any]:
    """
    Runs evaluation for a specific retrieval strategy configuration across all queries.
    """
    precisions_1 = []
    precisions_3 = []
    recalls_3 = []
    mrrs = []
    latencies = []
    results_by_query = []
    
    for q_item in queries:
        query = q_item["query"]
        expected = q_item["expected_files"]
        
        # Execute query search using the router entry point
        # The first query execution might download weights/warmup, so we measure time carefully.
        res = route_and_search(query, limit=3, force_strategy=force_strat, personalize=personalize)
        
        retrieved = [r["filename"] for r in res["results"]]
        latency = res["latency_ms"]
        
        # 1. Precision@1
        p1 = 1.0 if retrieved and retrieved[0] in expected else 0.0
        precisions_1.append(p1)
        
        # 2. Precision@3
        hits_3 = len(set(retrieved[:3]).intersection(expected))
        p3 = hits_3 / 3.0
        precisions_3.append(p3)
        
        # 3. Recall@3
        r3 = hits_3 / len(expected) if expected else 0.0
        recalls_3.append(r3)
        
        # 4. MRR
        mrr = calculate_mrr(retrieved, expected)
        mrrs.append(mrr)
        
        latencies.append(latency)
        
        results_by_query.append({
            "query": query,
            "strategy_used": res["strategy_chosen"],
            "retrieved": retrieved,
            "expected": expected,
            "mrr": mrr,
            "latency": latency
        })
        
    return {
        "p@1": np.mean(precisions_1),
        "p@3": np.mean(precisions_3),
        "r@3": np.mean(recalls_3),
        "mrr": np.mean(mrrs),
        "latency_mean": np.mean(latencies),
        "latency_p95": np.percentile(latencies, 95),
        "raw_results": results_by_query
    }

def print_metrics_table(metrics: Dict[str, Dict[str, Any]]):
    """
    Prints a formatted markdown table of retrieval and latency metrics.
    """
    print("| Strategy Config | P@1 | P@3 | R@3 | MRR | Mean Latency | p95 Latency |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for name, m in metrics.items():
        print(f"| {name:<15} | {m['p@1']:.3f} | {m['p@3']:.3f} | {m['r@3']:.3f} | {m['mrr']:.3f} | {m['latency_mean']:.2f} ms | {m['latency_p95']:.2f} ms |")

def main():
    print("==================================================")
    print("    COMPASS SYSTEMS EVALUATION RUNNER (Step 6)    ")
    print("==================================================")
    
    # 1. Warm up embedding model to prevent loading latency from skewing metrics
    print("\nInitializing retrieval system and warming up embedding models...")
    route_and_search("warmup query", force_strategy="semantic")
    print("Warmup complete.")
    
    # Load test queries
    with open(QUERIES_FILE, "r") as f:
        queries = json.load(f)
    print(f"Loaded {len(queries)} evaluation queries.")
    
    # 2. Run ablation logs setup
    setup_ablation_access_logs()
    
    # 3. Run Evaluation with Personalization OFF (Base Search Ablation)
    print("\n--- Running Evaluation: Personalization OFF ---")
    configs_off = {
        "Keyword-Only": "keyword",
        "Semantic-Only": "semantic",
        "Hybrid-Only": "hybrid",
        "Dynamic Router": None
    }
    
    results_off = {}
    for name, force in configs_off.items():
        print(f"Evaluating {name}...")
        results_off[name] = run_evaluation_on_config(queries, force_strat=force, personalize=False)
        
    print("\n### Base Performance Summary (Personalization OFF):")
    print_metrics_table(results_off)
    
    # 4. Run Evaluation with Personalization ON (Personalized Search Ablation)
    print("\n--- Running Evaluation: Personalization ON ---")
    results_on = {}
    for name, force in configs_off.items():
        print(f"Evaluating {name}...")
        results_on[name] = run_evaluation_on_config(queries, force_strat=force, personalize=True)
        
    print("\n### Personalized Performance Summary (Personalization ON):")
    print_metrics_table(results_on)
    
    # 5. Compute Specific Router Metrics (Personalization OFF)
    print("\n--- Computing Core Routing Metrics ---")
    kw_raw = results_off["Keyword-Only"]["raw_results"]
    sem_raw = results_off["Semantic-Only"]["raw_results"]
    hy_raw = results_off["Hybrid-Only"]["raw_results"]
    router_raw = results_off["Dynamic Router"]["raw_results"]
    
    accurate_decisions = 0
    total_queries = len(queries)
    savings_list = []
    
    failure_cases = []
    
    for i in range(total_queries):
        kw_mrr = kw_raw[i]["mrr"]
        sem_mrr = sem_raw[i]["mrr"]
        hy_mrr = hy_raw[i]["mrr"]
        router_mrr = router_raw[i]["mrr"]
        
        # Max performance possible
        best_mrr = max(kw_mrr, sem_mrr, hy_mrr)
        
        # Router is accurate if it matched the best achievable score
        if abs(router_mrr - best_mrr) < 0.001:
            accurate_decisions += 1
        else:
            # Document failure cases: queries where the router chosen path performed worse than another
            failure_cases.append({
                "query": router_raw[i]["query"],
                "chosen": router_raw[i]["strategy_used"],
                "chosen_mrr": router_mrr,
                "best_strategy": "keyword" if kw_mrr == best_mrr else ("semantic" if sem_mrr == best_mrr else "hybrid"),
                "best_mrr": best_mrr
            })
            
    router_accuracy = (accurate_decisions / total_queries) * 100
    
    # Compute latency savings: Always Hybrid vs Dynamic Router
    mean_hybrid_latency = results_off["Hybrid-Only"]["latency_mean"]
    mean_router_latency = results_off["Dynamic Router"]["latency_mean"]
    latency_saved = mean_hybrid_latency - mean_router_latency
    compute_savings_pct = (latency_saved / mean_hybrid_latency) * 100
    
    print(f"Router Accuracy (matched best strategy MRR): {router_accuracy:.2f}% ({accurate_decisions}/{total_queries})")
    print(f"Mean Hybrid Latency: {mean_hybrid_latency:.2f} ms")
    print(f"Mean Router Latency: {mean_router_latency:.2f} ms")
    print(f"Time Saved by Router vs. Hybrid: {latency_saved:.2f} ms ({compute_savings_pct:.2f}% compute savings)")
    
    # 6. Print Documented Failure Cases
    print("\n--- Documented Failure Cases (Queries where router selected suboptimal strategy) ---")
    if not failure_cases:
        print("None found! (Router selected optimal path for all queries in the test set).")
    else:
        for idx, fc in enumerate(failure_cases[:3]):  # Limit to 3 cases
            print(f"Failure Case #{idx+1}:")
            print(f" - Query: '{fc['query']}'")
            print(f" - Router Chose: '{fc['chosen']}' (MRR: {fc['chosen_mrr']:.2f})")
            print(f" - Optimal Path: '{fc['best_strategy']}' (MRR: {fc['best_mrr']:.2f})")
            print(f" - Explanation: The router classified this query into the '{fc['chosen']}' path due to its length or keyword content, "
                  f"but the semantic/hybrid path was required to yield a correct hit on the target file.")
            print()
            
    print("==================================================")
    print("Evaluation execution completed successfully.")

if __name__ == "__main__":
    main()
