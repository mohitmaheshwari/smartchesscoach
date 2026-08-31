"""
Rush-Test Drill — the drillable form of the `time_management` focus.

Board puzzles can't train clock discipline, so a time_management focus needs a
DIFFERENT drill: replay a position where the user rushed (moved in a couple of
seconds) and blundered, put a clock on it, and the test is whether — WITH the
time they didn't take — they can find the move they missed.

This trains the actual failure (rushing into a mistake), sourced from the user's
own games. It consumes signals the pipeline already stores on move_observations:
  - time_flag == "impulsive_critical"   (critical move played very fast)
  - time_spent_seconds                  (how long they actually took)
  - time_left_seconds, cp_loss, fen_before, move_san
The "right answer" (best move + idea) is joined from game_analyses.

Design: docs/daily_fix_scope.md (time_management drill type, 2026-06-29).
Pure shaping is separated from the DB query so it is unit-testable.
"""
from typing import Any, Dict, List, Optional

# A move played this fast at a critical moment is a "rush". The deriver already
# tags these as time_flag=="impulsive_critical"; this is the display threshold
# for the teaching line, not a re-detection.
RUSH_SECONDS = 3.0


def rush_teaching_line(time_spent_seconds: Optional[float], cp_loss: Optional[int]) -> str:
    """One plain-English line (600-1500 voice) framing the rush, no jargon.

    Leads with the behaviour (you moved fast), states the cost, and points at the
    fix (take the time). Deliberately does NOT name the move — the position is the
    lesson, not the notation."""
    secs = None
    try:
        secs = round(float(time_spent_seconds)) if time_spent_seconds is not None else None
    except (TypeError, ValueError):
        secs = None

    if secs is not None and secs <= 1:
        speed = "You moved here in about a second."
    elif secs is not None:
        speed = f"You spent only about {secs} seconds here."
    else:
        speed = "You moved here quickly."

    return f"{speed} Slow down — there's a better move if you take the time to look."


def shape_rush_drill_item(obs: Dict[str, Any], best: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Turn one impulsive_critical observation (+ its best-move data from the
    game analysis) into a drill item. Returns None if the position isn't usable
    (no FEN, or we can't name a correct answer to grade against)."""
    fen = obs.get("fen_before")
    if not fen:
        return None

    best = best or {}
    best_uci = best.get("best_move_uci") or best.get("best_move")
    if not best_uci:
        # No gradable correct answer → skip (never ship an ungradeable drill).
        return None

    game_id = obs.get("game_id")
    move_number = obs.get("move_number")
    if not game_id or move_number is None:
        return None

    return {
        "drill_type": "rush_test",
        "puzzle_id": f"{game_id}_m{move_number}",
        "fen": fen,
        "time_spent_seconds": obs.get("time_spent_seconds"),
        "time_left_seconds": obs.get("time_left_seconds"),
        "game_id": game_id,
        "move_number": move_number,
        "prompt": "You rushed here last time. Take your time — find the best move.",
        "teaching": rush_teaching_line(obs.get("time_spent_seconds"), obs.get("cp_loss")),
    }


async def build_rush_test_drill(db, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Build up to `limit` rush-test drill items from the user's own rushed
    blunders (most severe / most rushed first). Each item is timed on the client;
    passing = playing `solution_uci` (found the move they missed when they slowed
    down). Empty list if the user has no usable impulsive_critical positions."""
    cursor = db.move_observations.find(
        {"user_id": user_id, "time_flag": "impulsive_critical"},
    )
    # Prefer the costliest rushes; then the fastest ones.
    obs_list = await cursor.to_list(length=200)
    obs_list.sort(
        key=lambda o: (abs(o.get("cp_loss", 0) or 0), -float(o.get("time_spent_seconds", 99) or 99)),
        reverse=True,
    )

    items: List[Dict[str, Any]] = []
    seen_fens = set()
    for obs in obs_list:
        fen = obs.get("fen_before")
        if not fen or fen in seen_fens:
            continue
        best = await _best_move_for(
            db, user_id, obs.get("game_id"), obs.get("move_number")
        )
        item = shape_rush_drill_item(obs, best)
        if item:
            # The item is served only when the shared verifier can rebuild its
            # answer from this user's stored game + analysis.  The result is
            # deliberately not merged into the public row: it contains the
            # frozen answer and proof fields that must stay server-side.
            from services.verified_puzzle_runtime import resolve_verified_puzzle
            resolved = await resolve_verified_puzzle(
                db,
                item["puzzle_id"],
                user_id=user_id,
            )
            if not resolved:
                continue
            seen_fens.add(fen)
            items.append(item)
        if len(items) >= limit:
            break
    return items


async def _best_move_for(
    db,
    user_id: str,
    game_id: Optional[str],
    move_number: Optional[int],
) -> Optional[Dict[str, Any]]:
    """Find the engine best move for a given (game, move_number) from the stored
    analysis, so the drill has a gradable correct answer."""
    if not game_id or move_number is None:
        return None
    ga = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"stockfish_analysis.move_evaluations": 1},
    )
    if not ga:
        return None
    for me in (ga.get("stockfish_analysis", {}).get("move_evaluations", []) or []):
        if me.get("move_number") == move_number and not me.get("is_opponent_move"):
            return {"best_move": me.get("best_move"), "best_move_uci": me.get("best_move_uci")}
    return None
