"""
Coach Action Service — "Diagnose → Drill → Track"
====================================================

Replaces the narrative Coach Review with an ACTION-ORIENTED format:

1. WHAT WENT WRONG — One line, the main issue (not a story)
2. FIX IT NOW — 3 practice positions from this exact mistake type  
3. BEFORE NEXT GAME — One rule to follow
4. YOUR TREND — Is this getting better or worse across games?
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ─── DIAGNOSIS → simple label + one line ─────────────────────────

DIAGNOSIS_LABELS = {
    "THROW": {"label": "Threw a winning game", "short": "You were winning and gave it away.", "fix_pattern": "winning_position_collapse"},
    "MATE_BLIND": {"label": "Missed a checkmate threat", "short": "You didn't see what your opponent was doing.", "fix_pattern": "checkmate_pattern"},
    "SLOW_BLEED": {"label": "Outplayed slowly", "short": "No big mistake, but small errors added up.", "fix_pattern": "positional"},
    "OPENING_COLLAPSE": {"label": "Lost in the opening", "short": "You got a bad position before the middlegame started.", "fix_pattern": "opening_principles"},
    "PIECE_GIVEAWAY": {"label": "Hung a piece", "short": "You left a piece undefended and lost it.", "fix_pattern": "hanging_piece"},
    "TACTICAL_MISS": {"label": "Missed a winning tactic", "short": "There was a strong move and you didn't see it.", "fix_pattern": "tactical_miss"},
    "TIME_COLLAPSE": {"label": "Ran out of time", "short": "You played well then rushed at the end.", "fix_pattern": "calculation_depth"},
    "WON_CLEAN": {"label": "Clean win", "short": "You played well. Nothing major to fix.", "fix_pattern": None},
    "WON_OPPONENT_BLUNDER": {"label": "Won on opponent's mistake", "short": "Your opponent blundered, not your best game.", "fix_pattern": "calculation_depth"},
    "DRAW": {"label": "Draw", "short": "Even game. Could you have pushed harder?", "fix_pattern": None},
}

RULES_BY_DIAGNOSIS = {
    "THROW": "When you're ahead, stay focused. Don't coast.",
    "MATE_BLIND": "Before every move: what is my opponent threatening?",
    "SLOW_BLEED": "Ask yourself: what's my plan for the next 3 moves?",
    "OPENING_COLLAPSE": "Learn the ONE main idea of your opening.",
    "PIECE_GIVEAWAY": "Before moving: is my piece safe where it's going?",
    "TACTICAL_MISS": "When it feels tense, slow down. Check captures and checks.",
    "TIME_COLLAPSE": "Use your time on the hard moves, not the first 5.",
    "WON_CLEAN": "Keep doing this. You played with a plan.",
    "WON_OPPONENT_BLUNDER": "Ask: would I have won if they played well?",
    "DRAW": "Before accepting a draw, did you try to win?",
}


async def generate_coach_action(
    db, game: Dict, analysis: Dict, user_id: str, user_color: str
) -> Dict:
    """
    Generate the action-oriented coach review.
    Returns: { diagnosis, drill_positions, rule, trend }
    """
    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    result = game.get("result", "")
    opening = game.get("opening_name") or game.get("opening") or ""

    # 1. DIAGNOSIS
    from services.game_coach_summary import compute_game_summary
    summary = compute_game_summary(evals, result, user_color, opening)
    diagnosis = summary.get("diagnosis", "UNKNOWN")

    diag_info = DIAGNOSIS_LABELS.get(diagnosis, {"label": "Game reviewed", "short": "Check the details.", "fix_pattern": None})

    # Find the worst moment for context
    user_is_white = user_color == "white"
    worst_move = None
    worst_cp = 0
    for i, m in enumerate(evals):
        is_user = (i % 2 == 0 and user_is_white) or (i % 2 == 1 and not user_is_white)
        if is_user and m.get("cp_loss", 0) > worst_cp:
            worst_cp = m.get("cp_loss", 0)
            worst_move = {
                "move_number": (i // 2) + 1,
                "move_san": m.get("move", m.get("san", "?")),
                "best_move": m.get("best_move", ""),
                "cp_loss": worst_cp,
                "fen_before": m.get("fen_before", ""),
                "move_uci": m.get("move_uci", ""),
                "best_move_uci": m.get("best_move_uci", ""),
            }

    # 2. DRILL POSITIONS — from this game + same pattern from other games
    fix_pattern = diag_info.get("fix_pattern")
    drill_positions = []

    if fix_pattern:
        # Get positions from THIS game's mistakes
        game_id = game.get("game_id", "")
        own_positions = await db.community_training_positions.find(
            {"source_game_id": game_id, "source_user_id": user_id},
            {"_id": 0}
        ).limit(3).to_list(3)

        # If not enough from this game, get same pattern from other games
        if len(own_positions) < 3:
            more = await db.community_training_positions.find(
                {"source_user_id": user_id, "pattern_type": fix_pattern, "source_game_id": {"$ne": game_id}},
                {"_id": 0}
            ).sort("created_at", -1).limit(3 - len(own_positions)).to_list(3)
            own_positions.extend(more)

        # If still not enough, get community positions
        if len(own_positions) < 3:
            community = await db.community_training_positions.find(
                {"pattern_type": fix_pattern, "source_user_id": {"$ne": user_id}},
                {"_id": 0}
            ).limit(3 - len(own_positions)).to_list(3)
            own_positions.extend(community)

        for p in own_positions:
            drill_positions.append({
                "position_id": p.get("position_id", ""),
                "fen": p.get("fen", ""),
                "best_move": p.get("best_move_san", p.get("best_move", "")),
                "best_move_uci": p.get("best_move_uci", ""),
                "pattern_type": p.get("pattern_type", ""),
                "source": "your_game" if p.get("source_user_id") == user_id else "community",
                "cp_loss": p.get("cp_loss", 0),
            })

    # 3. RULE — one sentence
    rule = RULES_BY_DIAGNOSIS.get(diagnosis, "Focus on one thing at a time.")

    # 4. TREND — how is this diagnosis trending across recent games?
    trend = await _compute_trend(db, user_id, diagnosis, user_color)

    # 5. ACCURACY
    accuracy = sf.get("accuracy")
    blunders = sf.get("blunders", 0)
    mistakes = sf.get("mistakes", 0)

    # 6. BRAIN — player's overall context
    from services.memory_brain import get_player_brain
    brain = await get_player_brain(db, user_id)

    return {
        "diagnosis": {
            "type": diagnosis,
            "label": diag_info["label"],
            "short": diag_info["short"],
            "worst_move": worst_move,
        },
        "drill": {
            "pattern": fix_pattern,
            "positions": drill_positions,
            "count": len(drill_positions),
        },
        "rule": rule,
        "trend": trend,
        "game_stats": {
            "accuracy": accuracy,
            "blunders": blunders,
            "mistakes": mistakes,
        },
        "brain": {
            "focus_message": brain.get("focus_message"),
            "top_weakness": brain.get("top_weakness"),
            "drill_focus": brain.get("drill_focus"),
            "rating": brain.get("rating"),
        },
    }


async def _compute_trend(db, user_id: str, current_diagnosis: str, user_color: str) -> Dict:
    """How is this problem trending? Getting better or worse?"""
    from services.game_coach_summary import compute_game_summary

    recent = []
    cursor = db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis": 1}
    ).sort("created_at", -1).limit(20)
    async for doc in cursor:
        recent.append(doc)

    if len(recent) < 3:
        return {
            "has_data": False,
            "message": "Play more games to see your trend.",
        }

    # Get game results for each analysis
    game_ids = [a["game_id"] for a in recent]
    games_map = {}
    for g in await db.games.find({"game_id": {"$in": game_ids}}, {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "opening": 1}).to_list(20):
        games_map[g["game_id"]] = g

    # Count diagnosis occurrences
    diagnosis_count = 0
    total = len(recent)
    recent_5_count = 0
    older_count = 0

    for i, a in enumerate(recent):
        evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        g = games_map.get(a["game_id"], {})
        uc = g.get("user_color", "white")
        result = g.get("result", "")
        opening = g.get("opening", "")

        if not evals:
            continue

        summary = compute_game_summary(evals, result, uc, opening)
        if summary.get("diagnosis") == current_diagnosis:
            diagnosis_count += 1
            if i < 5:
                recent_5_count += 1
            else:
                older_count += 1

    # Calculate rates
    recent_rate = recent_5_count / min(5, total)
    older_rate = older_count / max(1, total - 5) if total > 5 else 0

    if diagnosis_count == 0:
        return {
            "has_data": True,
            "occurrences": 0,
            "total_games": total,
            "direction": "none",
            "message": "This hasn't been a problem in your recent games.",
        }

    if recent_rate < older_rate * 0.5:
        direction = "improving"
        message = f"Getting better. This happened {recent_5_count} times in last 5 games, down from {older_count} in the {total - 5} before that."
    elif recent_rate > older_rate * 1.5 and older_rate > 0:
        direction = "worsening"
        message = f"This is happening more. {recent_5_count} times in last 5 games vs {older_count} before."
    else:
        direction = "stable"
        message = f"This happened {diagnosis_count} times in your last {total} games."

    return {
        "has_data": True,
        "occurrences": diagnosis_count,
        "total_games": total,
        "recent_5": recent_5_count,
        "direction": direction,
        "message": message,
    }
