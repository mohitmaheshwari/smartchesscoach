"""
Stagnation Detector Module

Detects when a user is stuck in the same problem loop.

Rules:
- Stagnation = same main_problem for 3+ consecutive games
- When stagnation detected, tone shifts to FIRM
- Anti-repetition: track used insights to vary messaging
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta


async def detect_stagnation(
    db,
    user_id: str,
    current_main_problem: str
) -> Dict:
    """
    Detect if user is stuck in the same problem loop.
    
    Returns:
        {
            "is_stagnated": True/False,
            "consecutive_games": 3,
            "stagnation_problem": "DECISION_STABILITY",
            "tone": "FIRM" | "NORMAL"
        }
    """
    # Get last 3 behavioral reports
    reports = await db.behavioral_reports.find(
        {"user_id": user_id},
        {"main_problem": 1, "created_at": 1}
    ).sort("created_at", -1).limit(3).to_list(3)
    
    if len(reports) < 2:
        return {
            "is_stagnated": False,
            "consecutive_games": 0,
            "stagnation_problem": None,
            "tone": "NORMAL"
        }
    
    # Check if all have same main problem
    problems = [r.get("main_problem") for r in reports]
    
    # Add current problem
    all_problems = [current_main_problem] + problems[:2]
    
    # Check for stagnation (3 consecutive same problems)
    is_stagnated = len(set(all_problems)) == 1 and all_problems[0] != "NONE"
    
    if is_stagnated:
        return {
            "is_stagnated": True,
            "consecutive_games": len(all_problems),
            "stagnation_problem": all_problems[0],
            "tone": "FIRM"
        }
    
    # Check for 2 consecutive (use slightly firmer tone)
    if len(all_problems) >= 2 and all_problems[0] == all_problems[1] and all_problems[0] != "NONE":
        return {
            "is_stagnated": False,
            "consecutive_games": 2,
            "stagnation_problem": all_problems[0],
            "tone": "NORMAL"  # Not firm yet, but tracking
        }
    
    return {
        "is_stagnated": False,
        "consecutive_games": 0,
        "stagnation_problem": None,
        "tone": "NORMAL"
    }


async def store_behavioral_report(
    db,
    user_id: str,
    game_id: str,
    main_problem: str,
    root_cause: str,
    headline_template: str = None
) -> None:
    """
    Store a behavioral report for stagnation tracking.
    """
    report = {
        "user_id": user_id,
        "game_id": game_id,
        "main_problem": main_problem,
        "root_cause": root_cause,
        "headline_template": headline_template,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.behavioral_reports.update_one(
        {"user_id": user_id, "game_id": game_id},
        {"$set": report},
        upsert=True
    )


async def check_template_used_recently(
    db,
    user_id: str,
    template_key: str,
    days: int = 14
) -> bool:
    """
    Check if a headline template was used recently.
    Used for anti-repetition.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    count = await db.behavioral_reports.count_documents({
        "user_id": user_id,
        "headline_template": template_key,
        "created_at": {"$gte": cutoff.isoformat()}
    })
    
    return count > 0
