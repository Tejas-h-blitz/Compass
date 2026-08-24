import os
import sys
import math
import time
from typing import Dict, Any, Tuple

# Ensure import paths work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from backend.models.db import get_db_connection

# Exponential decay constant lambda calculation:
# H = half life in days (14.0)
# e^(-lambda * H) = 0.5  =>  -lambda * 14.0 = ln(0.5)  =>  -lambda * 14.0 = -0.693147
# lambda = 0.6931471805599453 / 14.0 = 0.04951051289713895
HALF_LIFE_DAYS = 14.0
DECAY_LAMBDA = 0.6931471805599453 / HALF_LIFE_DAYS

def get_access_history() -> Tuple[Dict[str, Tuple[int, float]], int]:
    """
    Queries the SQLite access logs and returns:
    1. A dictionary mapping filepath -> (open_count, last_accessed_timestamp)
    2. The maximum open count among all files (used for normalization)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    history = {}
    max_count = 0
    
    try:
        # Group by filepath to count accesses (frequency) and get the latest access time (recency)
        cursor.execute("""
            SELECT filepath, COUNT(*), MAX(accessed_at)
            FROM access_log
            GROUP BY filepath
        """)
        rows = cursor.fetchall()
        for row in rows:
            filepath = row[0]
            count = row[1]
            last_accessed = row[2]
            history[filepath] = (count, last_accessed)
            if count > max_count:
                max_count = count
                
    except Exception as e:
        print(f"Error reading access history: {e}")
    finally:
        conn.close()
        
    return history, max_count

def calculate_personalization_boost(
    filepath: str, 
    history: Dict[str, Tuple[int, float]], 
    max_count: int,
    current_time: float = None
) -> Dict[str, Any]:
    """
    Calculates personalization boost components for a file path.
    
    Formula:
    S_personal = 0.5 * S_frequency + 0.5 * S_recency
    
    Where:
    - S_frequency = open_count / max_count
    - S_recency = e^(-lambda * t_days)
    """
    if current_time is None:
        current_time = time.time()
        
    if filepath not in history or max_count == 0:
        # Cold start case: zero historical interactions
        # Return 0.0 scores, but keep details explicit for explanations
        return {
            "personal_score": 0.0,
            "freq_score": 0.0,
            "rec_score": 0.0,
            "count": 0,
            "days_ago": None
        }
        
    open_count, last_accessed = history[filepath]
    
    # 1. Frequency score (normalized linear boost)
    freq_score = open_count / max_count
    
    # 2. Recency score (exponential decay)
    time_diff_sec = current_time - last_accessed
    # Convert seconds difference to fractional days
    t_days = max(0.0, time_diff_sec / 86400.0)
    rec_score = math.exp(-DECAY_LAMBDA * t_days)
    
    # 3. Blended personalization score in [0, 1]
    personal_score = (0.5 * freq_score) + (0.5 * rec_score)
    
    return {
        "personal_score": personal_score,
        "freq_score": freq_score,
        "rec_score": rec_score,
        "count": open_count,
        "days_ago": round(t_days, 2)
    }
