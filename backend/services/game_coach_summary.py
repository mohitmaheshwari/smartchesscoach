"""
Game Coach Summary Service
===========================

Deterministic game diagnosis — no LLM, no storytelling.
Three outputs:

1. SUMMARY: One brutal truth about WHY you lost/won
2. HABITS:  Pass/fail checklist of behavioral patterns
3. MEMORY:  Identity snapshot + impact projection

Everything is derived from Stockfish eval + existing analysis data.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import chess

logger = logging.getLogger(__name__)


# ─── GAME DIAGNOSIS TYPES ────────────────────────────────────────

class GameDiagnosis:
    THROW = "THROW"                    # Was winning, threw it away
    MATE_BLIND = "MATE_BLIND"          # Missed checkmate threat
    SLOW_BLEED = "SLOW_BLEED"          # Gradual outplay, no single blunder
    OPENING_COLLAPSE = "OPENING_COLLAPSE"  # Lost in the opening
    PIECE_GIVEAWAY = "PIECE_GIVEAWAY"  # Hung a piece
    TACTICAL_MISS = "TACTICAL_MISS"    # Missed a winning tactic
    TIME_COLLAPSE = "TIME_COLLAPSE"    # Blunders clustered at end (time trouble)
    WON_CLEAN = "WON_CLEAN"           # Won without major mistakes
    WON_OPPONENT_BLUNDER = "WON_OPPONENT_BLUNDER"  # Won because opponent blundered
    DRAW = "DRAW"                      # Draw


# ─── SUMMARY COMPUTATION ─────────────────────────────────────────

def compute_game_summary(
    move_evaluations: List[Dict],
    game_result: str,
    user_color: str,
    opening_name: str = ""
) -> Dict:
    """
    Compute the ONE reason this game was lost/won/drawn.
    Returns: { diagnosis, root_cause, critical_move, context[], coach_note }
    """
    if not move_evaluations:
        return {"diagnosis": "UNKNOWN", "root_cause": "No move data available"}

    user_is_white = user_color == "white"
    user_won = (game_result == "1-0" and user_is_white) or (game_result == "0-1" and not user_is_white)
    is_draw = "1/2" in game_result

    # Extract user moves with eval data
    user_moves = []
    for i, m in enumerate(move_evaluations):
        is_user_move = (i % 2 == 0 and user_is_white) or (i % 2 == 1 and not user_is_white)
        if is_user_move:
            user_moves.append({
                "index": i,
                "move_number": (i // 2) + 1,
                "san": m.get("san", m.get("move", "?")),
                "cp_loss": m.get("cp_loss", 0),
                "eval_before": m.get("eval_before", 0),
                "eval_after": m.get("eval_after", 0),
                "best_move": m.get("best_move", ""),
                "phase": _get_phase(i),
            })

    if not user_moves:
        return {"diagnosis": "UNKNOWN", "root_cause": "No user moves found"}

    # Find critical moment (biggest swing)
    worst_move = max(user_moves, key=lambda m: m["cp_loss"])
    biggest_cp_loss = worst_move["cp_loss"]

    # Count blunders, mistakes
    blunders = [m for m in user_moves if m["cp_loss"] >= 200]
    mistakes = [m for m in user_moves if 100 <= m["cp_loss"] < 200]
    total_cp_loss = sum(m["cp_loss"] for m in user_moves)

    # Eval curve analysis
    max_advantage = max((m["eval_before"] for m in user_moves), default=0)
    was_winning = max_advantage >= 300  # Was +3 or better at some point

    # ─── DRAW ────────────
    if is_draw:
        return _build_summary(
            GameDiagnosis.DRAW,
            "Game ended in a draw.",
            worst_move if biggest_cp_loss > 100 else None,
            _draw_context(user_moves, max_advantage),
            "Draws happen. Was there a moment you could have pushed for more?"
        )

    # ─── USER WON ────────
    if user_won:
        opponent_moves = []
        for i, m in enumerate(move_evaluations):
            is_opp = (i % 2 == 1 and user_is_white) or (i % 2 == 0 and not user_is_white)
            if is_opp:
                opponent_moves.append(m)

        opp_blunders = [m for m in opponent_moves if m.get("cp_loss", 0) >= 200]

        if len(blunders) == 0:
            return _build_summary(
                GameDiagnosis.WON_CLEAN,
                "Solid game. You played accurately and your opponent couldn't handle it.",
                None,
                _win_context(user_moves, total_cp_loss, len(opp_blunders)),
                "Clean wins build confidence. Keep this level up."
            )
        else:
            return _build_summary(
                GameDiagnosis.WON_OPPONENT_BLUNDER,
                f"You won, but you had {len(blunders)} blunder{'s' if len(blunders) > 1 else ''} yourself. Your opponent's mistakes were bigger.",
                worst_move,
                _win_context(user_moves, total_cp_loss, len(opp_blunders)),
                "A win is a win, but those blunders will cost you against stronger opponents."
            )

    # ─── USER LOST ───────

    # Check for mate blindness (cp_loss > 5000 = missed mate)
    mate_blunders = [m for m in user_moves if m["cp_loss"] >= 5000]
    if mate_blunders:
        mate_move = mate_blunders[0]
        was_winning_before = mate_move["eval_before"] >= 300
        return _build_summary(
            GameDiagnosis.MATE_BLIND,
            "You missed a checkmate threat and lost immediately." +
            (f" You were completely winning (+{mate_move['eval_before'] / 100:.1f}) before this." if was_winning_before else ""),
            mate_move,
            [
                f"You were {'+' + str(round(mate_move['eval_before']/100, 1)) if mate_move['eval_before'] >= 0 else str(round(mate_move['eval_before']/100, 1))} before the blunder",
                f"Move {mate_move['move_number']}: {mate_move['san']} allowed forced checkmate",
                f"{mate_move['best_move']} would have kept you alive" if mate_move["best_move"] else "There was a defense available",
                "One moment of inattention cost the entire game",
            ],
            "This is not a skill issue. This is a habit issue: not checking opponent threats before moving."
        )

    # Check for THROW (was winning, then blundered)
    if was_winning and biggest_cp_loss >= 200:
        # Find the throw moment - first big blunder after being ahead
        throw_move = None
        for m in user_moves:
            if m["eval_before"] >= 200 and m["cp_loss"] >= 200:
                throw_move = m
                break
        if throw_move is None:
            throw_move = worst_move

        return _build_summary(
            GameDiagnosis.THROW,
            f"You threw a winning game. You were +{max_advantage / 100:.1f} and gave it away.",
            throw_move,
            [
                f"Peak advantage: +{max_advantage / 100:.1f}",
                "Position was stable — no pressure from opponent",
                f"Move {throw_move['move_number']}: {throw_move['san']} lost {throw_move['cp_loss'] / 100:.1f} pawns worth of advantage",
                "You didn't lose over many mistakes — you lost in one moment",
            ],
            "Winning positions need the same focus as losing ones. Check threats every single move."
        )

    # Check for opening collapse
    opening_blunders = [m for m in user_moves if m["phase"] == "opening" and m["cp_loss"] >= 100]
    if opening_blunders and blunders and blunders[0]["phase"] == "opening":
        return _build_summary(
            GameDiagnosis.OPENING_COLLAPSE,
            f"You lost this in the opening. {opening_name + ' went wrong.' if opening_name else 'The opening preparation failed.'}",
            opening_blunders[0],
            [
                f"Lost {sum(m['cp_loss'] for m in opening_blunders)} centipawns in the opening alone",
                f"Move {opening_blunders[0]['move_number']}: {opening_blunders[0]['san']} was the first critical error",
                "You were already struggling before the middlegame started",
            ],
            "This opening needs study. Know the key ideas, not just the moves."
        )

    # Check for piece giveaway
    piece_giveaways = [m for m in user_moves if 200 <= m["cp_loss"] < 5000]
    if piece_giveaways and len(blunders) <= 2:
        giveaway = piece_giveaways[0]
        return _build_summary(
            GameDiagnosis.PIECE_GIVEAWAY,
            f"You gave away material. Move {giveaway['move_number']}: {giveaway['san']} lost a piece.",
            giveaway,
            [
                f"Lost {giveaway['cp_loss'] / 100:.1f} pawns of material",
                f"{giveaway['best_move']} was the safe option" if giveaway["best_move"] else "A safer move was available",
                f"{'The position was equal before this' if abs(giveaway['eval_before']) < 100 else 'You were already under pressure'}",
            ],
            "Before every move: is my piece still defended after I move? Check the basics."
        )

    # Check for time collapse (blunders in last 25% of game)
    total_user_moves = len(user_moves)
    late_blunders = [m for m in blunders if m["move_number"] > total_user_moves * 0.75]
    if len(late_blunders) >= 2:
        return _build_summary(
            GameDiagnosis.TIME_COLLAPSE,
            "You collapsed under time pressure. Blunders clustered in the last phase.",
            worst_move,
            [
                f"{len(late_blunders)} blunders in the last {total_user_moves - int(total_user_moves * 0.75)} moves",
                "Earlier play was decent — you ran out of time/energy, not ideas",
                "Time management is a skill, not luck",
            ],
            "Use your time earlier. The clock is as important as the position."
        )

    # SLOW BLEED - no single catastrophic error
    if biggest_cp_loss < 200:
        return _build_summary(
            GameDiagnosis.SLOW_BLEED,
            "No single blunder. You were outplayed — small inaccuracies added up.",
            worst_move if biggest_cp_loss > 50 else None,
            [
                f"Total centipawn loss: {total_cp_loss}",
                f"Worst move lost only {biggest_cp_loss} centipawns",
                f"{len(mistakes)} small inaccuracies across the game",
                "Your opponent simply made fewer mistakes",
            ],
            "This is the hardest loss type to learn from. Focus on understanding the plans, not just the moves."
        )

    # Default: tactical miss / general loss
    return _build_summary(
        GameDiagnosis.TACTICAL_MISS,
        f"You missed a critical tactic at move {worst_move['move_number']}.",
        worst_move,
        [
            f"Move {worst_move['move_number']}: {worst_move['san']} lost {worst_move['cp_loss'] / 100:.1f} pawns",
            f"{worst_move['best_move']} was the right move" if worst_move["best_move"] else "A better move existed",
            "The position required calculation, and the calculation failed",
        ],
        "Tactics come from calculation. Slow down on critical moves."
    )


# ─── HABITS COMPUTATION ──────────────────────────────────────────

def compute_game_habits(
    move_evaluations: List[Dict],
    user_color: str,
    habits_report: Optional[Dict] = None,
    game_summary: Optional[Dict] = None
) -> Dict:
    """
    Compute pass/fail checklist for behavioral habits.
    Returns: { habits: [{ name, passed, evidence, impact }], focus_habit }
    """
    user_is_white = user_color == "white"

    user_moves = []
    for i, m in enumerate(move_evaluations):
        is_user = (i % 2 == 0 and user_is_white) or (i % 2 == 1 and not user_is_white)
        if is_user:
            user_moves.append({
                "index": i,
                "move_number": (i // 2) + 1,
                "san": m.get("san", m.get("move", "?")),
                "cp_loss": m.get("cp_loss", 0),
                "eval_before": m.get("eval_before", 0),
                "eval_after": m.get("eval_after", 0),
                "best_move": m.get("best_move", ""),
                "phase": _get_phase(i),
                "time_spent": m.get("time_spent", 0),
            })

    habits = []

    # 1. Checked opponent threats (mate-level blunders = missed threats)
    missed_mate = any(m["cp_loss"] >= 5000 for m in user_moves)
    # For threat checking, only count blunders that aren't just general inaccuracy
    missed_tactics = [m for m in user_moves if m["cp_loss"] >= 200]
    habits.append({
        "name": "Checked opponent threats before moving",
        "passed": not missed_mate and len(missed_tactics) == 0,
        "evidence": "Missed mate in 1" if missed_mate else
                    f"Missed {len(missed_tactics)} tactical threat{'s' if len(missed_tactics) > 1 else ''}" if missed_tactics else
                    "No threats missed",
        "impact": "Game lost immediately" if missed_mate else
                  f"Lost {sum(m['cp_loss'] for m in missed_tactics)} centipawns" if missed_tactics else
                  None,
    })

    # 2. Followed opening theory (threshold: 100cp = real mistake, not just inaccuracy)
    opening_moves = [m for m in user_moves if m["phase"] == "opening"]
    opening_blunders = [m for m in opening_moves if m["cp_loss"] >= 100]
    habits.append({
        "name": "Followed opening principles",
        "passed": len(opening_blunders) == 0,
        "evidence": f"{len(opening_blunders)} opening mistake{'s' if len(opening_blunders) > 1 else ''}" if opening_blunders else
                    "Clean opening play",
        "impact": f"Lost {sum(m['cp_loss'] for m in opening_blunders)} centipawns in opening" if opening_blunders else None,
    })

    # 3. No hanging pieces (exclude mate-level blunders — those are threat misses, not hung pieces)
    hanging = [m for m in user_moves if 250 <= m["cp_loss"] < 5000 and m["phase"] != "opening"]
    habits.append({
        "name": "Avoided hanging pieces",
        "passed": len(hanging) == 0,
        "evidence": f"Hung material {len(hanging)} time{'s' if len(hanging) > 1 else ''}" if hanging else
                    "No pieces left hanging",
        "impact": f"Lost {sum(m['cp_loss'] for m in hanging)} centipawns from hanging material" if hanging else None,
    })

    # 4. Played with a plan (consecutive moves with cp_loss >= 50 = truly aimless)
    # Exclude mate-level blunders — a single catastrophic miss isn't "aimlessness"
    aimless_count = 0
    for j in range(1, len(user_moves)):
        cp_j = user_moves[j]["cp_loss"] if user_moves[j]["cp_loss"] < 5000 else 0
        cp_prev = user_moves[j-1]["cp_loss"] if user_moves[j-1]["cp_loss"] < 5000 else 0
        if cp_j >= 50 and cp_prev >= 50:
            aimless_count += 1
    habits.append({
        "name": "Played with a plan",
        "passed": aimless_count <= 2,
        "evidence": f"{aimless_count} stretches of inaccurate play" if aimless_count > 2 else
                    "Moves showed consistent direction",
        "impact": "Multiple inaccuracies suggest no clear plan" if aimless_count > 2 else None,
    })

    # 5. Maintained focus in critical moments (exclude mate blunders — already in #1)
    critical_moments = [m for m in user_moves if abs(m["eval_before"]) >= 200]
    critical_blunders = [m for m in critical_moments if 100 <= m["cp_loss"] < 5000]
    habits.append({
        "name": "Maintained focus in critical moments",
        "passed": len(critical_blunders) <= 1,
        "evidence": f"Blundered in {len(critical_blunders)} critical position{'s' if len(critical_blunders) > 1 else ''}" if len(critical_blunders) > 1 else
                    "1 slip in a critical position" if len(critical_blunders) == 1 else
                    "Handled pressure well",
        "impact": "Converted advantage to loss" if any(m["eval_before"] >= 200 and m["cp_loss"] >= 200 for m in critical_blunders) else
                  "Lost concentration when it mattered" if len(critical_blunders) > 1 else None,
    })

    # 6. Endgame technique (if game reached endgame)
    endgame_moves = [m for m in user_moves if m["phase"] == "endgame"]
    if endgame_moves:
        eg_blunders = [m for m in endgame_moves if m["cp_loss"] >= 100]
        habits.append({
            "name": "Endgame technique",
            "passed": len(eg_blunders) == 0,
            "evidence": f"{len(eg_blunders)} endgame error{'s' if len(eg_blunders) > 1 else ''}" if eg_blunders else
                        "Clean endgame play",
            "impact": f"Endgame errors cost {sum(m['cp_loss'] for m in eg_blunders)} centipawns" if eg_blunders else None,
        })

    # Determine FOCUS HABIT — the one that cost the game
    failed_habits = [h for h in habits if not h["passed"]]
    focus_habit = None
    if failed_habits:
        # Priority: threats > hanging > critical moments > opening > plan > endgame
        priority_order = [
            "Checked opponent threats before moving",
            "Avoided hanging pieces",
            "Maintained focus in critical moments",
            "Followed opening principles",
            "Played with a plan",
            "Endgame technique",
        ]
        for name in priority_order:
            focus = next((h for h in failed_habits if h["name"] == name), None)
            if focus:
                focus_habit = focus
                break
        if not focus_habit:
            focus_habit = failed_habits[0]

    return {
        "habits": habits,
        "focus_habit": focus_habit,
        "passed_count": len([h for h in habits if h["passed"]]),
        "total_count": len(habits),
    }


# ─── MEMORY COMPUTATION (Identity + Impact) ──────────────────────

async def compute_game_memory(
    db,
    user_id: str,
    game_summary: Dict,
    user_rating: int = 0,
) -> Dict:
    """
    Memory = Identity Snapshot + Impact Projection.
    
    Identity: Who you are as a player, how this game confirms/changes that.
    Impact: What fixing your #1 weakness would do to your rating.
    """

    # Pull player identity data
    identity_doc = await db.player_identity.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )

    # Pull recent game analysis for pattern counting
    recent_analyses = []
    cursor = db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "stockfish_analysis": 1, "game_id": 1, "habits_report": 1}
    ).sort("created_at", -1).limit(30)
    async for doc in cursor:
        recent_analyses.append(doc)

    # Count pattern occurrences across recent games
    diagnosis_type = game_summary.get("diagnosis", "UNKNOWN")
    pattern_counts = _count_patterns(recent_analyses, diagnosis_type)
    total_games = len(recent_analyses) or 1

    # ─── YOUR CHESS DNA ─────────────────────────────────
    # "Before this game" + "After this game" narrative
    style = "developing"
    weakest_area = "general play"
    strength = "determination"

    if identity_doc:
        style = identity_doc.get("play_style", identity_doc.get("style_profile", {}).get("primary_style", "developing"))
        # Find weakest area from blunder taxonomy
        taxonomy = identity_doc.get("blunder_taxonomy", {})
        if isinstance(taxonomy, dict):
            by_type = taxonomy.get("by_type", taxonomy)
            if by_type and isinstance(by_type, dict):
                worst_type = max(by_type.items(), key=lambda x: x[1], default=("general", 0))
                weakest_area = _readable_blunder_type(worst_type[0])

        # Find strength
        strengths = identity_doc.get("strengths", [])
        if strengths:
            strength = strengths[0] if isinstance(strengths[0], str) else strengths[0].get("name", "consistency")

    # Build "before/after this game" identity lines
    before_line, after_line, archetype = _build_chess_dna(
        diagnosis_type, pattern_counts, total_games, style, weakest_area, strength
    )

    # ─── IF YOU FIXED THIS ONE THING ──────────────────────
    games_lost_to_pattern = pattern_counts.get(diagnosis_type, 0)
    pattern_rate = games_lost_to_pattern / total_games if total_games > 0 else 0

    # Rating impact per pattern type
    estimated_rating_gain = 0
    if diagnosis_type in (GameDiagnosis.THROW, GameDiagnosis.MATE_BLIND):
        estimated_rating_gain = min(games_lost_to_pattern * 20, 200)
    elif diagnosis_type in (GameDiagnosis.PIECE_GIVEAWAY, GameDiagnosis.TACTICAL_MISS):
        estimated_rating_gain = min(games_lost_to_pattern * 15, 150)
    elif diagnosis_type in (GameDiagnosis.OPENING_COLLAPSE,):
        estimated_rating_gain = min(games_lost_to_pattern * 12, 120)
    elif diagnosis_type == GameDiagnosis.SLOW_BLEED:
        estimated_rating_gain = min(games_lost_to_pattern * 8, 80)
    elif diagnosis_type == GameDiagnosis.TIME_COLLAPSE:
        estimated_rating_gain = min(games_lost_to_pattern * 18, 180)

    severity = "CRITICAL" if pattern_rate > 0.3 else "HIGH" if pattern_rate > 0.15 else "MEDIUM" if pattern_rate > 0.05 else "LOW"

    # Build the 3-line punch
    fix_habit = _diagnosis_to_habit_fix(diagnosis_type)
    stat_line = f"You've had {games_lost_to_pattern} games with {_readable_diagnosis(diagnosis_type).lower()} in your last {total_games} games"
    fix_line = f"If you {fix_habit}, your rating would be ~{estimated_rating_gain} points higher" if estimated_rating_gain > 0 else ""
    diff_line = ""
    if user_rating and estimated_rating_gain > 0:
        diff_line = f"That's the difference between {user_rating} and {user_rating + estimated_rating_gain}"

    impact = {
        "pattern_name": _readable_diagnosis(diagnosis_type),
        "occurrences": games_lost_to_pattern,
        "out_of_games": total_games,
        "rate_percent": round(pattern_rate * 100),
        "estimated_rating_gain": estimated_rating_gain,
        "current_rating": user_rating,
        "projected_rating": user_rating + estimated_rating_gain if user_rating else None,
        "severity": severity,
        "stat_line": stat_line,
        "fix_line": fix_line,
        "diff_line": diff_line,
        "one_liner": _impact_one_liner(diagnosis_type, games_lost_to_pattern, total_games, estimated_rating_gain, user_rating),
    }

    return {
        "identity": {
            "style": style,
            "strength": strength,
            "weakest_area": weakest_area,
            "before_line": before_line,
            "after_line": after_line,
            "archetype": archetype,
            "this_game_confirms": _this_game_confirms(diagnosis_type, pattern_counts),
        },
        "impact": impact,
    }


# ─── HELPERS ──────────────────────────────────────────────────────

def _get_phase(move_index: int) -> str:
    half_move = move_index
    if half_move < 20:
        return "opening"
    elif half_move < 50:
        return "middlegame"
    return "endgame"


def _build_summary(diagnosis, root_cause, critical_move, context, coach_note):
    result = {
        "diagnosis": diagnosis,
        "root_cause": root_cause,
        "context": context if isinstance(context, list) else [context],
        "coach_note": coach_note,
    }
    if critical_move:
        result["critical_move"] = {
            "move_number": critical_move["move_number"],
            "san": critical_move["san"],
            "cp_loss": critical_move["cp_loss"],
            "eval_before": critical_move.get("eval_before", 0),
            "eval_after": critical_move.get("eval_after", 0),
            "best_move": critical_move.get("best_move", ""),
            "phase": critical_move.get("phase", ""),
        }
    return result


def _draw_context(user_moves, max_advantage):
    ctx = []
    if max_advantage > 200:
        ctx.append(f"You had up to +{max_advantage / 100:.1f} advantage but couldn't convert")
    blunders = [m for m in user_moves if m["cp_loss"] >= 200]
    if blunders:
        ctx.append(f"{len(blunders)} blunder{'s' if len(blunders) > 1 else ''} during the game")
    ctx.append(f"Total centipawn loss: {sum(m['cp_loss'] for m in user_moves)}")
    return ctx


def _win_context(user_moves, total_cp_loss, opp_blunders):
    ctx = []
    ctx.append(f"Your total inaccuracy: {total_cp_loss} centipawns")
    if opp_blunders:
        ctx.append(f"Opponent made {opp_blunders} blunder{'s' if opp_blunders > 1 else ''}")
    blunders = [m for m in user_moves if m["cp_loss"] >= 200]
    if blunders:
        ctx.append(f"You had {len(blunders)} blunder{'s' if len(blunders) > 1 else ''} yourself")
    return ctx


def _count_patterns(analyses: List[Dict], current_diagnosis: str) -> Dict:
    """Count how many recent games match each diagnosis pattern."""
    counts = {}
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        if not evals:
            continue

        # Quick diagnosis based on eval data
        max_loss = max((e.get("cp_loss", 0) for e in evals), default=0)
        has_mate_miss = max_loss >= 5000
        has_big_blunder = max_loss >= 200
        blunder_count = sum(1 for e in evals if e.get("cp_loss", 0) >= 200)

        if has_mate_miss:
            counts[GameDiagnosis.MATE_BLIND] = counts.get(GameDiagnosis.MATE_BLIND, 0) + 1
        elif has_big_blunder and blunder_count <= 2:
            counts[GameDiagnosis.PIECE_GIVEAWAY] = counts.get(GameDiagnosis.PIECE_GIVEAWAY, 0) + 1
            counts[GameDiagnosis.THROW] = counts.get(GameDiagnosis.THROW, 0) + 1
        elif not has_big_blunder and max_loss >= 50:
            counts[GameDiagnosis.SLOW_BLEED] = counts.get(GameDiagnosis.SLOW_BLEED, 0) + 1

    return counts


def _readable_diagnosis(diagnosis: str) -> str:
    return {
        GameDiagnosis.THROW: "Throwing winning positions",
        GameDiagnosis.MATE_BLIND: "Missing checkmate threats",
        GameDiagnosis.SLOW_BLEED: "Gradual positional loss",
        GameDiagnosis.OPENING_COLLAPSE: "Opening preparation failure",
        GameDiagnosis.PIECE_GIVEAWAY: "Leaving pieces hanging",
        GameDiagnosis.TACTICAL_MISS: "Missing tactics",
        GameDiagnosis.TIME_COLLAPSE: "Time pressure collapse",
        GameDiagnosis.WON_CLEAN: "Clean play",
        GameDiagnosis.WON_OPPONENT_BLUNDER: "Opponent error conversion",
    }.get(diagnosis, diagnosis)


def _readable_blunder_type(bt: str) -> str:
    return {
        "missed_fork": "missing forks",
        "missed_pin": "missing pins",
        "missed_checkmate": "missing checkmate",
        "hanging_piece": "leaving pieces hanging",
        "king_safety_neglect": "king safety",
        "winning_position_collapse": "throwing winning positions",
        "time_trouble_blunder": "time pressure mistakes",
        "impulse_move": "impulse moves",
    }.get(bt, bt.replace("_", " "))


def _build_chess_dna(diagnosis, pattern_counts, total_games, style, weakest_area, strength):
    """
    Build the "Before this game / After this game" Chess DNA narrative.
    Returns (before_line, after_line, archetype)
    """
    count = pattern_counts.get(diagnosis, 0)

    # Archetype: derived from dominant pattern
    archetype = _style_to_archetype(style, weakest_area, diagnosis, count, total_games)

    # "Before this game" — who you were coming in
    if style and style != "developing":
        style_label = style.replace("_", " ").title()
        if weakest_area and weakest_area != "general play":
            before_line = f"You were a {style_label.lower()} player who struggles with {weakest_area}"
        else:
            before_line = f"You were a {style_label.lower()} player with solid fundamentals"
    else:
        if weakest_area and weakest_area != "general play":
            before_line = f"You were a developing player with a recurring leak in {weakest_area}"
        else:
            before_line = "You were a developing player building your chess identity"

    # "After this game" — how this game changed things
    diag_label = _readable_diagnosis(diagnosis).lower()
    if diagnosis in (GameDiagnosis.WON_CLEAN,):
        after_line = "Solid performance. This is the player you want to be consistently."
    elif diagnosis in (GameDiagnosis.WON_OPPONENT_BLUNDER,):
        after_line = "You won, but the sloppiness is still there. Clean wins build identity — messy ones don't."
    elif count >= 5:
        after_line = f"+1 more game lost to {diag_label}. This is now your signature weakness."
    elif count >= 3:
        after_line = f"+1 more {diag_label}. This is becoming a pattern — {count + 1} times now."
    elif count >= 1:
        after_line = f"Another game with {diag_label}. It happened before — now it's happening again."
    else:
        after_line = f"First game lost to {diag_label}. One-off or emerging habit? Next games will tell."

    return before_line, after_line, archetype


def _style_to_archetype(style, weakest_area, diagnosis, count, total_games):
    """Determine player archetype label based on patterns."""
    # If dominant pattern is clear
    if count >= 5 and total_games > 0 and count / total_games > 0.2:
        return {
            GameDiagnosis.THROW: "The Thrower",
            GameDiagnosis.MATE_BLIND: "The Blind Spot",
            GameDiagnosis.SLOW_BLEED: "The Slow Leak",
            GameDiagnosis.OPENING_COLLAPSE: "The Opening Gambler",
            GameDiagnosis.PIECE_GIVEAWAY: "The Gift Giver",
            GameDiagnosis.TIME_COLLAPSE: "The Clock Fighter",
            GameDiagnosis.TACTICAL_MISS: "The Calculator (Broken)",
        }.get(diagnosis, style.replace("_", " ").title() if style else "Developing")

    # Otherwise use style
    return {
        "aggressive": "Attacker",
        "positional": "Strategist",
        "tactical": "Tactician",
        "defensive": "Fortress Builder",
        "universal": "All-Rounder",
    }.get(style, "Developing")


def _diagnosis_to_habit_fix(diagnosis):
    """Map diagnosis to the ONE habit that would fix it."""
    return {
        GameDiagnosis.THROW: "held focus in winning positions",
        GameDiagnosis.MATE_BLIND: "checked opponent threats before every move",
        GameDiagnosis.SLOW_BLEED: "played with a clear plan each move",
        GameDiagnosis.OPENING_COLLAPSE: "studied your opening repertoire",
        GameDiagnosis.PIECE_GIVEAWAY: "checked if your pieces are safe before moving",
        GameDiagnosis.TACTICAL_MISS: "spent 10 more seconds on critical moves",
        GameDiagnosis.TIME_COLLAPSE: "managed your clock better in the middlegame",
        GameDiagnosis.WON_CLEAN: "kept this level of focus consistently",
        GameDiagnosis.WON_OPPONENT_BLUNDER: "eliminated your own blunders",
        GameDiagnosis.DRAW: "pushed harder in equal positions",
    }.get(diagnosis, "fixed your most common mistake")


def _this_game_confirms(diagnosis, pattern_counts):
    count = pattern_counts.get(diagnosis, 0)
    if count >= 5:
        return f"This game confirms a recurring problem. {_readable_diagnosis(diagnosis)} is becoming your signature weakness."
    elif count >= 3:
        return f"This is a pattern now. You've done this {count} times."
    elif count >= 1:
        return "This has happened before. Watch for it becoming a habit."
    return "First occurrence. One-off or emerging pattern? Next few games will tell."


def _impact_one_liner(diagnosis, occurrences, total_games, rating_gain, current_rating):
    if rating_gain == 0:
        return "No significant rating impact from this pattern."
    if current_rating:
        return f"Fixing '{_readable_diagnosis(diagnosis).lower()}' could take you from {current_rating} to ~{current_rating + rating_gain}."
    return f"Fixing this one pattern could gain you ~{rating_gain} rating points."
