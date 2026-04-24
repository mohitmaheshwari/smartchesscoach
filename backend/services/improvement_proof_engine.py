"""
Proof of Improvement Engine
============================

Turns raw game analysis data into CLEAR, VISUAL, EMOTIONAL proof
that the player is improving.

NOT analytics. NOT dashboards.
"3 weeks ago you hung your queen here → yesterday you defended correctly."

Uses existing services:
- pattern_decay_service → pattern states (active/declining/fading)
- root_behavior_engine → 5 behavioral clusters
- thinking_score → 5 habit dimensions with trends
- game_analyses → per-move data with cognitive_gap, cp_loss, fen_before
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ─── ROOT PATTERN MAPPING ────────────────────────────────────────
# Map raw cognitive_gap types into 4 root patterns

ROOT_PATTERNS = {
    "threat_awareness": {
        "label": "Threat Awareness",
        "description": "Seeing what your opponent is doing",
        "gaps": ["ignore_threat", "ignored_threat", "hung_pieces", "hanging_piece",
                 "piece_safety", "king_safety", "missed_capture"],
    },
    "calculation": {
        "label": "Calculation",
        "description": "Thinking ahead before moving",
        "gaps": ["calculation_depth", "tactical_miss", "tactical_oversight",
                 "one_move_blunder", "blunder", "complex_tactical_miss"],
    },
    "coordination": {
        "label": "Piece Coordination",
        "description": "Making your pieces work together",
        "gaps": ["loose_pieces", "weak_development", "disconnected_pieces",
                 "premature_attack", "piece_activity"],
    },
    "endgame": {
        "label": "Endgame Play",
        "description": "Converting advantages and finishing games",
        "gaps": ["endgame_collapse", "endgame_technique", "threw_winning",
                 "conversion", "missed_win"],
    },
}

# Reverse map: gap → root pattern
GAP_TO_ROOT = {}
for root_key, root_data in ROOT_PATTERNS.items():
    for gap in root_data["gaps"]:
        GAP_TO_ROOT[gap] = root_key


def _classify_gap(gap: str) -> str:
    """Map a cognitive_gap to its root pattern."""
    return GAP_TO_ROOT.get(gap, GAP_TO_ROOT.get(gap.lower(), "calculation"))


# ─── CORE ENGINE ─────────────────────────────────────────────────

async def compute_improvement_proof(db, user_id: str) -> Dict:
    """
    Main entry point. Returns the complete improvement proof for a user.
    """
    # Get all analyzed games with move evaluations
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "imported_at": 1, "result": 1, "user_color": 1}
    ).sort("imported_at", -1).to_list(50)

    if len(games) < 6:
        return {"has_data": False, "reason": "Need at least 6 analyzed games."}

    game_ids = [g["game_id"] for g in games]
    game_dates = {g["game_id"]: g.get("imported_at") for g in games}

    # Get analyses
    analyses = {}
    async for a in db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1,
         "stockfish_analysis.accuracy": 1, "stockfish_analysis.blunders": 1}
    ):
        analyses[a["game_id"]] = a

    # Split into recent (last 10) and older (previous 10)
    recent_ids = game_ids[:10]
    older_ids = game_ids[10:20]

    if not older_ids:
        older_ids = game_ids[5:10]
        recent_ids = game_ids[:5]

    # ─── 1. COUNT PATTERNS PER ROOT ───
    recent_counts = _count_patterns(recent_ids, analyses)
    older_counts = _count_patterns(older_ids, analyses)

    # Minimum events before we'll claim improvement. Going from 3 mistakes
    # to 2 across 10 games is -33% on paper but well within random noise.
    # Requiring ≥5 events in the baseline window cuts out the small-sample
    # false positives. Tunable as more data comes in.
    MIN_BASELINE_EVENTS = 5

    # ─── 2. FIND PRIMARY IMPROVING PATTERN ───
    improvements = []
    for root_key, root_data in ROOT_PATTERNS.items():
        old_count = older_counts.get(root_key, 0)
        new_count = recent_counts.get(root_key, 0)
        old_per_game = old_count / len(older_ids) if older_ids else 0
        new_per_game = new_count / len(recent_ids) if recent_ids else 0

        # Gate: only compute a reduction % when the baseline has enough
        # events to make the ratio meaningful. Otherwise tag as "stable"
        # (no claim) instead of reporting a noisy percentage.
        if old_count < MIN_BASELINE_EVENTS:
            reduction_pct = 0
            trend = "insufficient_data"
        elif old_per_game > 0:
            reduction_pct = round((1 - new_per_game / old_per_game) * 100)
            trend = "improving" if reduction_pct >= 20 else "worsening" if reduction_pct <= -20 else "stable"
        elif new_per_game == 0:
            reduction_pct = 0
            trend = "stable"
        else:
            reduction_pct = -100
            trend = "worsening"

        improvements.append({
            "pattern": root_key,
            "label": root_data["label"],
            "description": root_data["description"],
            "old_count": old_count,
            "new_count": new_count,
            "old_per_game": round(old_per_game, 1),
            "new_per_game": round(new_per_game, 1),
            "reduction_pct": reduction_pct,
            "trend": trend,
        })

    # Sort by improvement magnitude (biggest improvement first)
    improvements.sort(key=lambda x: -x["reduction_pct"])

    # Primary = most improved pattern
    primary = improvements[0] if improvements and improvements[0]["reduction_pct"] > 0 else None

    # ─── 3. BEFORE vs AFTER MOMENTS ───
    before_after = []
    if primary:
        before_after = _find_before_after_moments(
            primary["pattern"], recent_ids, older_ids, analyses, games, game_dates
        )

    # ─── 4. STREAKS ───
    streaks = _compute_streaks(game_ids, analyses)

    # ─── 5. OVERALL ACCURACY TREND ───
    recent_acc = []
    older_acc = []
    for gid in recent_ids:
        a = analyses.get(gid, {})
        acc = a.get("stockfish_analysis", {}).get("accuracy")
        if acc is not None:
            recent_acc.append(acc)
    for gid in older_ids:
        a = analyses.get(gid, {})
        acc = a.get("stockfish_analysis", {}).get("accuracy")
        if acc is not None:
            older_acc.append(acc)

    avg_recent = round(sum(recent_acc) / len(recent_acc), 1) if recent_acc else 0
    avg_older = round(sum(older_acc) / len(older_acc), 1) if older_acc else 0

    return {
        "has_data": True,
        "primary_pattern": primary,
        "all_patterns": improvements,
        "before_after": before_after[:2],
        "streaks": streaks,
        "accuracy": {
            "recent": avg_recent,
            "older": avg_older,
            "delta": round(avg_recent - avg_older, 1),
        },
        "games_analyzed": len(game_ids),
        "recent_window": len(recent_ids),
        "older_window": len(older_ids),
    }


def _count_patterns(game_ids: List[str], analyses: Dict) -> Dict[str, int]:
    """
    Count root pattern occurrences across a set of games.
    Uses cognitive_gap when available, but ALSO infers from move context:
    - threat field populated + high cp_loss → threat_awareness
    - high cp_loss with no threat → calculation
    - eval was winning then collapsed → endgame (if late) or coordination (if mid)
    """
    counts = {}
    for gid in game_ids:
        a = analyses.get(gid, {})
        evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])

        for ev in evals:
            cp = ev.get("cp_loss", 0) or 0
            if cp < 100:
                continue  # Only count real mistakes

            gap = ev.get("cognitive_gap", "")
            move_num = ev.get("move_number", 0) or 0
            has_threat = bool(ev.get("threat"))

            # Classify into root pattern — ORDER MATTERS
            # 1. Threat present + big loss = missed threat (most specific)
            # 2. Endgame phase = endgame issue
            # 3. Opening phase = coordination issue
            # 4. Cognitive gap or default = calculation
            if has_threat and cp >= 150:
                root = "threat_awareness"
            elif move_num > 30:
                root = "endgame"
            elif move_num <= 10 and cp >= 150:
                root = "coordination"
            elif cp >= 300:
                root = "calculation"
            elif gap:
                root = _classify_gap(gap)
            else:
                root = "calculation"

            counts[root] = counts.get(root, 0) + 1
    return counts


def _find_before_after_moments(
    pattern_key: str,
    recent_ids: List[str],
    older_ids: List[str],
    analyses: Dict,
    games: List[Dict],
    game_dates: Dict,
) -> List[Dict]:
    """
    Find REAL board positions where:
    - Old game: user made a mistake matching this pattern
    - New game: user handled a similar situation correctly

    Returns [{old_fen, new_fen, old_game_id, new_game_id, old_move, new_move, message}]
    """
    # Collect OLD mistakes (high cp_loss, matching root pattern by inference)
    old_mistakes = []
    for gid in older_ids:
        a = analyses.get(gid, {})
        evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        for ev in evals:
            cp = ev.get("cp_loss", 0) or 0
            fen = ev.get("fen_before", "")
            if cp < 150 or not fen:
                continue

            # Classify this mistake — same logic as _count_patterns
            gap = ev.get("cognitive_gap", "")
            has_threat = bool(ev.get("threat"))
            move_num = ev.get("move_number", 0) or 0

            if has_threat and cp >= 150:
                root = "threat_awareness"
            elif move_num > 30:
                root = "endgame"
            elif move_num <= 10 and cp >= 150:
                root = "coordination"
            elif cp >= 300:
                root = "calculation"
            elif gap:
                root = _classify_gap(gap)
            else:
                root = "calculation"

            if root == pattern_key:
                old_mistakes.append({
                    "game_id": gid,
                    "fen": fen,
                    "move": ev.get("move", ""),
                    "move_number": move_num,
                    "cp_loss": cp,
                    "gap": gap or root,
                    "phase": _move_phase(move_num),
                    "date": game_dates.get(gid),
                })

    if not old_mistakes:
        return []

    # Collect NEW good moves (low cp_loss, same phase, same gap type existed but was handled)
    new_successes = []
    for gid in recent_ids:
        a = analyses.get(gid, {})
        evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        for ev in evals:
            cp = ev.get("cp_loss", 0) or 0
            fen = ev.get("fen_before", "")
            move_num = ev.get("move_number", 0)
            phase = _move_phase(move_num)

            # Good move: low cp_loss in a similar phase
            if cp <= 20 and fen and move_num > 5:
                new_successes.append({
                    "game_id": gid,
                    "fen": fen,
                    "move": ev.get("move", ""),
                    "move_number": move_num,
                    "cp_loss": cp,
                    "phase": phase,
                    "date": game_dates.get(gid),
                })

    if not new_successes:
        return []

    # Match: same phase, worst old mistake → best new success
    results = []
    used_old = set()
    used_new = set()

    # Sort old by worst first
    old_mistakes.sort(key=lambda m: -m["cp_loss"])

    for old in old_mistakes:
        if old["game_id"] in used_old:
            continue

        # Find a matching new success in the same phase
        best_new = None
        for new in new_successes:
            if new["game_id"] in used_new:
                continue
            if new["phase"] == old["phase"]:
                best_new = new
                break

        if not best_new:
            # Try any phase
            for new in new_successes:
                if new["game_id"] not in used_new:
                    best_new = new
                    break

        if best_new:
            # Build the message
            old_date_str = _format_relative_date(old["date"])
            gap_label = old["gap"].replace("_", " ")

            message = f"{old_date_str}, you lost material here ({gap_label}). Recently, you played this type of position cleanly."

            results.append({
                "old_fen": old["fen"],
                "old_game_id": old["game_id"],
                "old_move": old["move"],
                "old_move_number": old["move_number"],
                "old_cp_loss": old["cp_loss"],
                "new_fen": best_new["fen"],
                "new_game_id": best_new["game_id"],
                "new_move": best_new["move"],
                "new_move_number": best_new["move_number"],
                "message": message,
                "phase": old["phase"],
            })
            used_old.add(old["game_id"])
            used_new.add(best_new["game_id"])

        if len(results) >= 3:
            break

    return results


def _compute_streaks(game_ids: List[str], analyses: Dict) -> Dict:
    """Compute current clean streaks."""
    # No-blunder streak
    no_blunder_streak = 0
    for gid in game_ids:
        a = analyses.get(gid, {})
        blunders = a.get("stockfish_analysis", {}).get("blunders", 0)
        if blunders == 0:
            no_blunder_streak += 1
        else:
            break

    # No-big-mistake streak (no move with cp_loss >= 300 = blunder-level)
    no_big_mistake_streak = 0
    for gid in game_ids:
        a = analyses.get(gid, {})
        evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        has_big = any((ev.get("cp_loss", 0) or 0) >= 300 for ev in evals)
        if not has_big:
            no_big_mistake_streak += 1
        else:
            break

    # No-threat-miss streak (no move where threat existed + high cp_loss)
    no_threat_miss_streak = 0
    for gid in game_ids:
        a = analyses.get(gid, {})
        evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        missed_threat = any(
            ev.get("threat") and (ev.get("cp_loss", 0) or 0) >= 150
            for ev in evals
        )
        if not missed_threat:
            no_threat_miss_streak += 1
        else:
            break

    return {
        "no_blunder_games": no_blunder_streak,
        "no_big_mistake_games": no_big_mistake_streak,
        "no_threat_miss_games": no_threat_miss_streak,
    }


def _move_phase(move_number: int) -> str:
    if move_number <= 12:
        return "opening"
    elif move_number <= 30:
        return "middlegame"
    return "endgame"


def _format_relative_date(date_val) -> str:
    """Format a date as relative time ('3 weeks ago', 'last month')."""
    if not date_val:
        return "Earlier"
    try:
        if isinstance(date_val, str):
            date_val = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - date_val
        days = delta.days
        if days <= 1:
            return "Yesterday"
        elif days <= 7:
            return f"{days} days ago"
        elif days <= 14:
            return "Last week"
        elif days <= 30:
            weeks = days // 7
            return f"{weeks} weeks ago"
        elif days <= 60:
            return "Last month"
        else:
            months = days // 30
            return f"{months} months ago"
    except Exception:
        return "Earlier"
