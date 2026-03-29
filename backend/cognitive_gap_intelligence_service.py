"""
Cognitive Gap Intelligence Service

This service tracks, analyzes, and acts upon cognitive gap data from reflections.
It powers:
1. Gap persistence and history tracking
2. Pattern recurrence alerts  
3. Gap-driven drill generation
4. Progress tracking over time
5. Plan quality analysis

The goal: Turn reflection data into actionable training that targets YOUR specific weaknesses.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# ============================================
# COGNITIVE GAP TO TRAINING LAYER MAPPING
# ============================================

# Map cognitive gap types to training layers and drill categories
COGNITIVE_GAP_CONFIG = {
    # Calculation errors -> Precision layer
    "calculation_depth": {
        "layer": "precision",
        "drill_category": "calculation",
        "drill_types": ["mate_in_3", "long_tactics", "defensive_calculation"],
        "training_focus": "Calculate one move deeper before deciding",
        "severity": "high",
    },
    "calculation_error": {
        "layer": "precision", 
        "drill_category": "calculation",
        "drill_types": ["simple_tactics", "piece_safety"],
        "training_focus": "Verify your calculation by checking opponent responses",
        "severity": "high",
    },
    
    # Awareness errors -> Stability layer
    "threat_blindness": {
        "layer": "stability",
        "drill_category": "threat_awareness",
        "drill_types": ["find_the_threat", "defensive_moves", "prophylaxis"],
        "training_focus": "Before moving, ask: What can opponent do to me?",
        "severity": "critical",
    },
    "hanging_piece_blindness": {
        "layer": "stability",
        "drill_category": "piece_safety",
        "drill_types": ["hanging_pieces", "undefended_pieces", "piece_safety_check"],
        "training_focus": "Before EVERY move, scan: What am I leaving undefended?",
        "severity": "critical",
    },
    "check_blindness": {
        "layer": "stability",
        "drill_category": "checks_captures_threats",
        "drill_types": ["find_the_check", "forcing_moves", "check_patterns"],
        "training_focus": "Start candidate move search with: Are there any checks?",
        "severity": "high",
    },
    
    # Tactical errors -> Precision layer
    "tactical_oversight": {
        "layer": "precision",
        "drill_category": "tactics",
        "drill_types": ["mixed_tactics", "winning_material", "combinations"],
        "training_focus": "Scan for captures and tactical opportunities",
        "severity": "high",
    },
    "missed_fork": {
        "layer": "precision",
        "drill_category": "forks",
        "drill_types": ["knight_forks", "queen_forks", "pawn_forks", "fork_patterns"],
        "training_focus": "Look for pieces that can attack two targets at once",
        "severity": "medium",
    },
    "missed_pin": {
        "layer": "precision",
        "drill_category": "pins",
        "drill_types": ["absolute_pins", "relative_pins", "pin_exploitation"],
        "training_focus": "Check for pieces on the same line as opponent's king/queen",
        "severity": "medium",
    },
    "missed_skewer": {
        "layer": "precision",
        "drill_category": "skewers",
        "drill_types": ["skewer_patterns", "x_ray_attacks"],
        "training_focus": "Look for valuable pieces in a line",
        "severity": "medium",
    },
    "missed_discovered": {
        "layer": "precision",
        "drill_category": "discovered_attacks",
        "drill_types": ["discovered_attacks", "discovered_checks"],
        "training_focus": "When moving, check: What does this uncover behind it?",
        "severity": "medium",
    },
    "back_rank_blindness": {
        "layer": "stability",
        "drill_category": "back_rank",
        "drill_types": ["back_rank_mates", "back_rank_defense", "luft"],
        "training_focus": "Ensure your king has an escape square (luft)",
        "severity": "high",
    },
    
    # Positional errors -> Structure layer
    "positional_misread": {
        "layer": "structure",
        "drill_category": "positional",
        "drill_types": ["positional_puzzles", "improving_pieces", "weak_squares"],
        "training_focus": "Ask: What is the most important feature of this position?",
        "severity": "medium",
    },
    "wrong_plan": {
        "layer": "structure",
        "drill_category": "planning",
        "drill_types": ["strategic_puzzles", "plan_finding", "piece_coordination"],
        "training_focus": "Before acting, identify what the position requires",
        "severity": "medium",
    },
    "premature_action": {
        "layer": "structure",
        "drill_category": "development",
        "drill_types": ["development_puzzles", "preparation", "prophylaxis"],
        "training_focus": "Complete development and preparation before attacking",
        "severity": "medium",
    },
    
    # Defensive errors -> Stability layer
    "defensive_lapse": {
        "layer": "stability",
        "drill_category": "defense",
        "drill_types": ["defensive_moves", "saving_lost_positions", "fortress"],
        "training_focus": "Before attacking, ALWAYS check opponent's threats",
        "severity": "high",
    },
    "king_safety_neglect": {
        "layer": "stability",
        "drill_category": "king_safety",
        "drill_types": ["king_attacks", "castling_decisions", "king_defense"],
        "training_focus": "Prioritize king safety - ask: Is my king safe?",
        "severity": "high",
    },
    
    # Psychological errors -> Stability layer
    "overconfidence": {
        "layer": "stability",
        "drill_category": "defensive",
        "drill_types": ["defensive_moves", "prophylaxis", "opponent_threats"],
        "training_focus": "When confident, double-check: What am I possibly missing?",
        "severity": "medium",
    },
    "desperation": {
        "layer": "conversion",
        "drill_category": "endgame",
        "drill_types": ["defensive_endgames", "drawing_techniques", "fortress"],
        "training_focus": "In losing positions, find the most resilient defense",
        "severity": "low",
    },
    
    # Time-related -> Stability layer
    "time_pressure": {
        "layer": "stability",
        "drill_category": "time_management",
        "drill_types": ["quick_tactics", "intuition_training", "rapid_assessment"],
        "training_focus": "Work on time management - avoid getting into time trouble",
        "severity": "medium",
    },
    "rushed_move": {
        "layer": "stability",
        "drill_category": "discipline",
        "drill_types": ["slow_tactics", "verification_puzzles"],
        "training_focus": "On critical moves, force yourself to spend at least 20 seconds",
        "severity": "medium",
    },
    
    # Pattern recognition -> Precision layer
    "pattern_unfamiliarity": {
        "layer": "precision",
        "drill_category": "pattern_recognition",
        "drill_types": ["common_patterns", "tactical_motifs", "standard_positions"],
        "training_focus": "Study common tactical and positional patterns",
        "severity": "medium",
    },
    
    # Fallback
    "unclear": {
        "layer": "precision",
        "drill_category": "mixed",
        "drill_types": ["mixed_tactics"],
        "training_focus": "Practice calculating 2-3 moves ahead",
        "severity": "low",
    },
}

# Severity weights for trend analysis
SEVERITY_WEIGHTS = {
    "critical": 3.0,
    "high": 2.0,
    "medium": 1.0,
    "low": 0.5,
}


# ============================================
# PHASE 1: DATA PERSISTENCE
# ============================================

async def persist_cognitive_gap(
    db,
    user_id: str,
    game_id: str,
    move_number: int,
    gap_analysis: Dict,
    user_plan: Optional[str] = None,
    user_confidence: Optional[str] = None,
) -> Dict:
    """
    Persist cognitive gap data for historical tracking and analysis.
    This is the foundation for all other intelligence features.
    """
    now = datetime.now(timezone.utc)
    
    gap_type = gap_analysis.get("primary_gap", "unclear")
    config = COGNITIVE_GAP_CONFIG.get(gap_type, COGNITIVE_GAP_CONFIG["unclear"])
    
    gap_record = {
        "user_id": user_id,
        "game_id": game_id,
        "move_number": move_number,
        "gap_type": gap_type,
        "confidence": gap_analysis.get("confidence", 0.5),
        "evidence": gap_analysis.get("evidence", ""),
        "explanation": gap_analysis.get("explanation", ""),
        "coaching_focus": gap_analysis.get("coaching_focus", ""),
        "secondary_gaps": gap_analysis.get("secondary_gaps", []),
        
        # User input for plan quality tracking
        "user_plan": user_plan,
        "user_confidence": user_confidence,
        
        # Derived data for analysis
        "layer": config["layer"],
        "drill_category": config["drill_category"],
        "severity": config["severity"],
        
        # Timestamps
        "created_at": now.isoformat(),
        "week_number": now.isocalendar()[1],
        "month": now.month,
        "year": now.year,
    }
    
    await db.cognitive_gap_history.insert_one(gap_record)
    
    # Update aggregated stats
    await update_gap_aggregates(db, user_id, gap_type, config)
    
    return {
        "persisted": True,
        "gap_type": gap_type,
        "layer": config["layer"],
    }


async def update_gap_aggregates(db, user_id: str, gap_type: str, config: Dict):
    """Update running aggregates for faster queries."""
    now = datetime.now(timezone.utc)
    
    await db.cognitive_gap_aggregates.update_one(
        {"user_id": user_id},
        {
            "$inc": {
                f"gap_counts.{gap_type}": 1,
                f"layer_counts.{config['layer']}": 1,
                "total_gaps": 1,
            },
            "$set": {
                "last_gap_at": now.isoformat(),
                "last_gap_type": gap_type,
            },
            "$push": {
                "recent_gaps": {
                    "$each": [{"type": gap_type, "at": now.isoformat()}],
                    "$slice": -50,  # Keep last 50
                }
            }
        },
        upsert=True
    )


# ============================================
# PHASE 2: PATTERN RECURRENCE ALERTS
# ============================================

async def check_recurrence_alerts(db, user_id: str, current_gap_type: str) -> Optional[Dict]:
    """
    Check if user has recurring pattern of this gap type.
    Returns alert if same gap occurred 3+ times in last 7 days.
    """
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    
    # Count occurrences of this gap type in last week
    count = await db.cognitive_gap_history.count_documents({
        "user_id": user_id,
        "gap_type": current_gap_type,
        "created_at": {"$gte": week_ago.isoformat()}
    })
    
    if count < 3:
        return None
    
    # Get the config for this gap
    config = COGNITIVE_GAP_CONFIG.get(current_gap_type, COGNITIVE_GAP_CONFIG["unclear"])
    
    # Calculate trend
    two_weeks_ago = now - timedelta(days=14)
    prev_week_count = await db.cognitive_gap_history.count_documents({
        "user_id": user_id,
        "gap_type": current_gap_type,
        "created_at": {
            "$gte": two_weeks_ago.isoformat(),
            "$lt": week_ago.isoformat()
        }
    })
    
    trend = "stable"
    if count > prev_week_count:
        trend = "worsening"
    elif count < prev_week_count:
        trend = "improving"
    
    gap_name = current_gap_type.replace("_", " ").title()
    
    return {
        "alert_type": "recurring_pattern",
        "gap_type": current_gap_type,
        "occurrences_this_week": count,
        "occurrences_last_week": prev_week_count,
        "trend": trend,
        "severity": config["severity"],
        "message": f"You've made '{gap_name}' mistakes {count} times this week.",
        "action_prompt": f"Train {config['drill_category']} drills to fix this pattern.",
        "drill_category": config["drill_category"],
    }


async def get_all_recurring_patterns(db, user_id: str, min_occurrences: int = 3) -> List[Dict]:
    """Get all recurring patterns for a user in the last 7 days."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    
    # Aggregate gap counts for last week
    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "created_at": {"$gte": week_ago.isoformat()}
            }
        },
        {
            "$group": {
                "_id": "$gap_type",
                "count": {"$sum": 1},
                "last_occurrence": {"$max": "$created_at"},
            }
        },
        {
            "$match": {"count": {"$gte": min_occurrences}}
        },
        {
            "$sort": {"count": -1}
        }
    ]
    
    results = await db.cognitive_gap_history.aggregate(pipeline).to_list(20)
    
    patterns = []
    for r in results:
        gap_type = r["_id"]
        config = COGNITIVE_GAP_CONFIG.get(gap_type, COGNITIVE_GAP_CONFIG["unclear"])
        
        patterns.append({
            "gap_type": gap_type,
            "gap_name": gap_type.replace("_", " ").title(),
            "occurrences": r["count"],
            "last_occurrence": r["last_occurrence"],
            "severity": config["severity"],
            "layer": config["layer"],
            "drill_category": config["drill_category"],
            "training_focus": config["training_focus"],
        })
    
    return patterns


# ============================================
# PHASE 3: GAP-DRIVEN DRILL GENERATION
# ============================================

async def get_drills_for_gap(db, user_id: str, gap_type: str, count: int = 5) -> Dict:
    """
    Generate drill positions specifically targeting a cognitive gap type.
    Uses the user's own mistakes when available, falls back to curated positions.
    """
    config = COGNITIVE_GAP_CONFIG.get(gap_type, COGNITIVE_GAP_CONFIG["unclear"])
    
    # First, try to get positions from user's own games with this gap
    user_positions = await get_user_gap_positions(db, user_id, gap_type, count)
    
    # Get curated positions for this drill category
    curated_positions = await get_curated_drill_positions(db, config["drill_category"], count)
    
    # Combine: prioritize user's own mistakes
    positions = user_positions[:3] + curated_positions[:count - len(user_positions[:3])]
    
    return {
        "gap_type": gap_type,
        "gap_name": gap_type.replace("_", " ").title(),
        "drill_category": config["drill_category"],
        "training_focus": config["training_focus"],
        "layer": config["layer"],
        "positions": positions,
        "user_positions_count": len(user_positions),
        "total_positions": len(positions),
        "drill_types": config["drill_types"],
    }


async def get_user_gap_positions(db, user_id: str, gap_type: str, limit: int = 5) -> List[Dict]:
    """Get positions from user's own games where they made this type of mistake."""
    
    # Get recent gaps of this type
    gaps = await db.cognitive_gap_history.find(
        {"user_id": user_id, "gap_type": gap_type},
        {"_id": 0, "game_id": 1, "move_number": 1, "evidence": 1}
    ).sort("created_at", -1).limit(limit * 2).to_list(limit * 2)
    
    positions = []
    for gap in gaps:
        # Get the position from game analysis
        analysis = await db.game_analyses.find_one(
            {"game_id": gap["game_id"], "user_id": user_id},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1}
        )
        
        if analysis:
            evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
            for ev in evals:
                if ev.get("move_number") == gap["move_number"]:
                    positions.append({
                        "fen": ev.get("fen_before"),
                        "best_move": ev.get("best_move"),
                        "user_move": ev.get("move"),
                        "source": "your_game",
                        "game_id": gap["game_id"],
                        "move_number": gap["move_number"],
                        "hint": gap.get("evidence", ""),
                    })
                    break
        
        if len(positions) >= limit:
            break
    
    return positions


async def get_curated_drill_positions(db, drill_category: str, limit: int = 5) -> List[Dict]:
    """Get curated drill positions for a category from the drills collection."""
    
    # Check if we have curated positions
    drills = await db.drill_positions.find(
        {"category": drill_category, "active": True},
        {"_id": 0}
    ).limit(limit).to_list(limit)
    
    if drills:
        return [
            {
                "fen": d.get("fen"),
                "best_move": d.get("solution"),
                "source": "curated",
                "difficulty": d.get("difficulty", "medium"),
                "hint": d.get("hint", ""),
            }
            for d in drills
        ]
    
    # Fallback: return empty (frontend should handle gracefully)
    return []


async def get_recommended_drills(db, user_id: str) -> Dict:
    """
    Get personalized drill recommendations based on cognitive gap history.
    Prioritizes: high severity gaps + recurring patterns.
    """
    # Get aggregates
    agg = await db.cognitive_gap_aggregates.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not agg:
        return {
            "has_data": False,
            "message": "Complete some reflections first to get personalized drill recommendations.",
            "recommendations": [],
        }
    
    gap_counts = agg.get("gap_counts", {})
    
    # Score each gap type: count * severity_weight
    scored_gaps = []
    for gap_type, count in gap_counts.items():
        config = COGNITIVE_GAP_CONFIG.get(gap_type, COGNITIVE_GAP_CONFIG["unclear"])
        score = count * SEVERITY_WEIGHTS.get(config["severity"], 1.0)
        scored_gaps.append({
            "gap_type": gap_type,
            "count": count,
            "score": score,
            "config": config,
        })
    
    # Sort by score descending
    scored_gaps.sort(key=lambda x: x["score"], reverse=True)
    
    # Get top 3 recommendations
    recommendations = []
    for sg in scored_gaps[:3]:
        recommendations.append({
            "gap_type": sg["gap_type"],
            "gap_name": sg["gap_type"].replace("_", " ").title(),
            "occurrences": sg["count"],
            "priority_score": round(sg["score"], 1),
            "drill_category": sg["config"]["drill_category"],
            "training_focus": sg["config"]["training_focus"],
            "layer": sg["config"]["layer"],
        })
    
    return {
        "has_data": True,
        "total_gaps_analyzed": agg.get("total_gaps", 0),
        "recommendations": recommendations,
        "primary_weakness": recommendations[0] if recommendations else None,
    }


# ============================================
# PHASE 4: PROGRESS TRACKING
# ============================================

async def get_gap_progress(db, user_id: str, weeks: int = 8) -> Dict:
    """
    Track how cognitive gaps are changing over time.
    Shows improvement or worsening trends.
    """
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(weeks=weeks)
    
    # Get all gaps in the time period
    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "created_at": {"$gte": start_date.isoformat()}
            }
        },
        {
            "$addFields": {
                "parsed_date": {"$dateFromString": {"dateString": "$created_at"}}
            }
        },
        {
            "$group": {
                "_id": {
                    "week": {"$isoWeek": "$parsed_date"},
                    "year": {"$isoWeekYear": "$parsed_date"},
                    "gap_type": "$gap_type"
                },
                "count": {"$sum": 1}
            }
        },
        {
            "$sort": {"_id.year": 1, "_id.week": 1}
        }
    ]
    
    results = await db.cognitive_gap_history.aggregate(pipeline).to_list(500)
    
    # Organize by gap type and week
    gap_trends = defaultdict(lambda: defaultdict(int))
    weeks_seen = set()
    
    for r in results:
        gap_type = r["_id"]["gap_type"]
        week_key = f"{r['_id']['year']}-W{r['_id']['week']:02d}"
        gap_trends[gap_type][week_key] = r["count"]
        weeks_seen.add(week_key)
    
    # Sort weeks
    sorted_weeks = sorted(weeks_seen)
    
    # Calculate trends for each gap type
    progress_data = []
    for gap_type, week_data in gap_trends.items():
        config = COGNITIVE_GAP_CONFIG.get(gap_type, COGNITIVE_GAP_CONFIG["unclear"])
        
        # Get counts for trend calculation
        counts = [week_data.get(w, 0) for w in sorted_weeks]
        
        # Calculate trend: compare first half to second half
        if len(counts) >= 2:
            mid = len(counts) // 2
            first_half_avg = sum(counts[:mid]) / max(mid, 1)
            second_half_avg = sum(counts[mid:]) / max(len(counts) - mid, 1)
            
            if first_half_avg == 0 and second_half_avg == 0:
                trend = "stable"
                change_pct = 0
            elif first_half_avg == 0:
                trend = "worsening"
                change_pct = 100
            else:
                change_pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100
                if change_pct < -20:
                    trend = "improving"
                elif change_pct > 20:
                    trend = "worsening"
                else:
                    trend = "stable"
        else:
            trend = "insufficient_data"
            change_pct = 0
        
        progress_data.append({
            "gap_type": gap_type,
            "gap_name": gap_type.replace("_", " ").title(),
            "total_occurrences": sum(counts),
            "weekly_counts": {w: week_data.get(w, 0) for w in sorted_weeks},
            "trend": trend,
            "change_percent": round(change_pct, 1),
            "severity": config["severity"],
            "layer": config["layer"],
        })
    
    # Sort by total occurrences
    progress_data.sort(key=lambda x: x["total_occurrences"], reverse=True)
    
    # Calculate overall progress
    total_first_half = sum(
        sum(list(d["weekly_counts"].values())[:len(sorted_weeks)//2])
        for d in progress_data
    )
    total_second_half = sum(
        sum(list(d["weekly_counts"].values())[len(sorted_weeks)//2:])
        for d in progress_data
    )
    
    if total_first_half > 0:
        overall_change = ((total_second_half - total_first_half) / total_first_half) * 100
    else:
        overall_change = 0
    
    return {
        "weeks_analyzed": len(sorted_weeks),
        "week_labels": sorted_weeks,
        "gaps": progress_data,
        "overall_trend": "improving" if overall_change < -15 else "worsening" if overall_change > 15 else "stable",
        "overall_change_percent": round(overall_change, 1),
        "improving_gaps": [g for g in progress_data if g["trend"] == "improving"],
        "worsening_gaps": [g for g in progress_data if g["trend"] == "worsening"],
    }


async def get_gap_summary(db, user_id: str) -> Dict:
    """Get a quick summary of cognitive gap status for dashboard display."""
    
    agg = await db.cognitive_gap_aggregates.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not agg or agg.get("total_gaps", 0) < 3:
        return {
            "has_data": False,
            "message": "Complete more reflections to see your gap analysis.",
        }
    
    gap_counts = agg.get("gap_counts", {})
    layer_counts = agg.get("layer_counts", {})
    
    # Find dominant gap
    dominant_gap = max(gap_counts.items(), key=lambda x: x[1]) if gap_counts else None
    dominant_layer = max(layer_counts.items(), key=lambda x: x[1]) if layer_counts else None
    
    # Get progress data
    progress = await get_gap_progress(db, user_id, weeks=4)
    
    return {
        "has_data": True,
        "total_gaps_tracked": agg.get("total_gaps", 0),
        "dominant_gap": {
            "type": dominant_gap[0] if dominant_gap else None,
            "name": dominant_gap[0].replace("_", " ").title() if dominant_gap else None,
            "count": dominant_gap[1] if dominant_gap else 0,
        } if dominant_gap else None,
        "dominant_layer": {
            "type": dominant_layer[0] if dominant_layer else None,
            "count": dominant_layer[1] if dominant_layer else 0,
        } if dominant_layer else None,
        "overall_trend": progress.get("overall_trend", "stable"),
        "improving_count": len(progress.get("improving_gaps", [])),
        "worsening_count": len(progress.get("worsening_gaps", [])),
    }


# ============================================
# PHASE 5: PLAN QUALITY ANALYSIS
# ============================================

async def analyze_plan_quality(db, user_id: str) -> Dict:
    """
    Analyze the quality of user's plans over time.
    Tracks: plan specificity, plan accuracy, plan improvement.
    """
    # Get all reflections with plans
    reflections = await db.cognitive_gap_history.find(
        {"user_id": user_id, "user_plan": {"$exists": True, "$nin": [None, ""]}},
        {"_id": 0, "user_plan": 1, "gap_type": 1, "created_at": 1, "user_confidence": 1}
    ).sort("created_at", -1).limit(100).to_list(100)
    
    if len(reflections) < 5:
        return {
            "has_data": False,
            "message": "Share more plans during reflection to see your plan quality analysis.",
            "plans_recorded": len(reflections),
        }
    
    # Analyze plan characteristics
    total_plans = len(reflections)
    
    # Plan specificity: longer, more detailed plans are better
    plan_lengths = [len(r.get("user_plan", "")) for r in reflections]
    avg_plan_length = sum(plan_lengths) / len(plan_lengths)
    
    # Plan accuracy: plans that don't result in major gaps are "accurate"
    high_severity_gaps = ["threat_blindness", "hanging_piece_blindness", "calculation_depth"]
    accurate_plans = sum(1 for r in reflections if r.get("gap_type") not in high_severity_gaps)
    accuracy_rate = accurate_plans / total_plans
    
    # Confidence calibration: high confidence should correlate with lower severity gaps
    confidence_data = defaultdict(lambda: {"total": 0, "accurate": 0})
    for r in reflections:
        conf = r.get("user_confidence", "unknown")
        confidence_data[conf]["total"] += 1
        if r.get("gap_type") not in high_severity_gaps:
            confidence_data[conf]["accurate"] += 1
    
    confidence_calibration = {}
    for conf, data in confidence_data.items():
        if data["total"] > 0:
            confidence_calibration[conf] = {
                "accuracy": round(data["accurate"] / data["total"] * 100, 1),
                "sample_size": data["total"],
            }
    
    # Trend: compare recent vs older plans
    mid = len(reflections) // 2
    recent_accuracy = sum(1 for r in reflections[:mid] if r.get("gap_type") not in high_severity_gaps) / max(mid, 1)
    older_accuracy = sum(1 for r in reflections[mid:] if r.get("gap_type") not in high_severity_gaps) / max(len(reflections) - mid, 1)
    
    if older_accuracy > 0:
        improvement = ((recent_accuracy - older_accuracy) / older_accuracy) * 100
    else:
        improvement = 0
    
    return {
        "has_data": True,
        "total_plans_analyzed": total_plans,
        "plan_quality": {
            "avg_length": round(avg_plan_length, 0),
            "specificity": "detailed" if avg_plan_length > 50 else "brief" if avg_plan_length > 20 else "minimal",
        },
        "accuracy": {
            "rate": round(accuracy_rate * 100, 1),
            "accurate_plans": accurate_plans,
            "total_plans": total_plans,
        },
        "confidence_calibration": confidence_calibration,
        "trend": {
            "direction": "improving" if improvement > 15 else "worsening" if improvement < -15 else "stable",
            "change_percent": round(improvement, 1),
            "recent_accuracy": round(recent_accuracy * 100, 1),
            "older_accuracy": round(older_accuracy * 100, 1),
        },
        "insight": generate_plan_insight(accuracy_rate, improvement, confidence_calibration),
    }


def generate_plan_insight(accuracy_rate: float, improvement: float, calibration: Dict) -> str:
    """Generate a human-readable insight about plan quality."""
    
    # Check confidence calibration
    very_sure = calibration.get("very_sure", {})
    guessing = calibration.get("guessing", {})
    
    if very_sure.get("accuracy", 0) < 50 and very_sure.get("sample_size", 0) >= 3:
        return "You're often confident but wrong. Try asking 'What am I missing?' when you feel sure."
    
    if guessing.get("accuracy", 0) > 70 and guessing.get("sample_size", 0) >= 3:
        return "Your 'guesses' are often good! Trust your intuition more."
    
    if improvement > 30:
        return f"Your plans are {round(improvement)}% more accurate than before. Great progress!"
    
    if improvement < -20:
        return "Your recent plans have been less accurate. Take more time to assess the position."
    
    if accuracy_rate > 0.7:
        return "Your plans are generally well-aligned with what positions require. Keep it up!"
    
    if accuracy_rate < 0.4:
        return "Focus on identifying the key features of each position before making a plan."
    
    return "Your planning is consistent. Keep reflecting to improve further."


# ============================================
# INTEGRATION: Update training focus
# ============================================

async def update_training_from_gaps(db, user_id: str) -> Dict:
    """
    Update user's training focus based on accumulated cognitive gaps.
    This integrates gap data into the training system.
    """
    # Get aggregates
    agg = await db.cognitive_gap_aggregates.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not agg or agg.get("total_gaps", 0) < 3:
        return {"updated": False, "reason": "Not enough data"}
    
    layer_counts = agg.get("layer_counts", {})
    
    # Calculate layer boosts based on gap frequency
    layer_boosts = {}
    total = sum(layer_counts.values())
    
    for layer, count in layer_counts.items():
        # Higher count = higher boost
        boost = (count / total) * 1000 if total > 0 else 0
        layer_boosts[layer] = boost
    
    # Update reflection impacts (existing system)
    await db.reflection_impacts.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "layer_boosts": layer_boosts,
                "gap_driven": True,
                "last_gap_sync": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True
    )
    
    dominant_layer = max(layer_counts.items(), key=lambda x: x[1])[0] if layer_counts else None
    
    return {
        "updated": True,
        "layer_boosts": layer_boosts,
        "dominant_layer": dominant_layer,
        "total_gaps_used": agg.get("total_gaps", 0),
    }
