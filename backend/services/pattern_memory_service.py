"""
Pattern Memory Service
======================

Aggregates recurring thinking patterns and mistake types from:
1. game_analyses (Stockfish-verified mistakes with cognitive_gap and coaching_focus)
2. question_insights (thinking patterns revealed during Q&A sessions)

This is the data source for "confrontation, not information" coaching:
- "You've ignored opponent threats 23 times in your last 20 games"
- "Overall: 113 times"

The goal: Force users to confront their undeniable, data-backed patterns.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)


# Pattern type mapping - normalize various cognitive gap / coaching focus strings
PATTERN_NORMALIZATION = {
    # From cognitive_gap_service
    "threat_oversight": "ignore_threat",
    "ignored_threat": "ignore_threat",
    "tactical_oversight": "tactical_miss",
    "missed_tactic": "tactical_miss",
    "calculation_error": "short_calculation",
    "short_calculation": "short_calculation",
    "hanging_piece": "hanging_piece",
    "piece_safety": "hanging_piece",
    "time_pressure": "time_pressure",
    "overconfidence": "overconfidence",
    "positional_blindness": "positional_miss",
    "positional_misread": "positional_miss",
    
    # From thinking_pattern detection in Q&A
    "check_first": "check_obsession",
    "check_obsession": "check_obsession",
    "pawn_grabbing": "pawn_grabbing",
    "capture_instinct": "capture_obsession",
    "trade_seeking": "trade_seeking",
}

# Human-readable labels for patterns
PATTERN_LABELS = {
    "ignore_threat": "Ignoring Opponent Threats",
    "tactical_miss": "Missing Tactics",
    "short_calculation": "Stopping Calculation Too Early",
    "hanging_piece": "Leaving Pieces Hanging",
    "time_pressure": "Time Pressure Blunders",
    "overconfidence": "Overconfident Errors",
    "positional_miss": "Positional Oversights",
    "check_obsession": "Wasting Time with Pointless Checks",
    "pawn_grabbing": "Grabbing Poisoned Pawns",
    "capture_obsession": "Reflexive Captures",
    "trade_seeking": "Trading for No Reason",
    "unknown": "Unclassified Errors",
}

# Severity thresholds
SEVERITY_THRESHOLDS = {
    "critical": 5,   # 5+ occurrences in recent games = critical
    "high": 3,       # 3-4 occurrences = high
    "medium": 2,     # 2 occurrences = medium
    "low": 1,        # 1 occurrence = low
}


def normalize_pattern(raw_pattern: str) -> str:
    """Normalize a raw pattern/gap string to a canonical pattern type."""
    if not raw_pattern:
        return "unknown"
    
    # Lowercase and clean
    clean = raw_pattern.lower().strip().replace(" ", "_").replace("-", "_")
    
    # Check direct mapping
    if clean in PATTERN_NORMALIZATION:
        return PATTERN_NORMALIZATION[clean]
    
    # Check partial matches
    for key, value in PATTERN_NORMALIZATION.items():
        if key in clean or clean in key:
            return value
    
    # Default
    return clean if clean else "unknown"


def get_severity(recent_count: int, total_count: int) -> str:
    """
    Determine severity based on recent and total counts.
    Recent matters more for urgency, total matters for weight.
    """
    if recent_count >= SEVERITY_THRESHOLDS["critical"]:
        return "critical"
    elif recent_count >= SEVERITY_THRESHOLDS["high"]:
        return "high"
    elif total_count >= 10 or recent_count >= SEVERITY_THRESHOLDS["medium"]:
        return "medium"
    else:
        return "low"


async def get_pattern_summary(
    db: AsyncIOMotorDatabase,
    user_id: str,
    recent_games_limit: int = 20
) -> Dict[str, Any]:
    """
    Get aggregated pattern summary for a user.
    
    Returns:
        {
            "patterns": [
                {
                    "pattern_type": "ignore_threat",
                    "label": "Ignoring Opponent Threats",
                    "total_count": 113,
                    "recent_count": 23,
                    "recent_games": 20,
                    "last_seen": "2026-03-21T...",
                    "severity": "critical",
                    "phase": "middlegame",  # Most common phase
                    "common_opening": "london",  # Most common opening (if detected)
                    "sample_games": ["game_abc", "game_def"]  # Recent examples
                },
                ...
            ],
            "total_games_analyzed": 50,
            "recent_games_count": 20,
            "worst_pattern": "ignore_threat",
            "updated_at": "2026-03-21T..."
        }
    """
    now = datetime.now(timezone.utc)
    
    # Get all game analyses for user
    analyses_cursor = db.game_analyses.find(
        {"user_id": user_id},
        {
            "_id": 0,
            "game_id": 1,
            "stockfish_analysis": 1,
            "interpretation": 1,
            "created_at": 1,
            "analyzed_at": 1
        }
    ).sort("created_at", -1)
    
    all_analyses = await analyses_cursor.to_list(500)  # Last 500 games max
    
    if not all_analyses:
        return {
            "patterns": [],
            "total_games_analyzed": 0,
            "recent_games_count": 0,
            "worst_pattern": None,
            "updated_at": now.isoformat()
        }
    
    # Track pattern occurrences
    pattern_data = {}  # {pattern_type: {total: N, recent: N, games: [...], phases: [...], openings: [...]}}
    total_games = len(all_analyses)
    recent_analyses = all_analyses[:recent_games_limit]
    recent_game_ids = {a.get("game_id") for a in recent_analyses}
    
    # Process each analysis
    for analysis in all_analyses:
        game_id = analysis.get("game_id", "")
        is_recent = game_id in recent_game_ids
        
        # Extract patterns from move evaluations
        sf_analysis = analysis.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        
        # Also check interpretation for primary issue
        interpretation = analysis.get("interpretation", {})
        primary_issue = interpretation.get("primary_issue")
        
        game_patterns = set()  # Patterns found in this game
        
        for move in move_evals:
            # Only consider significant mistakes
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss < 100:
                continue
            
            # Extract pattern from cognitive_gap or coaching_focus
            cognitive_gap = move.get("cognitive_gap", "")
            coaching_focus = move.get("coaching_focus", "")
            
            # Normalize the pattern
            pattern = None
            if cognitive_gap:
                pattern = normalize_pattern(cognitive_gap)
            elif coaching_focus:
                # Try to extract pattern from coaching focus text
                focus_lower = coaching_focus.lower()
                if "threat" in focus_lower:
                    pattern = "ignore_threat"
                elif "hang" in focus_lower:
                    pattern = "hanging_piece"
                elif "calculat" in focus_lower:
                    pattern = "short_calculation"
                elif "tactic" in focus_lower:
                    pattern = "tactical_miss"
            
            if pattern and pattern != "unknown":
                game_patterns.add(pattern)
                
                # Get phase if available
                phase = move.get("phase", "middlegame")
        
        # Add primary issue if we didn't find specific patterns
        if not game_patterns and primary_issue:
            game_patterns.add(normalize_pattern(primary_issue))
        
        # Update pattern_data
        for pattern in game_patterns:
            if pattern not in pattern_data:
                pattern_data[pattern] = {
                    "total": 0,
                    "recent": 0,
                    "games": [],
                    "phases": [],
                    "last_seen": None
                }
            
            pattern_data[pattern]["total"] += 1
            pattern_data[pattern]["games"].append(game_id)
            
            if is_recent:
                pattern_data[pattern]["recent"] += 1
            
            # Track last seen
            created_at = analysis.get("created_at") or analysis.get("analyzed_at")
            if created_at:
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    except:
                        created_at = None
                # Ensure timezone awareness for comparison
                if created_at and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if created_at:
                    last_seen = pattern_data[pattern]["last_seen"]
                    if last_seen and last_seen.tzinfo is None:
                        last_seen = last_seen.replace(tzinfo=timezone.utc)
                    if not last_seen or created_at > last_seen:
                        pattern_data[pattern]["last_seen"] = created_at
    
    # Also aggregate from question_insights (thinking patterns from Q&A)
    insights_cursor = db.question_insights.find(
        {"user_id": user_id} if await db.question_insights.find_one({"user_id": {"$exists": True}}) else {},
        {
            "_id": 0,
            "thinking_pattern": 1,
            "thinking_label": 1,
            "coaching_signal": 1,
            "severity": 1,
            "asked_at": 1
        }
    ).sort("asked_at", -1).limit(200)
    
    insights = await insights_cursor.to_list(200)
    
    # Note: question_insights may not have user_id field yet - check if data exists
    for insight in insights:
        thinking_pattern = insight.get("thinking_pattern", "")
        coaching_signal = insight.get("coaching_signal", "")
        
        # Only count concerning patterns (not positive ones)
        if coaching_signal == "positive" or not thinking_pattern:
            continue
        
        pattern = normalize_pattern(thinking_pattern)
        if pattern == "unknown":
            continue
        
        if pattern not in pattern_data:
            pattern_data[pattern] = {
                "total": 0,
                "recent": 0,
                "games": [],
                "phases": [],
                "last_seen": None
            }
        
        # Q&A insights count as separate occurrences
        pattern_data[pattern]["total"] += 1
        
        # Check if recent (within last week)
        asked_at = insight.get("asked_at")
        if asked_at:
            if isinstance(asked_at, str):
                try:
                    asked_at = datetime.fromisoformat(asked_at.replace("Z", "+00:00"))
                except:
                    asked_at = None
            # Ensure timezone awareness
            if asked_at and asked_at.tzinfo is None:
                asked_at = asked_at.replace(tzinfo=timezone.utc)
            
            if asked_at:
                week_ago = now - timedelta(days=7)
                if asked_at > week_ago:
                    pattern_data[pattern]["recent"] += 1
                
                last_seen = pattern_data[pattern]["last_seen"]
                if last_seen and last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                if not last_seen or asked_at > last_seen:
                    pattern_data[pattern]["last_seen"] = asked_at
    
    # Build final pattern list
    patterns = []
    for pattern_type, data in pattern_data.items():
        if data["total"] == 0:
            continue
        
        severity = get_severity(data["recent"], data["total"])
        
        patterns.append({
            "pattern_type": pattern_type,
            "label": PATTERN_LABELS.get(pattern_type, pattern_type.replace("_", " ").title()),
            "total_count": data["total"],
            "recent_count": data["recent"],
            "recent_games": recent_games_limit,
            "last_seen": data["last_seen"].isoformat() if data["last_seen"] else None,
            "severity": severity,
            "sample_games": data["games"][:3]  # Last 3 game IDs as examples
        })
    
    # Sort by recent count (urgency), then total count (weight)
    patterns.sort(key=lambda p: (p["recent_count"], p["total_count"]), reverse=True)
    
    # Determine worst pattern
    worst_pattern = patterns[0]["pattern_type"] if patterns else None
    
    return {
        "patterns": patterns,
        "total_games_analyzed": total_games,
        "recent_games_count": len(recent_analyses),
        "worst_pattern": worst_pattern,
        "updated_at": now.isoformat()
    }


async def get_pattern_for_mistake(
    db: AsyncIOMotorDatabase,
    user_id: str,
    cognitive_gap: str,
    recent_games_limit: int = 20
) -> Optional[Dict[str, Any]]:
    """
    Get pattern data for a specific cognitive gap/mistake type.
    
    Used when showing a mistake on the review page:
    "You've made this mistake 23 times in your last 20 games. Overall: 113 times."
    
    Returns:
        {
            "pattern_type": "ignore_threat",
            "label": "Ignoring Opponent Threats",
            "recent_count": 23,
            "recent_games": 20,
            "total_count": 113,
            "severity": "critical",
            "confrontation_message": "You've ignored opponent threats 23 times in your last 20 games. Overall: 113 times."
        }
    """
    summary = await get_pattern_summary(db, user_id, recent_games_limit)
    
    normalized_gap = normalize_pattern(cognitive_gap)
    
    for pattern in summary["patterns"]:
        if pattern["pattern_type"] == normalized_gap:
            # Build confrontational message
            label = pattern["label"]
            recent = pattern["recent_count"]
            total = pattern["total_count"]
            recent_games = pattern["recent_games"]
            
            if recent > 0 and total > recent:
                message = f"You've had {label.lower()} {recent} times in your last {recent_games} games. Overall: {total} times."
            elif recent > 0:
                message = f"You've had {label.lower()} {recent} times in your last {recent_games} games."
            else:
                message = f"You've had {label.lower()} {total} times total."
            
            return {
                **pattern,
                "confrontation_message": message
            }
    
    return None


async def get_top_patterns(
    db: AsyncIOMotorDatabase,
    user_id: str,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Get the user's top N worst patterns for dashboard display.
    
    Returns patterns sorted by severity and count, limited to `limit` items.
    """
    summary = await get_pattern_summary(db, user_id)
    return summary["patterns"][:limit]
