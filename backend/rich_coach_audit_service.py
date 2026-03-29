"""
Rich Coach Audit Service

Creates a comprehensive, data-driven game audit from a coach's perspective.
Combines ALL available data about the user to provide deep, personalized insights.

Data Sources:
1. Game Analysis (Stockfish) - What happened tactically
2. Cognitive Gap History - User's thinking patterns from reflections
3. Pattern Recurrence - Recurring mistakes over time  
4. Skill Trends - How user is progressing
5. Historical Baseline - How this game compares to user's typical performance
6. Opening Repertoire - User's opening choices and success rates
7. Time Management - Clock usage patterns

Output: A rich, coach-like narrative with specific insights and a targeted plan.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# ============================================
# INSIGHT TEMPLATES (Coach Voice)
# ============================================

RECURRING_PATTERN_TEMPLATES = {
    "threat_blindness": {
        "detected": "You missed opponent threats again - this is the {count}th time this week.",
        "coach_note": "Before EVERY move, ask: 'What does my opponent want to do?'",
    },
    "calculation_depth": {
        "detected": "Calculation depth was an issue again - {count} times in recent games.",
        "coach_note": "Force yourself to calculate ONE move deeper before deciding.",
    },
    "hanging_piece_blindness": {
        "detected": "You left pieces hanging - this pattern has appeared {count} times recently.",
        "coach_note": "After choosing your move, do a final scan: 'Is everything defended?'",
    },
    "time_pressure": {
        "detected": "Time trouble struck again - you've had this issue {count} times lately.",
        "coach_note": "Set a rule: No move takes longer than 1 minute. Move faster in the opening.",
    },
    "advantage_collapse": {
        "detected": "You had an advantage but gave it back - this has happened {count} times.",
        "coach_note": "When ahead, simplify. Trade pieces, avoid complications.",
    },
    "tactical_oversight": {
        "detected": "You missed a tactic - this is the {count}th tactical oversight recently.",
        "coach_note": "Every move, check: Captures, Checks, Threats (CCT).",
    },
}

IMPROVEMENT_TEMPLATES = {
    "better_than_usual": "This was actually better than your average - {metric} improved by {improvement}%.",
    "first_time_clean": "First clean game in this area in a while - great discipline!",
    "streak_broken": "You broke a negative pattern - no {pattern} mistakes this game.",
    "new_high": "Personal best! Your {metric} was the best we've seen.",
}

CONCERN_TEMPLATES = {
    "worse_than_usual": "This was below your average - {metric} was {decline}% worse than usual.",
    "new_low": "This was concerning - your {metric} hit a new low.",
    "pattern_worsening": "The {pattern} pattern is getting worse - {this_week} vs {last_week} last week.",
}


async def generate_rich_coach_audit(
    db,
    user_id: str,
    game_id: str,
) -> Dict:
    """
    Generate a comprehensive, coach-like audit of the last game.
    
    Returns:
    {
        "game_summary": {...},          # Basic game info
        "performance_vs_baseline": {...}, # How this compares to typical
        "cognitive_insights": [...],    # Thinking pattern analysis
        "recurring_patterns": [...],    # What keeps happening
        "improvements": [...],          # What's getting better
        "concerns": [...],              # What needs attention
        "coach_narrative": "...",       # Human-readable summary
        "next_game_plan": {...},        # Specific plan for next game
    }
    """
    
    # Fetch all relevant data in parallel
    game = await db.games.find_one({"game_id": game_id, "user_id": user_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user_id}, {"_id": 0})
    
    if not game or not analysis:
        return {"error": "Game or analysis not found", "has_audit": False}
    
    # Get user's historical data
    recent_analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("analyzed_at", -1).limit(20).to_list(20)
    
    # Get cognitive gap history
    cognitive_gaps = await db.cognitive_gap_history.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    # Get gap aggregates
    gap_aggregates = await db.cognitive_gap_aggregates.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    # Get reflection data for this game
    game_reflections = await db.reflection_sessions.find(
        {"user_id": user_id, "game_id": game_id},
        {"_id": 0}
    ).to_list(20)
    
    # Build the audit
    audit = {
        "game_id": game_id,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "has_audit": True,
    }
    
    # 1. Game Summary
    audit["game_summary"] = build_game_summary(game, analysis)
    
    # 2. Performance vs Baseline
    audit["performance_vs_baseline"] = calculate_baseline_comparison(
        analysis, recent_analyses
    )
    
    # 3. Cognitive Insights (from reflections)
    audit["cognitive_insights"] = extract_cognitive_insights(
        game_reflections, cognitive_gaps, game_id
    )
    
    # 4. Recurring Patterns
    audit["recurring_patterns"] = identify_recurring_patterns(
        cognitive_gaps, gap_aggregates, analysis
    )
    
    # 5. Improvements & Concerns
    improvements, concerns = analyze_trends(
        analysis, recent_analyses, cognitive_gaps
    )
    audit["improvements"] = improvements
    audit["concerns"] = concerns
    
    # 6. Coach Narrative
    audit["coach_narrative"] = generate_coach_narrative(audit)
    
    # 7. Next Game Plan
    audit["next_game_plan"] = generate_targeted_plan(
        audit, gap_aggregates, analysis
    )
    
    return audit


def build_game_summary(game: Dict, analysis: Dict) -> Dict:
    """Build a comprehensive game summary."""
    
    sf = analysis.get("stockfish_analysis", {})
    moves = sf.get("move_evaluations", [])
    
    user_color = game.get("user_color", "white")
    result = game.get("result", "*")
    
    # Determine outcome
    if user_color == "white":
        outcome = "win" if result == "1-0" else "loss" if result == "0-1" else "draw"
    else:
        outcome = "win" if result == "0-1" else "loss" if result == "1-0" else "draw"
    
    # Count mistakes
    blunders = sum(1 for m in moves if m.get("evaluation") == "blunder")
    mistakes = sum(1 for m in moves if m.get("evaluation") == "mistake")
    inaccuracies = sum(1 for m in moves if m.get("evaluation") == "inaccuracy")
    
    # Find critical moments
    critical_moments = []
    for m in moves:
        if m.get("cp_loss", 0) >= 100:
            critical_moments.append({
                "move_number": m.get("move_number"),
                "move": m.get("move"),
                "best_move": m.get("best_move"),
                "cp_loss": m.get("cp_loss"),
                "fen": m.get("fen_before"),
                "evaluation": m.get("evaluation"),
            })
    
    # Find turning point (biggest eval swing)
    turning_point = None
    max_swing = 0
    for i, m in enumerate(moves):
        swing = abs(m.get("cp_loss", 0))
        if swing > max_swing:
            max_swing = swing
            turning_point = {
                "move_number": m.get("move_number"),
                "move": m.get("move"),
                "cp_loss": m.get("cp_loss"),
                "fen": m.get("fen_before"),
            }
    
    # Average centipawn loss
    cp_losses = [m.get("cp_loss", 0) for m in moves if m.get("cp_loss") is not None]
    avg_cp_loss = sum(cp_losses) / len(cp_losses) if cp_losses else 0
    
    # Opening info
    opening = game.get("opening_name", "Unknown opening")
    
    # Opponent
    if user_color == "white":
        opponent = game.get("black_player", "Opponent")
    else:
        opponent = game.get("white_player", "Opponent")
    
    return {
        "outcome": outcome,
        "user_color": user_color,
        "opponent": opponent,
        "opening": opening,
        "time_control": game.get("time_control", "Unknown"),
        "total_moves": len(moves),
        "blunders": blunders,
        "mistakes": mistakes,
        "inaccuracies": inaccuracies,
        "avg_cp_loss": round(avg_cp_loss, 1),
        "critical_moments": critical_moments[:5],  # Top 5
        "turning_point": turning_point,
        "played_at": game.get("played_at") or game.get("created_at"),
    }


def calculate_baseline_comparison(analysis: Dict, recent_analyses: List[Dict]) -> Dict:
    """Compare this game to user's typical performance."""
    
    if len(recent_analyses) < 3:
        return {"has_baseline": False, "reason": "Not enough games for comparison"}
    
    # Exclude current game from baseline
    baseline_analyses = [a for a in recent_analyses if a.get("game_id") != analysis.get("game_id")][:15]
    
    if len(baseline_analyses) < 3:
        return {"has_baseline": False, "reason": "Not enough historical data"}
    
    # Calculate baseline metrics
    def get_metrics(a):
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        cp_losses = [m.get("cp_loss", 0) for m in moves if m.get("cp_loss") is not None]
        return {
            "blunders": a.get("blunders", 0),
            "mistakes": a.get("mistakes", 0),
            "avg_cp_loss": sum(cp_losses) / len(cp_losses) if cp_losses else 0,
        }
    
    baseline_metrics = [get_metrics(a) for a in baseline_analyses]
    current_metrics = get_metrics(analysis)
    
    avg_blunders = sum(m["blunders"] for m in baseline_metrics) / len(baseline_metrics)
    avg_mistakes = sum(m["mistakes"] for m in baseline_metrics) / len(baseline_metrics)
    avg_cp_loss = sum(m["avg_cp_loss"] for m in baseline_metrics) / len(baseline_metrics)
    
    comparisons = []
    
    # Blunders comparison
    blunder_diff = current_metrics["blunders"] - avg_blunders
    if blunder_diff <= -1:
        comparisons.append({
            "metric": "blunders",
            "status": "better",
            "message": f"Fewer blunders than usual ({current_metrics['blunders']} vs avg {avg_blunders:.1f})",
            "change_pct": round((blunder_diff / max(avg_blunders, 1)) * 100, 0),
        })
    elif blunder_diff >= 1:
        comparisons.append({
            "metric": "blunders",
            "status": "worse",
            "message": f"More blunders than usual ({current_metrics['blunders']} vs avg {avg_blunders:.1f})",
            "change_pct": round((blunder_diff / max(avg_blunders, 1)) * 100, 0),
        })
    
    # CP loss comparison
    cp_diff_pct = ((current_metrics["avg_cp_loss"] - avg_cp_loss) / max(avg_cp_loss, 1)) * 100
    if cp_diff_pct <= -15:
        comparisons.append({
            "metric": "accuracy",
            "status": "better",
            "message": f"More accurate than usual ({current_metrics['avg_cp_loss']:.0f} cp vs avg {avg_cp_loss:.0f} cp)",
            "change_pct": round(cp_diff_pct, 0),
        })
    elif cp_diff_pct >= 15:
        comparisons.append({
            "metric": "accuracy",
            "status": "worse",
            "message": f"Less accurate than usual ({current_metrics['avg_cp_loss']:.0f} cp vs avg {avg_cp_loss:.0f} cp)",
            "change_pct": round(cp_diff_pct, 0),
        })
    
    return {
        "has_baseline": True,
        "baseline_games": len(baseline_analyses),
        "this_game": current_metrics,
        "baseline_avg": {
            "blunders": round(avg_blunders, 1),
            "mistakes": round(avg_mistakes, 1),
            "avg_cp_loss": round(avg_cp_loss, 1),
        },
        "comparisons": comparisons,
        "overall": "better" if len([c for c in comparisons if c["status"] == "better"]) > len([c for c in comparisons if c["status"] == "worse"]) else "worse" if len([c for c in comparisons if c["status"] == "worse"]) > 0 else "typical",
    }


def extract_cognitive_insights(
    game_reflections: List[Dict],
    all_gaps: List[Dict],
    game_id: str
) -> List[Dict]:
    """Extract insights about user's thinking patterns from reflections."""
    
    insights = []
    
    # Get gaps from this specific game
    game_gaps = [g for g in all_gaps if g.get("game_id") == game_id]
    
    if not game_gaps:
        return [{
            "type": "no_reflection",
            "message": "No reflection data for this game yet. Reflect on your critical moments to get thinking insights.",
        }]
    
    # Analyze gaps from this game
    gap_types = [g.get("gap_type") for g in game_gaps]
    gap_counts = defaultdict(int)
    for gt in gap_types:
        gap_counts[gt] += 1
    
    # Main cognitive gap in this game
    if gap_counts:
        main_gap = max(gap_counts.items(), key=lambda x: x[1])
        insights.append({
            "type": "main_gap",
            "gap_type": main_gap[0],
            "count": main_gap[1],
            "message": f"Your main thinking gap this game: {main_gap[0].replace('_', ' ').title()} ({main_gap[1]} instances)",
        })
    
    # Check confidence calibration
    high_conf_wrong = 0
    low_conf_right = 0
    for g in game_gaps:
        conf = g.get("user_confidence")
        severity = g.get("severity", "medium")
        if conf == "very_sure" and severity in ["critical", "high"]:
            high_conf_wrong += 1
        elif conf == "guessing" and severity == "low":
            low_conf_right += 1
    
    if high_conf_wrong >= 2:
        insights.append({
            "type": "overconfidence",
            "message": f"You were confident but wrong {high_conf_wrong} times. Ask yourself: 'What am I possibly missing?'",
        })
    
    if low_conf_right >= 2:
        insights.append({
            "type": "intuition_good",
            "message": f"Your 'guesses' were often good ({low_conf_right} times). Trust your intuition more!",
        })
    
    # Plans quality
    plans = [g.get("user_plan") for g in game_gaps if g.get("user_plan")]
    if plans:
        avg_plan_length = sum(len(p) for p in plans) / len(plans)
        if avg_plan_length < 20:
            insights.append({
                "type": "vague_plans",
                "message": "Your plans were quite brief. Try to articulate more specific intentions.",
            })
        elif avg_plan_length > 50:
            insights.append({
                "type": "detailed_plans",
                "message": "Good job articulating your plans - keep this level of detail.",
            })
    
    return insights


def identify_recurring_patterns(
    all_gaps: List[Dict],
    aggregates: Optional[Dict],
    analysis: Dict
) -> List[Dict]:
    """Identify patterns that keep recurring."""
    
    recurring = []
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    
    # Count gaps in last week
    recent_gaps = [g for g in all_gaps if g.get("created_at", "") >= week_ago.isoformat()]
    
    gap_counts = defaultdict(int)
    for g in recent_gaps:
        gap_counts[g.get("gap_type", "unknown")] += 1
    
    # Find recurring ones (3+ times in a week)
    for gap_type, count in gap_counts.items():
        if count >= 3:
            template = RECURRING_PATTERN_TEMPLATES.get(gap_type, {
                "detected": f"Pattern '{gap_type}' appeared {count} times this week.",
                "coach_note": "Focus on this area in your training.",
            })
            
            recurring.append({
                "pattern": gap_type,
                "pattern_name": gap_type.replace("_", " ").title(),
                "count_this_week": count,
                "message": template["detected"].format(count=count),
                "coach_advice": template["coach_note"],
                "severity": "high" if count >= 5 else "medium",
            })
    
    # Sort by count
    recurring.sort(key=lambda x: x["count_this_week"], reverse=True)
    
    return recurring[:5]  # Top 5 recurring patterns


def analyze_trends(
    current_analysis: Dict,
    recent_analyses: List[Dict],
    cognitive_gaps: List[Dict]
) -> Tuple[List[Dict], List[Dict]]:
    """Identify what's improving and what needs attention."""
    
    improvements = []
    concerns = []
    
    if len(recent_analyses) < 5:
        return improvements, concerns
    
    # Split analyses into two halves for trend
    mid = len(recent_analyses) // 2
    recent_half = recent_analyses[:mid]
    older_half = recent_analyses[mid:]
    
    # Calculate metrics for each half
    def calc_avg_metrics(analyses):
        if not analyses:
            return {"blunders": 0, "mistakes": 0, "cp_loss": 0}
        total_blunders = sum(a.get("blunders", 0) for a in analyses)
        total_mistakes = sum(a.get("mistakes", 0) for a in analyses)
        total_cp = 0
        cp_count = 0
        for a in analyses:
            sf = a.get("stockfish_analysis", {})
            moves = sf.get("move_evaluations", [])
            for m in moves:
                if m.get("cp_loss") is not None:
                    total_cp += m["cp_loss"]
                    cp_count += 1
        return {
            "blunders": total_blunders / len(analyses),
            "mistakes": total_mistakes / len(analyses),
            "cp_loss": total_cp / max(cp_count, 1),
        }
    
    recent_avg = calc_avg_metrics(recent_half)
    older_avg = calc_avg_metrics(older_half)
    
    # Blunder trend
    blunder_change = recent_avg["blunders"] - older_avg["blunders"]
    if blunder_change < -0.5:
        improvements.append({
            "metric": "Blunder Control",
            "message": "You're making fewer blunders recently - great progress!",
            "detail": f"{recent_avg['blunders']:.1f}/game vs {older_avg['blunders']:.1f}/game before",
        })
    elif blunder_change > 0.5:
        concerns.append({
            "metric": "Blunder Rate",
            "message": "Your blunder rate has increased recently.",
            "detail": f"{recent_avg['blunders']:.1f}/game vs {older_avg['blunders']:.1f}/game before",
        })
    
    # CP loss trend
    cp_change_pct = ((recent_avg["cp_loss"] - older_avg["cp_loss"]) / max(older_avg["cp_loss"], 1)) * 100
    if cp_change_pct < -15:
        improvements.append({
            "metric": "Accuracy",
            "message": "Your move accuracy is improving!",
            "detail": f"{abs(cp_change_pct):.0f}% better average centipawn loss",
        })
    elif cp_change_pct > 15:
        concerns.append({
            "metric": "Accuracy",
            "message": "Your move accuracy has declined.",
            "detail": f"{cp_change_pct:.0f}% worse average centipawn loss",
        })
    
    # Cognitive gap trends
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    
    this_week_gaps = [g for g in cognitive_gaps if g.get("created_at", "") >= week_ago.isoformat()]
    last_week_gaps = [g for g in cognitive_gaps if week_ago.isoformat() > g.get("created_at", "") >= two_weeks_ago.isoformat()]
    
    if len(this_week_gaps) < len(last_week_gaps) and len(last_week_gaps) >= 3:
        improvements.append({
            "metric": "Cognitive Gaps",
            "message": "Fewer thinking errors this week!",
            "detail": f"{len(this_week_gaps)} gaps vs {len(last_week_gaps)} last week",
        })
    elif len(this_week_gaps) > len(last_week_gaps) + 2:
        concerns.append({
            "metric": "Cognitive Gaps",
            "message": "More thinking errors this week.",
            "detail": f"{len(this_week_gaps)} gaps vs {len(last_week_gaps)} last week",
        })
    
    return improvements, concerns


def generate_coach_narrative(audit: Dict) -> str:
    """Generate a human-readable coach narrative."""
    
    summary = audit.get("game_summary", {})
    baseline = audit.get("performance_vs_baseline", {})
    recurring = audit.get("recurring_patterns", [])
    improvements = audit.get("improvements", [])
    concerns = audit.get("concerns", [])
    cognitive = audit.get("cognitive_insights", [])
    
    parts = []
    
    # Opening
    outcome = summary.get("outcome", "game")
    opponent = summary.get("opponent", "opponent")
    if outcome == "win":
        parts.append(f"Good result against {opponent}.")
    elif outcome == "loss":
        parts.append(f"Tough game against {opponent}, but every loss is data.")
    else:
        parts.append(f"Solid draw against {opponent}.")
    
    # Baseline comparison
    if baseline.get("has_baseline"):
        overall = baseline.get("overall", "typical")
        if overall == "better":
            parts.append("This was actually better than your usual play.")
        elif overall == "worse":
            parts.append("This was below your typical performance.")
    
    # Recurring patterns (most important)
    if recurring:
        top_pattern = recurring[0]
        parts.append(f"Watch out: {top_pattern['message']}")
    
    # Improvements
    if improvements:
        imp = improvements[0]
        parts.append(f"Good news: {imp['message']}")
    
    # Concerns
    if concerns:
        conc = concerns[0]
        parts.append(f"Area to work on: {conc['message']}")
    
    # Cognitive insight
    for ci in cognitive:
        if ci.get("type") == "overconfidence":
            parts.append(ci["message"])
            break
    
    return " ".join(parts)


def generate_targeted_plan(
    audit: Dict,
    aggregates: Optional[Dict],
    analysis: Dict
) -> Dict:
    """Generate a specific plan for the next game based on audit findings."""
    
    plan = {
        "plan_id": f"plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "focus_areas": [],
        "before_each_move": [],
        "situational_rules": [],
    }
    
    recurring = audit.get("recurring_patterns", [])
    concerns = audit.get("concerns", [])
    cognitive = audit.get("cognitive_insights", [])
    summary = audit.get("game_summary", {})
    
    # Primary focus: Most recurring pattern
    if recurring:
        top = recurring[0]
        plan["primary_focus"] = {
            "area": top["pattern_name"],
            "reason": f"This has appeared {top['count_this_week']} times this week",
            "action": top["coach_advice"],
        }
        plan["before_each_move"].append(top["coach_advice"])
    
    # Secondary focus: From concerns
    if concerns:
        for concern in concerns[:2]:
            plan["focus_areas"].append({
                "area": concern["metric"],
                "reason": concern["detail"],
            })
    
    # From cognitive insights
    for ci in cognitive:
        if ci.get("type") == "main_gap":
            gap = ci.get("gap_type", "")
            if gap == "threat_blindness":
                plan["before_each_move"].append("Ask: What does my opponent want?")
            elif gap == "calculation_depth":
                plan["before_each_move"].append("Calculate one move deeper.")
            elif gap == "hanging_piece_blindness":
                plan["before_each_move"].append("Final check: Is everything defended?")
    
    # Game-specific situational rules
    if summary.get("blunders", 0) >= 2:
        plan["situational_rules"].append({
            "situation": "When you feel confident about a move",
            "action": "Pause 10 seconds and ask: What am I missing?",
        })
    
    turning_point = summary.get("turning_point")
    if turning_point and turning_point.get("cp_loss", 0) >= 200:
        move_num = turning_point.get("move_number", 0)
        if move_num <= 15:
            plan["situational_rules"].append({
                "situation": "In the opening (moves 1-15)",
                "action": "Slow down. Don't rush piece development.",
            })
        elif move_num <= 30:
            plan["situational_rules"].append({
                "situation": "In the middlegame",
                "action": "Check for tactics before every move (CCT: Checks, Captures, Threats).",
            })
        else:
            plan["situational_rules"].append({
                "situation": "In the endgame",
                "action": "King activity! Centralize your king immediately.",
            })
    
    # Ensure we have at least 2 before-move checklist items
    default_checks = [
        "Checks, Captures, Threats (CCT)",
        "Is my opponent's last move a threat?",
        "Are all my pieces safe?",
    ]
    while len(plan["before_each_move"]) < 2:
        for check in default_checks:
            if check not in plan["before_each_move"]:
                plan["before_each_move"].append(check)
                break
        else:
            break
    
    return plan
