import os
import sys
import time
import math
from typing import Dict, Any, List

# Ensure import paths work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from backend.models.db import get_recent_and_frequent_files, get_db_connection
from backend.search.personalize import get_access_history, calculate_personalization_boost, DECAY_LAMBDA

def format_time_ago(timestamp: float, current_time: float) -> str:
    """
    Returns a human-readable relative time string.
    """
    diff_sec = max(0.0, current_time - timestamp)
    if diff_sec < 3600:
        mins = max(1, int(diff_sec / 60))
        return f"{mins}m ago"
    elif diff_sec < 86400:
        hours = int(diff_sec / 3600)
        return f"{hours}h ago"
    else:
        days = int(diff_sec / 86400)
        if days == 1:
            return "yesterday"
        return f"{days}d ago"

def get_smart_recommendations(limit: int = 6) -> List[Dict[str, Any]]:
    """
    Generates intelligent zero-query file recommendations.
    Surfaces files based on:
    1. Historical access frequency and exponential recency decay.
    2. Recently modified documents across monitored horizons.
    """
    current_time = time.time()
    candidates = get_recent_and_frequent_files(limit=limit * 2)
    history, max_count = get_access_history()

    scored_items = []
    for c in candidates:
        filepath = c["filepath"]
        filename = c["filename"]
        file_type = c["file_type"]
        file_size = c["file_size"]
        modified_at = c["modified_at"]
        preview = c.get("preview", "")

        if filepath in history and max_count > 0:
            open_count, last_accessed = history[filepath]
            boost = calculate_personalization_boost(filepath, history, max_count, current_time=current_time)
            personal_score = boost["personal_score"]
            freq_score = boost["freq_score"]
            rec_score = boost["rec_score"]

            time_ago_str = format_time_ago(last_accessed, current_time)
            if open_count > 2 and rec_score > 0.6:
                reason = f"Frequently & recently used ({open_count} opens, {time_ago_str})"
                badge = "FAVORITE"
            elif open_count > 1:
                reason = f"Accessed {open_count} times ({time_ago_str})"
                badge = "FREQUENT"
            else:
                reason = f"Opened {time_ago_str}"
                badge = "RECENT"

            # Blend score with slight weight on recency
            final_score = (0.6 * rec_score) + (0.4 * freq_score)
        else:
            # Cold-start: file not yet opened through Compass, but recently modified on disk
            time_diff_days = max(0.0, (current_time - modified_at) / 86400.0)
            rec_score = math.exp(-DECAY_LAMBDA * time_diff_days)
            time_ago_str = format_time_ago(modified_at, current_time)
            
            reason = f"Modified {time_ago_str} on disk"
            badge = "ACTIVE"
            final_score = 0.5 * rec_score

        scored_items.append({
            "filepath": filepath,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "modified_at": modified_at,
            "score": round(final_score, 3),
            "reason": reason,
            "badge": badge,
            "content_preview": preview.strip() if preview else "No preview content available."
        })

    # Sort by recommendation score descending
    scored_items.sort(key=lambda x: x["score"], reverse=True)
    return scored_items[:limit]
