"""
Player Habits Service
=====================

Analyzes player behavior patterns and generates smart coaching.
This goes beyond move quality — it understands the PLAYER:
- Time management (rushing vs overthinking)
- Calculation habits (depth, accuracy)
- Phase performance (opening/middlegame/endgame)
- Recurring patterns (same mistakes, tilt tendencies)
- Emotional state (tilt detection, recovery)

Used by BOTH Play with Coach (live) and Lab (post-game).
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ─── BEHAVIORAL COACHING MESSAGES ───────────────────────────────────

def generate_behavioral_coaching(
    move_san: str,
    time_spent: float,
    move_quality: str,
    game_phase: str,
    behavior_events: List[Dict],
    move_history: List[Dict],
    player_profile: Optional[Dict] = None
) -> Optional[Dict]:
    """
    Generate behavioral coaching for a move.
    Returns a coaching dict with message, type, and severity.
    
    This is the LIVE coaching that tells players about their HABITS,
    not just their moves.
    """
    if not move_history:
        return None
    
    # Get recent player moves (last 5)
    recent_player_moves = [m for m in move_history if m.get("by") == "player"][-5:]
    len([m for m in move_history if m.get("by") == "player"])
    
    # Check for behaviors detected on THIS move
    latest_behaviors = []
    for evt in behavior_events:
        if evt.get("move_san") == move_san:
            latest_behaviors.append(evt)
    
    coaching = None
    
    # ─── BLUNDER/MISTAKE: Always give behavioral coaching ───
    if move_quality == "blunder":
        if time_spent < 3.0:
            coaching = {
                "type": "time_management",
                "severity": "high",
                "icon": "clock",
                "message": f"Whoa — {move_san} in {time_spent:.0f}s? You didn't calculate at all. "
                           f"Quick moves in complex spots = blunders.",
                "habit": "impulse_move",
                "actionable_tip": "Before moving, ask yourself: 'What can my opponent capture or attack after this?'"
            }
        elif time_spent < 10.0:
            coaching = {
                "type": "calculation",
                "severity": "high",
                "icon": "brain",
                "message": f"You spent {time_spent:.0f}s on {move_san} but missed the danger. "
                           f"Your calculation needs to go deeper — check captures, checks, and threats before committing.",
                "habit": "calculation_miss",
                "actionable_tip": "Use the 'CCT' method: Checks, Captures, Threats. Scan all three before every move."
            }
        else:
            coaching = {
                "type": "calculation",
                "severity": "high",
                "icon": "brain",
                "message": f"You took {time_spent:.0f}s but still missed it. "
                           f"The issue isn't time — it's how you're calculating. "
                           f"Try to look at your opponent's best response to your move.",
                "habit": "calculation_depth",
                "actionable_tip": "After deciding on a move, pause and ask: 'If I play this, what's the BEST thing my opponent can do?'"
            }
    
    elif move_quality == "mistake":
        if time_spent < 3.0:
            coaching = {
                "type": "time_management",
                "severity": "medium",
                "icon": "clock",
                "message": f"You played {move_san} pretty fast ({time_spent:.0f}s). "
                           f"This position deserved more thought — there was a better move.",
                "habit": "impulse_move",
                "actionable_tip": "Try the 5-second rule: even if a move looks obvious, count to 5 before playing."
            }
        elif time_spent < 10.0:
            coaching = {
                "type": "calculation",
                "severity": "medium",
                "icon": "brain",
                "message": f"You spent {time_spent:.0f}s but there was a better option. "
                           f"Your instinct was off here — calculation would have found the right move.",
                "habit": "calculation_miss",
                "actionable_tip": "When you have 2-3 candidate moves, calculate each one at least 2 moves deep."
            }
        else:
            coaching = {
                "type": "calculation",
                "severity": "medium",
                "icon": "brain",
                "message": f"You thought for {time_spent:.0f}s but chose the wrong plan. "
                           f"The thinking time was good — now work on what to think ABOUT.",
                "habit": "calculation_direction",
                "actionable_tip": "Focus your calculation on the most forcing moves first: checks, captures, then quiet moves."
            }
    
    elif move_quality == "inaccuracy":
        if time_spent < 3.0:
            coaching = {
                "type": "time_management",
                "severity": "low",
                "icon": "clock",
                "message": f"{move_san} was okay but not the best — and you moved quite fast ({time_spent:.0f}s). "
                           f"A few more seconds of thought could have found the stronger option.",
                "habit": "impulse_move",
                "actionable_tip": "Small inaccuracies add up. Give each move at least 5 seconds of focused thought."
            }
    
    # ─── TILT DETECTION: String of fast bad moves (overrides above) ───
    if _detect_tilt(recent_player_moves):
        streak_count = _count_rapid_streak(recent_player_moves)
        coaching = {
            "type": "emotional",
            "severity": "high",
            "icon": "brain",
            "message": f"Hey — you've made {streak_count} fast moves in a row and the quality dropped. "
                       f"This looks like tilt. Take a deep breath before your next move.",
            "habit": "tilt",
            "actionable_tip": "When you blunder, sit on your hands for 10 seconds. Seriously. It works."
        }
    
    # ─── GOOD PATIENCE: Took time + Good move ───
    if not coaching and time_spent > 15.0 and move_quality in ("good", "best", "great"):
        coaching = {
            "type": "positive",
            "severity": "low",
            "icon": "star",
            "message": f"Great patience! You took {time_spent:.0f}s on {move_san} and it paid off. "
                       f"That's exactly how strong players think — slow is smooth, smooth is fast.",
            "habit": "positional_patience",
            "actionable_tip": None
        }
    
    # ─── OVERTHINKING: Took too long on a simple position ───
    if not coaching and time_spent > 45.0 and move_quality in ("good", "best"):
        coaching = {
            "type": "time_management",
            "severity": "low",
            "icon": "clock",
            "message": f"You spent {time_spent:.0f}s on {move_san} — it was the right move, but "
                       f"the position wasn't that complex. Trust your instincts more on straightforward positions.",
            "habit": "overthinking",
            "actionable_tip": "In simple positions, aim for 10-15 seconds. Save your time for critical moments."
        }
    
    # ─── REPEATED PATTERN: Same type of mistake again ───
    if not coaching and player_profile:
        recurring = player_profile.get("recurring_mistakes", [])
        for pattern in recurring:
            if pattern.get("count", 0) >= 3 and _matches_current_mistake(pattern, move_quality, move_san, move_history):
                coaching = {
                    "type": "pattern",
                    "severity": "medium",
                    "icon": "repeat",
                    "message": f"This is a pattern — you've made this type of mistake {pattern['count']} times. "
                               f"{pattern.get('description', 'Pay extra attention here.')}",
                    "habit": "recurring_mistake",
                    "actionable_tip": pattern.get("tip")
                }
                break
    
    return coaching


def _estimate_position_complexity(move_history: List[Dict], move_index: int) -> str:
    """Estimate if position is simple or complex based on game phase and piece count."""
    if move_index <= 10:
        return "opening"
    elif move_index <= 25:
        return "complex middlegame"
    else:
        return "endgame"


def _detect_tilt(recent_moves: List[Dict]) -> bool:
    """Detect tilt: 3+ fast moves where at least 2 are mistakes."""
    if len(recent_moves) < 3:
        return False
    
    last_3 = recent_moves[-3:]
    fast_count = sum(1 for m in last_3 if m.get("time_spent", 10) < 3.0)
    bad_count = sum(1 for m in last_3 if m.get("evaluation", "") in ("mistake", "blunder"))
    
    return fast_count >= 2 and bad_count >= 2


def _count_rapid_streak(recent_moves: List[Dict]) -> int:
    """Count consecutive fast moves from the end."""
    count = 0
    for m in reversed(recent_moves):
        if m.get("time_spent", 10) < 4.0:
            count += 1
        else:
            break
    return count


def _matches_current_mistake(pattern: Dict, move_quality: str, move_san: str, move_history: List[Dict]) -> bool:
    """Check if the current mistake matches a recurring pattern."""
    if move_quality not in ("mistake", "blunder"):
        return False
    
    pattern_type = pattern.get("type", "")
    
    # Knight fork blindness
    if pattern_type == "knight_fork" and move_san and move_san[0] != "N":
        return True  # Missed a knight tactic
    
    # Hanging pieces
    if pattern_type == "hanging_piece":
        return True
    
    return False


# ─── GAME HABITS ANALYSIS (Post-game / Lab) ────────────────────────

def analyze_game_habits(
    move_history: List[Dict],
    evaluations: List[Dict],
    behavior_events: List[Dict],
    user_color: str = "white"
) -> Dict:
    """
    Analyze habits across an entire game. Used by Lab decryption.
    Returns a comprehensive habits report.
    """
    player_moves = [m for m in move_history if m.get("by") == "player"]
    
    if not player_moves:
        return {"summary": "No moves to analyze"}
    
    # Time analysis
    times = [m.get("time_spent", 0) for m in player_moves if m.get("time_spent", 0) > 0]
    avg_time = sum(times) / len(times) if times else 0
    fast_moves = sum(1 for t in times if t < 3.0)
    slow_moves = sum(1 for t in times if t > 30.0)
    
    # Quality by phase
    opening_moves = player_moves[:10]
    middlegame_moves = player_moves[10:25] if len(player_moves) > 10 else []
    endgame_moves = player_moves[25:] if len(player_moves) > 25 else []
    
    opening_quality = _phase_accuracy(opening_moves, evaluations)
    middlegame_quality = _phase_accuracy(middlegame_moves, evaluations)
    endgame_quality = _phase_accuracy(endgame_moves, evaluations)
    
    # Behavior summary
    behavior_counts = {}
    for evt in behavior_events:
        bt = evt.get("behavior_type", "unknown")
        behavior_counts[bt] = behavior_counts.get(bt, 0) + 1
    
    # Time vs quality correlation
    time_quality_insights = _analyze_time_quality_correlation(player_moves, evaluations)
    
    # Build the report
    habits_report = {
        "time_management": {
            "avg_move_time": round(avg_time, 1),
            "fast_moves": fast_moves,
            "slow_moves": slow_moves,
            "total_moves": len(player_moves),
            "score": _time_management_score(avg_time, fast_moves, len(player_moves)),
            "insight": _time_management_insight(avg_time, fast_moves, slow_moves, len(player_moves))
        },
        "phase_performance": {
            "opening": {"accuracy": opening_quality, "moves": len(opening_moves)},
            "middlegame": {"accuracy": middlegame_quality, "moves": len(middlegame_moves)},
            "endgame": {"accuracy": endgame_quality, "moves": len(endgame_moves)},
            "weakest_phase": _weakest_phase(opening_quality, middlegame_quality, endgame_quality),
            "insight": _phase_insight(opening_quality, middlegame_quality, endgame_quality)
        },
        "behavior_patterns": {
            "counts": behavior_counts,
            "tilt_detected": behavior_counts.get("rapid_streak", 0) > 0,
            "impulse_moves": behavior_counts.get("impulse_move", 0),
            "patience_moments": behavior_counts.get("positional_patience", 0),
            "insight": _behavior_insight(behavior_counts)
        },
        "time_quality_correlation": time_quality_insights,
        "overall_habits_score": _overall_habits_score(
            _time_management_score(avg_time, fast_moves, len(player_moves)),
            opening_quality, middlegame_quality, endgame_quality,
            behavior_counts
        )
    }
    
    # Generate top 3 actionable recommendations
    habits_report["recommendations"] = _generate_recommendations(habits_report)
    
    return habits_report


def _phase_accuracy(phase_moves: List[Dict], evaluations: List[Dict]) -> float:
    """Calculate accuracy percentage for a game phase."""
    if not phase_moves:
        return 0.0
    
    # Match moves with evaluations
    good_count = 0
    total = 0
    
    for m in phase_moves:
        move_san = m.get("move", "")
        eval_quality = m.get("evaluation", "")
        
        # Also check evaluations list
        if not eval_quality:
            for ev in evaluations:
                if ev.get("move") == move_san:
                    eval_quality = ev.get("quality", "")
                    break
        
        if eval_quality in ("good", "best", "great", "book", "accurate"):
            good_count += 1
        total += 1
    
    return round((good_count / total) * 100, 1) if total > 0 else 0.0


def _time_management_score(avg_time: float, fast_moves: int, total: int) -> int:
    """Score 0-100 for time management."""
    if total == 0:
        return 50
    
    fast_ratio = fast_moves / total
    
    # Ideal avg time is 10-20s
    if 8 <= avg_time <= 25:
        time_score = 80
    elif 5 <= avg_time <= 35:
        time_score = 60
    else:
        time_score = 40
    
    # Penalize high fast-move ratio
    impulse_penalty = min(30, int(fast_ratio * 100))
    
    return max(10, min(100, time_score - impulse_penalty))


def _time_management_insight(avg_time: float, fast_moves: int, slow_moves: int, total: int) -> str:
    """Generate a human-readable time management insight."""
    if total == 0:
        return "Not enough data."
    
    fast_ratio = fast_moves / total
    
    if fast_ratio > 0.4:
        return f"You're playing too fast — {fast_moves}/{total} moves were under 3 seconds. Slow down on critical positions."
    elif fast_ratio > 0.2:
        return f"You sometimes rush ({fast_moves} fast moves). Be more deliberate in complex positions."
    elif slow_moves > total * 0.3:
        return f"You tend to overthink ({slow_moves} moves over 30s). Trust your calculation more."
    elif 8 <= avg_time <= 20:
        return "Good time management! You balance speed and thinking well."
    else:
        return f"Your average move time is {avg_time:.0f}s. Aim for 10-20s on average."


def _weakest_phase(opening: float, middlegame: float, endgame: float) -> str:
    """Find the weakest game phase."""
    phases = {"opening": opening, "middlegame": middlegame, "endgame": endgame}
    # Filter out phases with 0 (no moves played)
    active = {k: v for k, v in phases.items() if v > 0}
    if not active:
        return "unknown"
    return min(active, key=active.get)


def _phase_insight(opening: float, middlegame: float, endgame: float) -> str:
    """Generate insight about phase performance."""
    weakest = _weakest_phase(opening, middlegame, endgame)
    
    if weakest == "opening" and opening < 60:
        return f"Your opening play ({opening:.0f}% accuracy) needs work. Study your openings and memorize the key ideas."
    elif weakest == "middlegame" and middlegame < 60:
        return f"Middlegame ({middlegame:.0f}% accuracy) is your weakest phase. Practice tactical puzzles to improve."
    elif weakest == "endgame" and endgame < 60:
        return f"Endgame ({endgame:.0f}% accuracy) needs attention. Study basic endgame patterns."
    elif opening > 70 and middlegame > 70 and endgame > 70:
        return "Solid across all phases! Focus on reducing mistakes in your weakest area."
    else:
        return f"Opening: {opening:.0f}%, Middlegame: {middlegame:.0f}%, Endgame: {endgame:.0f}%."


def _behavior_insight(behavior_counts: Dict) -> str:
    """Generate insight from behavior patterns."""
    impulses = behavior_counts.get("impulse_move", 0)
    tilts = behavior_counts.get("rapid_streak", 0)
    patience = behavior_counts.get("positional_patience", 0)
    
    if tilts > 0:
        return "You went on tilt during this game — multiple fast mistakes in a row. Work on emotional control."
    elif impulses >= 3:
        return f"You made {impulses} impulse moves (fast + wrong). Discipline yourself to think before moving."
    elif patience >= 3:
        return f"Nice! You showed patience {patience} times — taking time on important decisions."
    else:
        return "No major behavioral patterns detected in this game."


def _analyze_time_quality_correlation(player_moves: List[Dict], evaluations: List[Dict]) -> Dict:
    """Analyze correlation between time spent and move quality."""
    fast_mistakes = 0  # < 5s and mistake/blunder
    fast_good = 0      # < 5s and good
    slow_mistakes = 0  # > 15s and mistake/blunder
    slow_good = 0      # > 15s and good
    
    for m in player_moves:
        time = m.get("time_spent", 0)
        quality = m.get("evaluation", "good")
        
        is_good = quality in ("good", "best", "great", "accurate")
        is_bad = quality in ("mistake", "blunder")
        
        if time < 5:
            if is_bad:
                fast_mistakes += 1
            elif is_good:
                fast_good += 1
        elif time > 15:
            if is_bad:
                slow_mistakes += 1
            elif is_good:
                slow_good += 1
    
    total = len(player_moves)
    
    insight = ""
    if fast_mistakes > 2:
        insight = f"You made {fast_mistakes} mistakes on moves where you spent < 5 seconds. Speed is costing you points."
    elif slow_good > fast_good and total > 10:
        insight = "Your best moves came when you took more time. Keep investing time in critical positions."
    elif fast_good > slow_good and total > 10:
        insight = "You play well on instinct too! But be careful — fast doesn't always mean accurate."
    
    return {
        "fast_mistakes": fast_mistakes,
        "fast_good": fast_good,
        "slow_mistakes": slow_mistakes,
        "slow_good": slow_good,
        "insight": insight
    }


def _overall_habits_score(time_score: int, opening: float, middlegame: float, endgame: float, behavior_counts: Dict) -> int:
    """Calculate overall habits score (0-100)."""
    # Average of time management and phase accuracy
    phase_avg = (opening + middlegame + endgame) / 3 if (opening + middlegame + endgame) > 0 else 50
    
    base = (time_score * 0.3 + phase_avg * 0.5 + 50 * 0.2)
    
    # Penalties for bad behaviors
    penalties = behavior_counts.get("impulse_move", 0) * 3 + behavior_counts.get("rapid_streak", 0) * 5
    # Bonuses for good behaviors
    bonuses = behavior_counts.get("positional_patience", 0) * 2 + behavior_counts.get("tactical_alertness", 0) * 2
    
    return max(10, min(100, int(base - penalties + bonuses)))


def _generate_recommendations(report: Dict) -> List[Dict]:
    """Generate top 3 actionable recommendations based on the habits report."""
    recs = []
    
    # Time management
    tm = report.get("time_management", {})
    if tm.get("score", 100) < 60:
        recs.append({
            "priority": 1,
            "area": "Time Management",
            "message": tm.get("insight", "Work on your time management."),
            "icon": "clock"
        })
    
    # Weakest phase
    pp = report.get("phase_performance", {})
    weakest = pp.get("weakest_phase", "")
    if weakest and pp.get(weakest, {}).get("accuracy", 100) < 60:
        recs.append({
            "priority": 2,
            "area": f"{weakest.title()} Play",
            "message": pp.get("insight", f"Focus on improving your {weakest}."),
            "icon": "target"
        })
    
    # Behavior
    bp = report.get("behavior_patterns", {})
    if bp.get("tilt_detected") or bp.get("impulse_moves", 0) >= 2:
        recs.append({
            "priority": 1,
            "area": "Emotional Control",
            "message": bp.get("insight", "Work on staying calm after mistakes."),
            "icon": "brain"
        })
    
    # Time-quality correlation
    tqc = report.get("time_quality_correlation", {})
    if tqc.get("fast_mistakes", 0) >= 2:
        recs.append({
            "priority": 2,
            "area": "Calculation",
            "message": tqc.get("insight", "Spend more time on complex positions."),
            "icon": "brain"
        })
    
    # Sort by priority, take top 3
    recs.sort(key=lambda x: x["priority"])
    return recs[:3]


# ─── PLAYER PROFILE (Aggregate across games) ───────────────────────

async def update_player_profile(db, user_id: str, game_habits: Dict):
    """Update the aggregate player profile with data from a completed game."""
    profile = await db.player_profiles.find_one({"user_id": user_id}, {"_id": 0})
    
    if not profile:
        profile = {
            "user_id": user_id,
            "games_analyzed": 0,
            "avg_time_management_score": 50,
            "avg_habits_score": 50,
            "phase_accuracy": {"opening": [], "middlegame": [], "endgame": []},
            "recurring_mistakes": [],
            "tilt_count": 0,
            "total_impulse_moves": 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    # Update with new game data
    profile["games_analyzed"] = profile.get("games_analyzed", 0) + 1
    
    # Rolling average of scores
    n = profile["games_analyzed"]
    old_tm = profile.get("avg_time_management_score", 50)
    new_tm = game_habits.get("time_management", {}).get("score", 50)
    profile["avg_time_management_score"] = round(((old_tm * (n - 1)) + new_tm) / n, 1)
    
    old_hs = profile.get("avg_habits_score", 50)
    new_hs = game_habits.get("overall_habits_score", 50)
    profile["avg_habits_score"] = round(((old_hs * (n - 1)) + new_hs) / n, 1)
    
    # Track phase accuracy (keep last 20 games)
    for phase in ["opening", "middlegame", "endgame"]:
        acc = game_habits.get("phase_performance", {}).get(phase, {}).get("accuracy", 0)
        if acc > 0:
            phase_list = profile.get("phase_accuracy", {}).get(phase, [])
            phase_list.append(acc)
            if len(phase_list) > 20:
                phase_list = phase_list[-20:]
            profile.setdefault("phase_accuracy", {})[phase] = phase_list
    
    # Track behaviors
    behaviors = game_habits.get("behavior_patterns", {}).get("counts", {})
    if behaviors.get("rapid_streak", 0) > 0:
        profile["tilt_count"] = profile.get("tilt_count", 0) + 1
    profile["total_impulse_moves"] = profile.get("total_impulse_moves", 0) + behaviors.get("impulse_move", 0)
    
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.player_profiles.update_one(
        {"user_id": user_id},
        {"$set": profile},
        upsert=True
    )
    
    return profile


async def get_player_profile(db, user_id: str) -> Optional[Dict]:
    """Get the aggregate player profile."""
    return await db.player_profiles.find_one({"user_id": user_id}, {"_id": 0})
