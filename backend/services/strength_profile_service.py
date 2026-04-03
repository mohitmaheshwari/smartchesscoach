"""
Strength Profile Service
========================

Tracks what the user is GOOD at, not just what they're bad at.

Computes per-domain strength scores from positive move data:
- Tactical vision: brilliant moves, sacrifices found, only-move discoveries
- Calculation depth: how deep the user calculates (PV length of best moves)
- Positional sense: excellent moves in quiet positions
- Endgame technique: accuracy in endgame phase
- Opening knowledge: accuracy in the first 15 moves

Each domain produces a strength score (0-100) and a "strength rating"
that estimates what rating band this skill corresponds to.

Data source: game_analyses collection (move_evaluations per game)
Output: player_strength_profiles collection
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Phase boundaries (by move number)
OPENING_END = 15
ENDGAME_START_PIECES = 10  # If total pieces <= this, it's endgame

# Piece values for material counting
PIECE_COUNTS_FROM_FEN = True

# Rating band estimates based on strength percentiles
# These map a 0-100 strength score to an approximate rating
STRENGTH_TO_RATING = [
    (90, 1800),
    (75, 1500),
    (60, 1300),
    (45, 1100),
    (30, 900),
    (0, 600),
]


def _score_to_rating(score: float) -> int:
    """Convert a 0-100 strength score to an estimated rating."""
    for threshold, rating in STRENGTH_TO_RATING:
        if score >= threshold:
            return rating
    return 600


def _count_pieces_from_fen(fen: str) -> int:
    """Count total pieces (not pawns, not kings) from FEN."""
    if not fen:
        return 32
    board_part = fen.split(" ")[0]
    count = 0
    for ch in board_part:
        if ch in "rnbqRNBQ":
            count += 1
    return count


def _count_all_pieces_from_fen(fen: str) -> int:
    """Count all pieces and pawns from FEN."""
    if not fen:
        return 32
    board_part = fen.split(" ")[0]
    count = 0
    for ch in board_part:
        if ch.isalpha() and ch not in "kK":
            count += 1
    return count


def _get_phase(move_number: int, fen: str) -> str:
    """Determine game phase from move number and piece count."""
    if move_number <= OPENING_END:
        return "opening"
    pieces = _count_all_pieces_from_fen(fen)
    if pieces <= ENDGAME_START_PIECES:
        return "endgame"
    return "middlegame"


def compute_strength_profile(move_evaluations: List[Dict], game_result: str = "", user_color: str = "white") -> Dict:
    """
    Compute a strength profile from a single game's move evaluations.

    Returns per-domain stats that can be aggregated across games.
    """
    stats = {
        "total_moves": 0,
        "brilliant_moves": 0,
        "sacrifices": 0,
        "best_moves": 0,
        "excellent_moves": 0,
        "good_moves": 0,
        # Phase accuracy
        "opening_moves": 0,
        "opening_good_or_better": 0,
        "middlegame_moves": 0,
        "middlegame_good_or_better": 0,
        "endgame_moves": 0,
        "endgame_good_or_better": 0,
        # Tactical indicators
        "only_move_found": 0,  # Moves where all alternatives are 150+ cp worse
        "tactical_best_moves": 0,  # Best moves in tactical (high-eval-swing) positions
        "quiet_best_moves": 0,  # Best moves in quiet positions (positional sense)
        # Calculation indicators
        "complex_best_moves": 0,  # Best moves where PV is 4+ moves deep
        "mate_found": 0,  # Found forced mate sequences
        # Pressure handling
        "best_moves_when_losing": 0,  # Best/excellent when eval < -100
        "best_moves_when_winning": 0,  # Best/excellent when eval > 100
        "best_moves_when_equal": 0,  # Best/excellent when eval between -100 and 100
        "moves_when_losing": 0,
        "moves_when_winning": 0,
        "moves_when_equal": 0,
    }

    for m in move_evaluations:
        evaluation = m.get("evaluation", "")
        cp_loss = m.get("cp_loss", 0)
        eval_before = m.get("eval_before", 0)
        move_number = m.get("move_number", 0)
        fen_before = m.get("fen_before", "")
        eval_swing = m.get("eval_swing", 0)
        is_brilliant = m.get("is_brilliant", False)
        is_sacrifice = m.get("is_sacrifice", False)
        pv_after_played = m.get("pv_after_played") or []
        mate_after = m.get("mate_info", {})

        stats["total_moves"] += 1

        if is_brilliant:
            stats["brilliant_moves"] += 1
        if is_sacrifice:
            stats["sacrifices"] += 1

        is_good_or_better = evaluation in ("brilliant", "best", "excellent", "good")
        is_best_or_excellent = evaluation in ("brilliant", "best", "excellent")

        if evaluation == "best" or evaluation == "brilliant":
            stats["best_moves"] += 1
        elif evaluation == "excellent":
            stats["excellent_moves"] += 1
        elif evaluation == "good":
            stats["good_moves"] += 1

        # Phase tracking
        phase = _get_phase(move_number, fen_before)
        if phase == "opening":
            stats["opening_moves"] += 1
            if is_good_or_better:
                stats["opening_good_or_better"] += 1
        elif phase == "middlegame":
            stats["middlegame_moves"] += 1
            if is_good_or_better:
                stats["middlegame_good_or_better"] += 1
        elif phase == "endgame":
            stats["endgame_moves"] += 1
            if is_good_or_better:
                stats["endgame_good_or_better"] += 1

        # Tactical vs positional
        is_tactical = eval_swing >= 100 or cp_loss >= 100
        if is_best_or_excellent:
            if is_tactical:
                stats["tactical_best_moves"] += 1
            else:
                stats["quiet_best_moves"] += 1

        # Calculation depth (PV length of good moves)
        if is_best_or_excellent and len(pv_after_played) >= 4:
            stats["complex_best_moves"] += 1

        # Mate detection
        if mate_after and mate_after.get("after") is not None:
            mate_in = mate_after.get("after")
            if mate_in is not None and mate_in > 0 and user_color == "white":
                stats["mate_found"] += 1
            elif mate_in is not None and mate_in < 0 and user_color == "black":
                stats["mate_found"] += 1

        # Pressure handling
        if eval_before < -100:
            stats["moves_when_losing"] += 1
            if is_best_or_excellent:
                stats["best_moves_when_losing"] += 1
        elif eval_before > 100:
            stats["moves_when_winning"] += 1
            if is_best_or_excellent:
                stats["best_moves_when_winning"] += 1
        else:
            stats["moves_when_equal"] += 1
            if is_best_or_excellent:
                stats["best_moves_when_equal"] += 1

    return stats


def aggregate_strength_scores(game_stats_list: List[Dict]) -> Dict:
    """
    Aggregate per-game strength stats into domain scores (0-100).

    Takes a list of per-game stats (from compute_strength_profile)
    and produces the final strength profile.
    """
    if not game_stats_list:
        return _empty_profile()

    # Sum all stats across games
    totals = {}
    for stats in game_stats_list:
        for key, val in stats.items():
            totals[key] = totals.get(key, 0) + val

    total_moves = totals.get("total_moves", 1) or 1
    games_count = len(game_stats_list)

    # ── TACTICAL VISION (0-100) ──
    # Based on: brilliant moves, sacrifices, tactical best moves
    brilliant_rate = totals.get("brilliant_moves", 0) / games_count
    sacrifice_success = totals.get("sacrifices", 0) / games_count
    tactical_accuracy = (totals.get("tactical_best_moves", 0) / max(1, totals.get("tactical_best_moves", 0) + 1)) * 100
    mate_rate = totals.get("mate_found", 0) / games_count

    tactical_score = min(100, (
        brilliant_rate * 30 +        # Each brilliant per game = 30 points
        sacrifice_success * 15 +     # Each sacrifice per game = 15 points
        tactical_accuracy * 0.3 +    # Tactical accuracy contributes 30%
        mate_rate * 10               # Mates found = 10 per game
    ))

    # ── CALCULATION DEPTH (0-100) ──
    # Based on: complex best moves, best moves in losing positions
    complex_rate = (totals.get("complex_best_moves", 0) / total_moves) * 100
    defense_rate = _safe_pct(totals.get("best_moves_when_losing", 0), totals.get("moves_when_losing", 0))

    calculation_score = min(100, (
        complex_rate * 2.5 +         # Complex positions solved
        defense_rate * 0.4 +         # Finding best moves under pressure
        mate_rate * 15               # Finding mates requires deep calc
    ))

    # ── POSITIONAL SENSE (0-100) ──
    # Based on: quiet best moves, middlegame accuracy
    quiet_rate = (totals.get("quiet_best_moves", 0) / total_moves) * 100
    mg_accuracy = _safe_pct(totals.get("middlegame_good_or_better", 0), totals.get("middlegame_moves", 0))

    positional_score = min(100, (
        quiet_rate * 2.0 +           # Quiet position accuracy
        mg_accuracy * 0.5            # Overall middlegame quality
    ))

    # ── ENDGAME TECHNIQUE (0-100) ──
    endgame_accuracy = _safe_pct(totals.get("endgame_good_or_better", 0), totals.get("endgame_moves", 0))
    eg_moves = totals.get("endgame_moves", 0)

    endgame_score = endgame_accuracy if eg_moves >= 10 else endgame_accuracy * 0.5

    # ── OPENING KNOWLEDGE (0-100) ──
    opening_accuracy = _safe_pct(totals.get("opening_good_or_better", 0), totals.get("opening_moves", 0))

    opening_score = opening_accuracy

    # ── PRESSURE HANDLING (0-100) ──
    winning_accuracy = _safe_pct(totals.get("best_moves_when_winning", 0), totals.get("moves_when_winning", 0))
    losing_accuracy = _safe_pct(totals.get("best_moves_when_losing", 0), totals.get("moves_when_losing", 0))
    equal_accuracy = _safe_pct(totals.get("best_moves_when_equal", 0), totals.get("moves_when_equal", 0))

    # Pressure score: bonus for staying strong when losing, penalty for collapsing when winning
    pressure_score = min(100, (
        losing_accuracy * 0.5 +       # 50% weight on defense under pressure
        equal_accuracy * 0.3 +        # 30% weight on equal play
        winning_accuracy * 0.2        # 20% weight on converting advantages
    ))

    # ── BUILD PROFILE ──
    domains = {
        "tactical_vision": {
            "score": round(tactical_score, 1),
            "rating": _score_to_rating(tactical_score),
            "evidence": {
                "brilliant_moves": totals.get("brilliant_moves", 0),
                "sacrifices": totals.get("sacrifices", 0),
                "tactical_best_moves": totals.get("tactical_best_moves", 0),
                "mates_found": totals.get("mate_found", 0),
            },
            "label": _get_strength_label(tactical_score),
        },
        "calculation_depth": {
            "score": round(calculation_score, 1),
            "rating": _score_to_rating(calculation_score),
            "evidence": {
                "complex_best_moves": totals.get("complex_best_moves", 0),
                "best_when_losing": totals.get("best_moves_when_losing", 0),
                "mates_found": totals.get("mate_found", 0),
            },
            "label": _get_strength_label(calculation_score),
        },
        "positional_sense": {
            "score": round(positional_score, 1),
            "rating": _score_to_rating(positional_score),
            "evidence": {
                "quiet_best_moves": totals.get("quiet_best_moves", 0),
                "middlegame_accuracy": round(mg_accuracy, 1),
            },
            "label": _get_strength_label(positional_score),
        },
        "endgame_technique": {
            "score": round(endgame_score, 1),
            "rating": _score_to_rating(endgame_score),
            "evidence": {
                "endgame_accuracy": round(endgame_accuracy, 1),
                "endgame_moves_analyzed": eg_moves,
            },
            "label": _get_strength_label(endgame_score),
        },
        "opening_knowledge": {
            "score": round(opening_score, 1),
            "rating": _score_to_rating(opening_score),
            "evidence": {
                "opening_accuracy": round(opening_accuracy, 1),
                "opening_moves_analyzed": totals.get("opening_moves", 0),
            },
            "label": _get_strength_label(opening_score),
        },
        "pressure_handling": {
            "score": round(pressure_score, 1),
            "rating": _score_to_rating(pressure_score),
            "evidence": {
                "accuracy_when_losing": round(losing_accuracy, 1),
                "accuracy_when_winning": round(winning_accuracy, 1),
                "accuracy_when_equal": round(equal_accuracy, 1),
            },
            "label": _get_strength_label(pressure_score),
        },
    }

    # Find strongest and weakest domains
    sorted_domains = sorted(domains.items(), key=lambda x: x[1]["score"], reverse=True)
    strongest = sorted_domains[0][0]
    weakest = sorted_domains[-1][0]

    # Overall strength score (weighted average)
    overall = (
        tactical_score * 0.25 +
        calculation_score * 0.20 +
        positional_score * 0.20 +
        endgame_score * 0.15 +
        opening_score * 0.10 +
        pressure_score * 0.10
    )

    return {
        "overall_score": round(overall, 1),
        "overall_rating": _score_to_rating(overall),
        "overall_label": _get_strength_label(overall),
        "domains": domains,
        "strongest": strongest,
        "weakest": weakest,
        "games_analyzed": games_count,
        "total_moves_analyzed": total_moves,
        "headline_stats": {
            "brilliant_moves": totals.get("brilliant_moves", 0),
            "sacrifices": totals.get("sacrifices", 0),
            "best_move_rate": round((totals.get("best_moves", 0) + totals.get("excellent_moves", 0)) / total_moves * 100, 1),
            "mates_found": totals.get("mate_found", 0),
        },
    }


def _safe_pct(numerator: int, denominator: int) -> float:
    """Safe percentage calculation."""
    if denominator <= 0:
        return 0.0
    return (numerator / denominator) * 100


def _get_strength_label(score: float) -> str:
    """Human-readable label for a strength score."""
    if score >= 85:
        return "exceptional"
    elif score >= 70:
        return "strong"
    elif score >= 50:
        return "solid"
    elif score >= 30:
        return "developing"
    else:
        return "emerging"


def _empty_profile() -> Dict:
    """Return an empty strength profile."""
    return {
        "overall_score": 0,
        "overall_rating": 600,
        "overall_label": "emerging",
        "domains": {},
        "strongest": None,
        "weakest": None,
        "games_analyzed": 0,
        "total_moves_analyzed": 0,
        "headline_stats": {
            "brilliant_moves": 0,
            "sacrifices": 0,
            "best_move_rate": 0,
            "mates_found": 0,
        },
    }


async def build_strength_profile_for_user(db, user_id: str, max_games: int = 30) -> Dict:
    """
    Build a complete strength profile for a user from their recent analyzed games.

    Reads move_evaluations from game_analyses and computes domain scores.
    Saves the result to player_strength_profiles collection.
    """
    # Get recent game analyses
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {
            "_id": 0,
            "game_id": 1,
            "stockfish_analysis.move_evaluations": 1,
        }
    ).sort("analyzed_at", -1).limit(max_games).to_list(max_games)

    if not analyses:
        return _empty_profile()

    # Also get game results and user color
    game_ids = [a["game_id"] for a in analyses]
    games = await db.games.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1}
    ).to_list(max_games)
    game_map = {g["game_id"]: g for g in games}

    # Compute per-game stats
    game_stats_list = []
    for a in analyses:
        move_evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        if not move_evals:
            continue

        game_info = game_map.get(a["game_id"], {})
        game_result = game_info.get("result", "")
        user_color = game_info.get("user_color", "white")

        stats = compute_strength_profile(move_evals, game_result, user_color)
        game_stats_list.append(stats)

    # Aggregate across all games
    profile = aggregate_strength_scores(game_stats_list)
    profile["user_id"] = user_id
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Save to DB
    await db.player_strength_profiles.update_one(
        {"user_id": user_id},
        {"$set": profile},
        upsert=True
    )

    logger.info(
        f"Strength profile for {user_id}: "
        f"overall={profile['overall_score']}, "
        f"strongest={profile['strongest']}, "
        f"weakest={profile['weakest']}, "
        f"brilliant={profile['headline_stats']['brilliant_moves']}"
    )

    return profile


def build_strength_profile_sync(db, user_id: str, max_games: int = 30) -> Dict:
    """
    Synchronous version for the analysis worker.
    """
    analyses = list(db.game_analyses.find(
        {"user_id": user_id},
        {
            "_id": 0,
            "game_id": 1,
            "stockfish_analysis.move_evaluations": 1,
        }
    ).sort("analyzed_at", -1).limit(max_games))

    if not analyses:
        return _empty_profile()

    game_ids = [a["game_id"] for a in analyses]
    games = list(db.games.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1}
    ))
    game_map = {g["game_id"]: g for g in games}

    game_stats_list = []
    for a in analyses:
        move_evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        if not move_evals:
            continue

        game_info = game_map.get(a["game_id"], {})
        game_result = game_info.get("result", "")
        user_color = game_info.get("user_color", "white")

        stats = compute_strength_profile(move_evals, game_result, user_color)
        game_stats_list.append(stats)

    profile = aggregate_strength_scores(game_stats_list)
    profile["user_id"] = user_id
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()

    db.player_strength_profiles.update_one(
        {"user_id": user_id},
        {"$set": profile},
        upsert=True
    )

    logger.info(
        f"Strength profile (sync) for {user_id}: "
        f"overall={profile['overall_score']}, "
        f"strongest={profile['strongest']}, "
        f"weakest={profile['weakest']}"
    )

    return profile
