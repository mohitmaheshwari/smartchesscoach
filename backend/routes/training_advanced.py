from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
import os

router = APIRouter(tags=["Training Advanced"])
db = None
call_llm_fn = None

def set_db(database):
    global db
    db = database

def set_llm(llm_fn):
    global call_llm_fn
    call_llm_fn = llm_fn

from routes.auth import get_current_user, User

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')


# =============================================================================
# BEHAVIOR DIAGNOSIS ENGINE v4 — Production-ready
# =============================================================================
#
# STRUCTURE: [MOMENT] + [BEHAVIOR] + [PATTERN (if in THIS game)] + [RULE]
#
# INTENSITY (hard thresholds, 4 tiers):
#   CALM:        blunders == 0 AND mistakes <= 2 AND NOT lost_winning
#   FIRM:        blunders == 1 OR mistakes >= 3 OR (won AND blunders >= 1)
#   SHARP_LIGHT: blunders >= 2 (firm + serious)
#   SHARP_HEAVY: lost_winning == true OR pattern_count >= 5 (identity pressure)
#
# PRIORITY STACK:
#   0. recovery (pattern exists historically but ABSENT in this game)
#   1. brilliant
#   2. lost_winning
#   3. critical_move
#   4. pattern (ONLY if present in THIS game AND count >= 3)
#   5. blunder count
#   6. general result
#
# PATTERN RULES:
#   - Pattern escalation ONLY triggers if pattern appears in THIS game
#   - If pattern exists historically but NOT in this game → recovery message
#   - Escalation: 3-4 → "keeps happening" / 5-6 → "becoming your pattern" / 7+ → "biggest weakness"
#
# SINGLE BEHAVIOR: always pick ONE dominant mistake per message
# PHASE AWARENESS: inject "in the opening" / "in the endgame" where relevant
#
# NAMED RULES (label + instruction — users remember the label):
RULE_MAP = {
    "piece_safety":       {"name": "Piece Safety Check",    "rule": "Before moving, check: is anything I own under attack?"},
    "missed_tactic":      {"name": "Tactics Scan",          "rule": "Look for captures, checks, and threats — in that order — every move."},
    "ignore_threat":      {"name": "Threat Awareness",      "rule": "Before every move, ask: what is my opponent attacking?"},
    "calculation_depth":  {"name": "Calculation Depth",     "rule": "Calculate one move deeper before committing."},
    "king_safety":        {"name": "King Safety First",     "rule": "Before attacking, check: is my king safe?"},
    "time_pressure":      {"name": "Clock Discipline",      "rule": "Slow down on critical moves. Don't rush decisions."},
    "conversion":         {"name": "Winning Discipline",    "rule": "When ahead, slow down and protect your advantage."},
    "endgame_technique":  {"name": "Endgame Activation",   "rule": "In endgames, activate your king and push passed pawns."},
    "opening_knowledge":  {"name": "Opening Discipline",   "rule": "Stick to your opening prep. Don't improvise in the first 10 moves."},
    "tactical_oversight": {"name": "Opponent Response",     "rule": "After deciding your move, pause and ask: what can my opponent do next?"},
    "pawn_structure":     {"name": "Structure Awareness",   "rule": "Think about pawn structure before exchanges."},
    "piece_activity":     {"name": "Piece Activity",        "rule": "Every piece needs a job. Reposition idle pieces."},
    "_default":           {"name": "Opponent Response",     "rule": "Before every move, ask: what is my opponent's best response?"},
    "_consistency":       {"name": "Consistency",           "rule": "Follow the same thinking process every move."},
    "_recovery":          {"name": None,                    "rule": "Keep applying it every move."},
}

# PRESSURE RELEASE: appended to SHARP_HEAVY messages
PRESSURE_RELEASE = {
    "piece_safety":      "Fix this, and your level will jump immediately.",
    "ignore_threat":     "Fix this one thing, and you'll stop losing games you should win.",
    "conversion":        "Learn to hold advantages, and your rating will climb fast.",
    "calculation_depth": "One move deeper is all it takes to break through.",
    "time_pressure":     "Control your clock, and the mistakes will disappear.",
    "endgame_technique": "Better endgames means more points from drawn positions.",
    "_default":          "Fix this, and your results will change.",
}


def _pattern_prefix(count):
    """
    Continuity word. Avoids "Again" fatigue.
    3-4: "Again, " (first awareness)
    5-6: "" (drop Again, go direct to escalation)
    7+:  "" (identity only, no prefix needed)
    """
    if 3 <= count <= 4:
        return "Again, "
    return ""


def _pattern_phrase(count):
    """Exact escalation. No drift."""
    if count >= 7:
        return "This is your biggest weakness right now."
    if count >= 5:
        return "This is becoming your pattern."
    if count >= 3:
        return "This keeps happening."
    return ""


def _get_rule(key):
    """Returns 'Rule: <Name> — <instruction>'"""
    entry = RULE_MAP.get(key, RULE_MAP["_default"])
    return f"Rule: {entry['name']} — {entry['rule']}"


def _get_rule_recovery(key):
    """Returns 'Rule: <Name> — keep applying it every move.'"""
    entry = RULE_MAP.get(key, RULE_MAP["_default"])
    return f"Rule: {entry['name']} — keep applying it every move."


def _get_release(key):
    """Pressure release sentence for SHARP_HEAVY."""
    return PRESSURE_RELEASE.get(key, PRESSURE_RELEASE["_default"])


def _recovery_message(gap_label, consecutive_clean, behavior_key):
    """
    Progressive recovery language. Gets stronger with consecutive clean games.
    consecutive_clean: how many recent games in a row WITHOUT this pattern.
    """
    if consecutive_clean >= 3:
        return f"{gap_label.capitalize()} is no longer breaking your games. Keep it that way. {_get_rule_recovery(behavior_key)}"
    if consecutive_clean == 2:
        return f"Two games now without {gap_label}. You're fixing this. {_get_rule_recovery(behavior_key)}"
    return f"This time, no {gap_label}. That's been your weak spot — this is real progress. {_get_rule_recovery(behavior_key)}"


def _phase_label(move_number):
    """Inject phase context."""
    if move_number and move_number <= 12:
        return "in the opening"
    if move_number and move_number >= 35:
        return "in the endgame"
    return "in the middlegame"


def _generate_game_story(evals, user_color, user_won, is_draw, was_winning, max_advantage,
                          blunders, mistakes, accuracy, brilliant_count,
                          pattern_history=None, recovery_consecutive=0):
    """
    Deterministic behavior diagnosis.
    pattern_history: { gap_type: total_game_count } from pattern_memory_service
    recovery_consecutive: how many recent games in a row WITHOUT the recovery pattern (computed by caller)
    """
    if not evals:
        return ""

    user_is_white = user_color == "white"
    ph = pattern_history or {}

    # ── EXTRACT SIGNALS ──

    # Critical move: single highest cp_loss
    critical = None
    critical_cp = 0
    for e in evals:
        cp = e.get("cp_loss", 0) or 0
        if cp > critical_cp:
            critical_cp = cp
            critical = e

    # Collapse point
    collapse_move = None
    lost_winning = was_winning and not user_won and not is_draw
    if was_winning:
        for e in evals:
            ev = e.get("eval_before", 0)
            user_ev = ev if user_is_white else -ev
            if user_ev < -150 and not collapse_move:
                collapse_move = e.get("move_number", 0)

    # Cognitive gaps in THIS game only (one per type, not per move)
    game_gaps = {}
    for e in evals:
        gap = e.get("cognitive_gap", "")
        if gap and (e.get("cp_loss", 0) or 0) >= 80:
            game_gaps[gap] = game_gaps.get(gap, 0) + 1

    # Single dominant behavior: highest frequency in this game, tie-break by severity
    biggest_gap = max(game_gaps, key=game_gaps.get) if game_gaps else None

    # Threat ignores: cp_loss >= 150 AND threat field populated
    threat_ignores = sum(1 for e in evals if e.get("threat") and (e.get("cp_loss", 0) or 0) >= 150)

    # Rushed: time_spent < 3s AND cp_loss >= 50
    rushed = sum(1 for e in evals if (e.get("time_spent") or 99) < 3 and (e.get("cp_loss", 0) or 0) >= 50)

    # Pattern: ONLY counts if the gap appears in THIS game
    pattern_count = ph.get(biggest_gap, 0) if biggest_gap and biggest_gap in game_gaps else 0
    pattern_active = pattern_count >= 3  # Pattern present in this game AND historically significant

    # Check for recovery: pattern exists historically (count >= 3) but NOT in this game
    recovery_gap = None
    for gap_type, total in sorted(ph.items(), key=lambda x: -x[1]):
        if total >= 3 and gap_type not in game_gaps:
            recovery_gap = gap_type
            break

    # Behavior key for rule lookup — single behavior, highest priority
    if threat_ignores >= 2:
        behavior_key = "ignore_threat"
    elif rushed >= 2:
        behavior_key = "time_pressure"
    elif lost_winning and not collapse_move:
        behavior_key = "conversion"
    elif biggest_gap:
        behavior_key = biggest_gap
    else:
        behavior_key = "_default"

    # Intensity (4 tiers)
    if lost_winning or pattern_count >= 5:
        intensity = "sharp_heavy"
    elif blunders >= 2 or (pattern_active and pattern_count >= 3):
        intensity = "sharp_light"
    elif blunders == 1 or mistakes >= 3 or (user_won and blunders >= 1):
        intensity = "firm"
    else:
        intensity = "calm"

    rule = _get_rule(behavior_key)
    phase = _phase_label(critical.get("move_number") if critical else None)

    # ═══ PRIORITY 0: RECOVERY — pattern exists historically but ABSENT in this game ═══
    if recovery_gap and user_won and blunders == 0:
        gap_label = recovery_gap.replace("_", " ")
        return _recovery_message(gap_label, recovery_consecutive, recovery_gap)

    if recovery_gap and blunders <= 1 and not lost_winning and biggest_gap != recovery_gap:
        gap_label = recovery_gap.replace("_", " ")
        return _recovery_message(gap_label, recovery_consecutive, recovery_gap)

    # ═══ PRIORITY 1: BRILLIANT MOVE ═══
    if brilliant_count > 0:
        if user_won:
            return "You calculated deeply here — and it worked. This is the level you're capable of. Do this consistently."
        return "You found a brilliant sacrifice but couldn't convert. The vision is there — the technique needs to catch up."

    # ═══ PRIORITY 2: LOST WINNING POSITION (SHARP_HEAVY) ═══
    if lost_winning:
        moment = f"You had full control — then lost it around move {collapse_move} {phase}." if collapse_move else "You had the advantage and let it slip."
        behavior = behavior_key.replace("_", " ")
        if pattern_active:
            prefix = _pattern_prefix(pattern_count)
            release = _get_release(behavior_key)
            return f"{moment} {prefix}{behavior}. {_pattern_phrase(pattern_count)} {release}"
        return f"{moment} {rule}"

    if was_winning and is_draw:
        moment = f"You had a winning position {phase} but couldn't convert."
        if pattern_active:
            prefix = _pattern_prefix(pattern_count)
            release = _get_release(behavior_key)
            return f"{moment} {prefix}conversion issues. {_pattern_phrase(pattern_count)} {release}"
        return f"{moment} {rule}"

    # ═══ PRIORITY 3: CRITICAL MOVE ═══
    if not user_won and not is_draw and blunders == 1 and critical:
        mn = critical.get("move_number", "?")
        ms = critical.get("move", "")
        moment = f"One moment on move {mn} ({ms}) {phase} cost you the game."
        behavior = behavior_key.replace("_", " ")
        if pattern_active:
            prefix = _pattern_prefix(pattern_count)
            release = _get_release(behavior_key)
            return f"{moment} {prefix}{behavior}. {_pattern_phrase(pattern_count)} {release}"
        return f"{moment} {rule}"

    # ═══ PRIORITY 4: PATTERN (in THIS game + count >= 3) ═══
    if pattern_active and not user_won and biggest_gap:
        gap_label = biggest_gap.replace("_", " ")
        prefix = _pattern_prefix(pattern_count)
        release = _get_release(behavior_key) if intensity == "sharp_heavy" else ""
        return f"{prefix}{gap_label} {phase}. {_pattern_phrase(pattern_count)} {release} {rule}".strip()

    # ═══ PRIORITY 5: BLUNDER COUNT ═══

    # 3+ blunders
    if blunders >= 3:
        if rushed >= 2:
            return f"You're playing faster than you're thinking. {_get_rule('time_pressure')}"
        if biggest_gap:
            gap_label = biggest_gap.replace("_", " ")
            return f"Several critical mistakes {phase}, mostly {gap_label}. {rule}"
        return f"Several critical mistakes {phase}. {rule}"

    # 2 blunders
    if blunders >= 2:
        if biggest_gap:
            gap_label = biggest_gap.replace("_", " ")
            return f"Two moments of {gap_label} {phase}. {rule}"
        return f"Two critical moments {phase}. {rule}"

    # Won with 1 blunder
    if user_won and blunders == 1 and critical:
        mn = critical.get("move_number", "?")
        ms = critical.get("move", "")
        return f"You won, but {ms} on move {mn} showed a drop in focus. One lapse — the rest was solid."

    # Won with 2+ blunders
    if user_won and blunders >= 2:
        return "You won, but gave your opponent real chances. They didn't take them — next opponent might."

    # ═══ PRIORITY 6: GENERAL RESULT ═══

    if user_won and blunders == 0 and mistakes <= 2:
        return f"Clean, controlled game. This is what disciplined play looks like. Rule: Consistency — follow the same thinking process every move."

    if is_draw and blunders == 0:
        return "Solid, disciplined game. The position was equal and you handled it well."

    if user_won:
        return "Good result. You controlled the game when it mattered."

    if not user_won and not is_draw and blunders == 0:
        return "No major mistakes, but your opponent outplayed you in small ways. The position gradually slipped."

    if not user_won and not is_draw:
        return f"A game with clear lessons {phase}. {rule}"

    if is_draw:
        return "A balanced fight. Look for moments where you could have pushed for more."

    return ""


# =============================================================================
# SECTION A: Lab pick + puzzles
# =============================================================================

@router.get("/lab-coach-pick")
async def get_lab_coach_pick(user: User = Depends(get_current_user)):
    """
    Smart game picker for the Lab page.
    Returns the most educational unreviewed game + reason + all games with reviewed status.

    Priority:
    1. Recurring pattern (same mistake in multiple games)
    2. Thrown game (was winning, lost)
    3. Single decisive blunder (one teachable moment)
    Skip: clean wins, already reviewed games
    """
    # Get all analyzed games with analysis data
    games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(100)

    analyses_cursor = db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis.blunders": 1, "stockfish_analysis.mistakes": 1,
         "stockfish_analysis.move_evaluations": 1, "stockfish_analysis.accuracy": 1,
         "coach_summary": 1, "decryption_v5_data.core_lesson": 1}
    )
    analyses = {a["game_id"]: a async for a in analyses_cursor}

    # Get REAL pattern memory — persistent, decay-weighted, across all games
    pattern_history = {}
    try:
        from services.pattern_memory_service import get_pattern_summary
        pattern_summary = await get_pattern_summary(db, user.user_id)
        for p in pattern_summary.get("patterns", []):
            pt = p.get("pattern_type", "")
            if pt:
                pattern_history[pt] = p.get("total_count", 0)
    except Exception as ph_err:
        logger.warning(f"Pattern memory service failed, using fallback: {ph_err}")
        # Fallback: count from loaded analyses (game-level, not move-level)
        for gid_f, a_f in analyses.items():
            seen_gaps = set()
            for e in a_f.get("stockfish_analysis", {}).get("move_evaluations", []):
                gap = e.get("cognitive_gap", "")
                if gap and (e.get("cp_loss", 0) or 0) >= 80 and gap not in seen_gaps:
                    seen_gaps.add(gap)
                    pattern_history[gap] = pattern_history.get(gap, 0) + 1

    # Build enriched game list
    enriched = []
    for g in games:
        gid = g.get("game_id", "")
        a = analyses.get(gid, {})
        sf = a.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        uc = g.get("user_color", "white")
        result = g.get("result", "")
        user_won = (result == "1-0" and uc == "white") or (result == "0-1" and uc == "black")
        is_draw = "1/2" in result
        blunders = sf.get("blunders", 0)
        mistakes = sf.get("mistakes", 0)
        accuracy = sf.get("accuracy", 0)
        reviewed = g.get("reviewed", False)

        # Check if was winning (eval > +2 from user's perspective at any point)
        was_winning = False
        max_advantage = 0
        for e in evals:
            ev = e.get("eval_before", 0)
            user_ev = ev if uc == "white" else -ev
            if user_ev > max_advantage:
                max_advantage = user_ev
            if user_ev > 200:
                was_winning = True

        # Count cognitive gaps for pattern matching
        cognitive_gaps = []
        for e in evals:
            gap = e.get("cognitive_gap", "")
            if gap and e.get("cp_loss", 0) >= 100:
                cognitive_gaps.append(gap)

        # Count brilliant moves and sacrifices in this game
        brilliant_count = sum(1 for e in evals if e.get("is_brilliant"))
        sacrifice_count = sum(1 for e in evals if e.get("is_sacrifice"))
        brilliant_moves_detail = [
            {"move": e.get("move", ""), "move_number": e.get("move_number", 0)}
            for e in evals if e.get("is_brilliant")
        ]

        opp = g.get("opponent_name") or (g.get("white_player") if uc == "black" else g.get("black_player")) or ""

        # Behavioral data from enriched analysis
        coach_sum = a.get("coach_summary", {}) or {}
        # Handle decryption_v5_data being either dict or list
        decrypt_data = a.get("decryption_v5_data", {})
        if isinstance(decrypt_data, list):
            decrypt_data = {}  # Fallback if it's a list
        core_les = (decrypt_data or {}).get("core_lesson", {}) or {}

        # Override lesson_label for games with brilliant play
        lesson_label = core_les.get("short_label", "")
        if brilliant_count > 0 and not lesson_label:
            lesson_label = f"Brilliant sacrifice" if sacrifice_count > 0 else "Brilliant play"

        # Generate coach-style game summary (no LLM — pure deterministic)
        behavior = coach_sum.get("behavioral_insight") or coach_sum.get("key_observation") or ""
        if not behavior:
            try:
                # Compute recovery_consecutive: how many recent games lack the top pattern
                rc = 0
                top_pattern_key = max(pattern_history, key=pattern_history.get) if pattern_history else None
                if top_pattern_key and pattern_history.get(top_pattern_key, 0) >= 3:
                    game_ids_rev = list(analyses.keys())
                    for gid_rc in reversed(game_ids_rev):
                        a_rc = analyses[gid_rc]
                        rc_evals = a_rc.get("stockfish_analysis", {}).get("move_evaluations", [])
                        has_it = any(
                            e.get("cognitive_gap") == top_pattern_key and (e.get("cp_loss", 0) or 0) >= 80
                            for e in rc_evals
                        )
                        if has_it:
                            break
                        rc += 1
                    rc = min(rc, 10)

                behavior = _generate_game_story(
                    evals, uc, user_won, is_draw, was_winning, max_advantage,
                    blunders, mistakes, accuracy, brilliant_count,
                    pattern_history, rc
                )

                # Apply coach voice personality
                try:
                    from services.coach_voice import apply_coach_voice

                    lost_winning_g = was_winning and not user_won and not is_draw

                    # Find dominant gap in this game's evals
                    g_gaps = {}
                    for ev in evals:
                        g = ev.get("cognitive_gap", "")
                        if g and (ev.get("cp_loss", 0) or 0) >= 80:
                            g_gaps[g] = g_gaps.get(g, 0) + 1
                    top_g = max(g_gaps, key=g_gaps.get) if g_gaps else None
                    pc = pattern_history.get(top_g, 0) if top_g and top_g in g_gaps else 0

                    if lost_winning_g or pc >= 5:
                        v_intensity = "sharp_heavy"
                    elif blunders >= 2 or pc >= 3:
                        v_intensity = "sharp_light"
                    elif brilliant_count > 0:
                        v_intensity = "brilliant"
                    elif rc > 0 and top_g and top_g not in g_gaps:
                        v_intensity = "recovery"
                    elif blunders == 1 or mistakes >= 3:
                        v_intensity = "firm"
                    else:
                        v_intensity = "calm"

                    behavior = apply_coach_voice(behavior, v_intensity, {
                        "games_together": len(games),
                        "pattern_count": pc,
                        "is_recovery": rc > 0 and top_g and top_g not in g_gaps,
                    })
                except Exception:
                    pass  # Voice wrapper is non-fatal

            except Exception as story_err:
                logger.warning(f"Game story generation failed for {gid}: {story_err}")
                behavior = ""

        enriched.append({
            "game_id": gid,
            "opponent": opp,
            "result": "W" if user_won else ("D" if is_draw else "L"),
            "user_color": uc,
            "blunders": blunders,
            "mistakes": mistakes,
            "accuracy": round(accuracy, 1) if accuracy else 0,
            "reviewed": reviewed,
            "was_winning": was_winning,
            "max_advantage": round(max_advantage / 100, 1),
            "cognitive_gaps": cognitive_gaps,
            "opening": g.get("opening", ""),
            "summary_headline": g.get("summary", {}).get("headline") if isinstance(g.get("summary"), dict) else None,
            "behavior": behavior,
            "lesson_label": lesson_label,
            "lesson": core_les.get("lesson", ""),
            "brilliant_moves": brilliant_count,
            "sacrifices": sacrifice_count,
            "brilliant_detail": brilliant_moves_detail,
        })

    # ── SMART PICK: find the best unreviewed game ──
    unreviewed = [g for g in enriched if not g["reviewed"]]
    pick = None
    pick_reason = ""
    pick_pattern = ""

    if unreviewed:
        # Use recency-weighted decay model instead of raw counts
        from services.pattern_decay_service import compute_pattern_scores, pick_best_game

        pattern_scores = compute_pattern_scores(enriched)

        # Priority 1: Pattern-based pick using decay model
        picked, reason, pattern_key, score_data = pick_best_game(unreviewed, pattern_scores)
        if picked:
            pick = picked
            pick_reason = reason
            pick_pattern = pattern_key

        # Priority 2: Thrown game (was winning, lost)
        if not pick:
            for g in unreviewed:
                if g["result"] == "L" and g["was_winning"]:
                    pick = g
                    if g.get("behavior"):
                        pick_reason = f"You were +{g['max_advantage']} and lost. {g['behavior']}"
                    else:
                        pick_reason = f"You were +{g['max_advantage']} and threw it. This is where rating points go to die."
                    break

        # Priority 3: Loss with single decisive blunder
        if not pick:
            for g in unreviewed:
                if g["result"] == "L" and g["blunders"] >= 1:
                    pick = g
                    if g.get("lesson"):
                        pick_reason = g["lesson"]
                    else:
                        pick_reason = f"{g['blunders']} blunder{'s' if g['blunders'] > 1 else ''} decided this game. One lesson to learn."
                    break

        # Fallback: any unreviewed loss
        if not pick:
            for g in unreviewed:
                if g["result"] == "L":
                    pick = g
                    pick_reason = g.get("behavior") or "Your coach thinks this game has something to teach you."
                    break

        # Last resort: any unreviewed game
        if not pick and unreviewed:
            pick = unreviewed[0]
            pick_reason = g.get("behavior") or "Start with your most recent game."

    # Verdict strip
    recent = enriched[:15]
    wins = sum(1 for g in recent if g["result"] == "W")
    losses = sum(1 for g in recent if g["result"] == "L")
    blunder_losses = sum(1 for g in recent if g["result"] == "L" and g["blunders"] >= 1)
    throws = sum(1 for g in recent if g["result"] == "L" and g["was_winning"])

    insight = ""
    if throws >= 2:
        insight = f"{throws} games thrown from winning positions. That's where your rating is leaking."
    elif blunder_losses >= 3:
        insight = f"{blunder_losses} losses from blunders — you're not being outplayed, you're beating yourself."
    elif wins > losses * 2:
        insight = "Strong form. Keep the momentum."
    elif losses > wins:
        insight = "Rough stretch. Review losses, don't just play more."
    else:
        insight = "Steady form. Room to sharpen."

    return {
        "pick": pick,
        "pick_reason": pick_reason,
        "pick_pattern": pick_pattern,
        "verdict": {"wins": wins, "losses": losses, "total": len(recent), "insight": insight},
        "games": enriched,
        "reviewed_count": sum(1 for g in enriched if g["reviewed"]),
        "total_count": len(enriched),
    }


@router.post("/lab-mark-reviewed/{game_id}")
async def mark_game_reviewed(game_id: str, user: User = Depends(get_current_user)):
    """Mark a game as reviewed by the user."""
    result = await db.games.update_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"$set": {"reviewed": True, "reviewed_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}}
    )
    return {"success": result.modified_count > 0}


@router.get("/training/pattern-puzzles/{pattern}")
async def get_pattern_puzzles(
    pattern: str,
    limit: int = 15,
    user: User = Depends(get_current_user),
):
    """
    Get training puzzles for a specific cognitive gap pattern.
    Returns user's own game positions first, then community puzzles.
    Excludes already-solved puzzles.
    Auto-triggers backfill if no puzzles exist yet.
    """
    from services.puzzle_extraction_service import get_pattern_training_puzzles, backfill_puzzles_for_user

    # Check if user has ANY puzzles — if not, auto-backfill
    existing = await db.community_puzzles.count_documents({"shared_by": user.user_id})
    if existing == 0:
        try:
            created = await backfill_puzzles_for_user(db, user.user_id)
            if created > 0:
                logger.info(f"Auto-backfilled {created} puzzles for {user.user_id}")
        except Exception as e:
            logger.warning(f"Auto-backfill failed: {e}")

    return await get_pattern_training_puzzles(db, user.user_id, pattern, limit)


@router.post("/training/extract-puzzles")
async def extract_puzzles_endpoint(user: User = Depends(get_current_user)):
    """
    Backfill/extract puzzles from user's analyzed games into the community pool.
    """
    from services.puzzle_extraction_service import backfill_puzzles_for_user
    count = await backfill_puzzles_for_user(db, user.user_id)
    return {"puzzles_created": count, "message": f"Extracted {count} training positions from your games."}


@router.post("/lab/{game_id}/complete-review")
async def complete_game_review(game_id: str, request: Request, user: User = Depends(get_current_user)):
    """
    Complete a game review session. Saves what was learned, marks as reviewed,
    and returns a summary + next game recommendation.
    """
    from datetime import datetime, timezone

    body = await request.json()
    concepts_learned = body.get("concepts_learned", 0)
    drills_solved = body.get("drills_solved", 0)
    tabs_visited = body.get("tabs_visited", [])
    moves_viewed = body.get("moves_viewed", 0)
    total_moves = body.get("total_moves", 0)

    now = datetime.now(timezone.utc).isoformat()

    # 1. Mark game as reviewed
    await db.games.update_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"$set": {
            "reviewed": True,
            "reviewed_at": now,
            "review_stats": {
                "concepts_learned": concepts_learned,
                "drills_solved": drills_solved,
                "tabs_visited": tabs_visited,
                "moves_viewed": moves_viewed,
                "total_moves": total_moves,
                "completed_at": now,
            },
        }}
    )

    # 2. Get the lesson and coach summary for this game
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "coach_summary": 1, "decryption_v5_data.core_lesson": 1}
    )
    coach_sum = (analysis or {}).get("coach_summary", {}) or {}
    decrypt_data = (analysis or {}).get("decryption_v5_data", {})
    if isinstance(decrypt_data, list):
        decrypt_data = {}
    core_les = (decrypt_data or {}).get("core_lesson", {}) or {}

    # Build the takeaway
    takeaway = coach_sum.get("actionable_takeaway") or core_les.get("behavioral_fix") or ""
    lesson = core_les.get("lesson") or coach_sum.get("key_observation") or ""
    lesson_label = core_les.get("short_label", "")

    # 3. Find the next unreviewed game (next Coach's Pick)
    next_game = await db.games.find_one(
        {"user_id": user.user_id, "is_analyzed": True, "reviewed": {"$ne": True}, "game_id": {"$ne": game_id}},
        {"_id": 0, "game_id": 1, "opponent_name": 1, "result": 1, "user_color": 1, "opening": 1},
        sort=[("imported_at", -1)]
    )

    next_rec = None
    if next_game:
        uc = next_game.get("user_color", "white")
        res = next_game.get("result", "")
        won = (res == "1-0" and uc == "white") or (res == "0-1" and uc == "black")
        next_rec = {
            "game_id": next_game["game_id"],
            "opponent": next_game.get("opponent_name", ""),
            "result": "W" if won else ("D" if "1/2" in res else "L"),
            "opening": next_game.get("opening", ""),
        }

    return {
        "success": True,
        "summary": {
            "lesson_label": lesson_label,
            "lesson": lesson,
            "takeaway": takeaway,
            "concepts_learned": concepts_learned,
            "drills_solved": drills_solved,
        },
        "next_game": next_rec,
    }


# =============================================================================
# SECTION B: Training profile & reflection
# =============================================================================

@router.get("/training/profile")
async def get_training_profile_endpoint(
    force_regenerate: bool = False,
    user: User = Depends(get_current_user)
):
    """
    Get the user's training profile.

    The training profile contains:
    - active_phase: The layer with highest cost (stability/conversion/structure/precision)
    - micro_habit: The dominant pattern within the active phase
    - rules: 2 actionable rules for the week
    - layer_breakdown: Costs for all 4 layers
    - example_positions: Positions from their mistakes for practice
    - reflection_question: Question to prompt self-reflection

    Recalculates automatically every 7 games or when force_regenerate=True.
    """
    from training_profile_service import get_or_generate_training_profile

    # Get user's rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("rating", 1200) if user_doc else 1200

    profile = await get_or_generate_training_profile(db, user.user_id, rating, force_regenerate)
    return profile


@router.post("/training/profile/regenerate")
async def regenerate_training_profile(user: User = Depends(get_current_user)):
    """Force regenerate the training profile."""
    from training_profile_service import generate_training_profile

    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("rating", 1200) if user_doc else 1200

    profile = await generate_training_profile(db, user.user_id, rating)
    return profile


@router.get("/training/reflection-options")
async def get_reflection_options_endpoint(user: User = Depends(get_current_user)):
    """
    Get reflection options based on the user's active phase.

    Returns tagged options the user can select from to describe
    what happened in their game. These options update pattern weights.
    """
    from training_profile_service import get_reflection_options

    options = await get_reflection_options(db, user.user_id)
    return options


@router.post("/training/reflection")
async def save_reflection_endpoint(
    game_id: str,
    reflection_data: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Save a reflection for a specific game.

    Body:
    - selected_tags: List of pattern tags (e.g., ["rushing", "threat_blindness"])
    - free_text: Optional free-form reflection text

    This updates pattern weights to improve personalization.
    """
    from training_profile_service import save_reflection

    result = await save_reflection(db, user.user_id, game_id, reflection_data)
    return result


@router.get("/training/drills")
async def get_training_drills(
    limit: int = 5,
    user: User = Depends(get_current_user)
):
    """
    Get drill positions for training.

    Sources drills from:
    1. User's own mistakes (priority)
    2. Similar users' mistakes (same rating band, same micro habit)

    Each drill contains:
    - fen: Position to practice
    - correct_move: The better move
    - user_move: What was played (if from user's game)
    - cp_loss: How much the mistake cost
    - source: "own_game" or "similar_user"
    """
    from training_profile_service import get_drill_positions

    drills = await get_drill_positions(db, user.user_id, limit)
    return {"drills": drills, "count": len(drills)}


@router.get("/training/layer-info")
async def get_layer_info():
    """
    Get information about training layers and patterns.

    Returns static information for UI display.
    """
    from training_profile_service import TRAINING_LAYERS, PATTERN_INFO

    return {
        "layers": TRAINING_LAYERS,
        "patterns": PATTERN_INFO,
    }


@router.get("/training/game/{game_id}/milestones")
async def get_game_milestones(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get ALL mistakes/milestones from a game for reflection.

    Rating-based filtering:
    - <1000: Only blunders (≥200cp)
    - 1000-1400: Blunders + big mistakes (≥150cp)
    - 1400-1800: All mistakes (≥100cp)
    - 1800+: Including inaccuracies (≥50cp)

    Each milestone includes:
    - Position FEN, move played, better move
    - PV lines for interactive board
    - Threat info if applicable
    - Contextual reflection options
    """
    from training_profile_service import get_game_milestones_for_reflection

    # Get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("rating", 1200) if user_doc else 1200

    result = await get_game_milestones_for_reflection(db, user.user_id, game_id, rating)
    return result


@router.post("/training/milestone/explain")
async def explain_milestone(
    milestone_data: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Generate human-readable explanation for why better move is better.

    Uses Stockfish data (deterministic) + GPT for natural language.

    Body:
    - context_for_explanation: The milestone's context data
    - fen: Position FEN
    - move_played: What user played
    - best_move: What was better
    """
    from training_profile_service import generate_position_explanation

    # Get user rating category
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("rating", 1200) if user_doc else 1200

    milestone_data["rating_category"] = "beginner" if rating < 1000 else "intermediate" if rating < 1400 else "club" if rating < 1800 else "advanced"

    explanation = await generate_position_explanation(db, milestone_data, use_llm=True)

    # If LLM humanization needed, call GPT
    if explanation.get("needs_llm_humanization"):
        try:
            from llm_helper import LlmChat, UserMessage
            import os

            api_key = os.environ.get("EMERGENT_LLM_KEY", OPENAI_API_KEY)

            chat = LlmChat(
                api_key=api_key,
                session_id=f"explain_{os.urandom(8).hex()}",
                system_message="You are a chess coach explaining moves to amateur players. Be concrete and simple. Focus on the 'what happens' not abstract strategy."
            ).with_model("openai", "gpt-4o-mini")

            response = await chat.send_message(UserMessage(text=explanation["llm_prompt"]))

            explanation["human_explanation"] = response
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            # Fallback to stockfish analysis
            sf_analysis = explanation.get("stockfish_analysis", {})
            explanation["human_explanation"] = f"{sf_analysis.get('position_context', 'In this position')}, you played {explanation['move_played']} but {explanation['best_move']} was better. {sf_analysis.get('threat_missed', '')} {sf_analysis.get('cp_lost', '')}."

    return explanation


@router.post("/training/plan/describe")
async def describe_plan_moves(
    plan_data: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Convert a sequence of chess moves into a VERIFIED description of the plan.

    This uses actual chess analysis to understand what moves DO, not LLM guessing.

    Body:
    - fen: Starting position FEN
    - moves: List of moves in SAN notation (e.g., ["Nf3", "e4", "d4"])
    - user_playing_color: "white" or "black" - which color the user was playing in the game
    - turn_to_move: "white" or "black" - whose turn it is in this position
    - user_move: What the user actually played (the mistake)
    - best_move: What was the better move
    """
    fen = plan_data.get("fen")
    moves = plan_data.get("moves", [])
    plan_data.get("user_playing_color", "white")
    plan_data.get("turn_to_move", "white")
    user_move = plan_data.get("user_move", "")
    best_move = plan_data.get("best_move", "")

    if not fen or not moves:
        return {"error": "Missing fen or moves", "plan_description": ""}

    # Use VERIFIED chess analysis instead of LLM guessing
    try:
        from plan_interpretation_service import generate_reflection_from_plan

        result = generate_reflection_from_plan(
            fen=fen,
            plan_moves=moves,
            user_move=user_move,
            best_move=best_move,
            eval_change=plan_data.get("eval_change", 0.0)
        )

        return {
            "plan_description": result.get("thought", f"I was thinking about: {' '.join(moves)}"),
            "moves": moves,
            "fen": fen,
            "behavioral_tags": result.get("behavioral_tags", []),
            "verified": result.get("verified", False),
            "interpretation": result.get("plan_interpretation", {}),
        }
    except Exception as e:
        logger.error(f"Error interpreting plan: {e}")
        # Fallback: just list the moves
        moves_str = " ".join([
            f"{i//2 + 1}. {moves[i]}" if i % 2 == 0 else moves[i]
            for i in range(len(moves))
        ])
        return {
            "plan_description": f"I was thinking about playing: {moves_str}",
            "moves": moves,
            "fen": fen,
            "error": str(e)
        }


@router.post("/training/milestone/reflect")
async def save_milestone_reflection(
    game_id: str,
    move_number: int,
    reflection_data: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Save reflection for a SPECIFIC position/milestone.

    Body:
    - selected_tags: List of contextual tags (e.g., "missed_threat", "time_pressure")
    - user_plan: What the user was thinking/planning (free text)
    - understood: Whether user understood the explanation
    - fen: Position FEN
    """
    from training_profile_service import save_position_reflection

    result = await save_position_reflection(db, user.user_id, game_id, move_number, reflection_data)
    return result


@router.get("/training/last-game-for-reflection")
async def get_last_game_for_reflection(user: User = Depends(get_current_user)):
    """
    Get the user's last analyzed game ID for reflection.
    """
    # Find last analyzed game
    last_analysis = await db.game_analyses.find_one(
        {"user_id": user.user_id},
        {"game_id": 1},
        sort=[("analyzed_at", -1)]
    )

    if not last_analysis:
        return {"game_id": None, "error": "No analyzed games found"}

    return {"game_id": last_analysis["game_id"]}


@router.get("/training/phase-progress")
async def get_phase_progress_endpoint(user: User = Depends(get_current_user)):
    """
    Get user's progress within their current training phase.

    Returns:
    - games_in_phase: How many games analyzed
    - progress_percent: Overall progress toward graduation
    - clean_games: Games without target pattern errors
    - improvement_percent: Pattern reduction percentage
    - trend: "improving" | "stable" | "regressing"
    - ready_to_graduate: Boolean
    """
    from training_profile_service import get_phase_progress

    result = await get_phase_progress(db, user.user_id)
    return result


@router.get("/training/reflection-history")
async def get_reflection_history_endpoint(user: User = Depends(get_current_user)):
    """
    Get user's reflection history with pattern evolution.

    Returns:
    - reflections: List of past reflections
    - tag_counts: How often each issue was identified
    - top_patterns: Most common patterns
    - user_plans: What user wrote during reflections
    """
    from training_profile_service import get_reflection_history

    result = await get_reflection_history(db, user.user_id, limit=50)
    return result


@router.get("/training/ai-insights")
async def get_ai_insights(user: User = Depends(get_current_user)):
    """
    Get AI-powered analysis of user's thinking patterns.

    Analyzes:
    - Common themes in their written plans
    - Recurring patterns in their mistakes
    - Personalized suggestions based on their data
    """
    from training_profile_service import generate_personalized_suggestions

    suggestion_data = await generate_personalized_suggestions(db, user.user_id)

    if not suggestion_data.get("ready_for_ai"):
        return suggestion_data

    # Use GPT to generate insights
    try:
        from llm_helper import LlmChat, UserMessage
        import os

        api_key = os.environ.get("EMERGENT_LLM_KEY", OPENAI_API_KEY)

        chat = LlmChat(
            api_key=api_key,
            session_id=f"insights_{os.urandom(8).hex()}",
            system_message="You are a chess coach analyzing a player's thinking patterns. Be specific, reference their actual words, and give actionable advice."
        ).with_model("openai", "gpt-4o-mini")

        response = await chat.send_message(UserMessage(text=suggestion_data["prompt"]))

        return {
            "has_insights": True,
            "ai_analysis": response,
            "context": suggestion_data["context"],
        }
    except Exception as e:
        logger.error(f"Error generating AI insights: {e}")
        return {
            "has_insights": False,
            "error": "Could not generate AI insights",
            "context": suggestion_data.get("context", {}),
        }


# =============================================================================
# SECTION C: Puzzle validation + progress
# =============================================================================

@router.post("/training/puzzle/validate")
async def validate_puzzle_answer(
    data: dict,
    user: User = Depends(get_current_user)
):
    """
    Validate user's answer to a puzzle.

    Request body:
    - puzzle_id: str
    - user_answer: str (move in SAN notation)
    - correct_move: str
    - fen: str

    Returns feedback with explanation and teaching point.
    """
    from interactive_training_service import validate_puzzle_answer as validate_answer

    result = await validate_answer(
        db,
        user.user_id,
        data.get("puzzle_id"),
        data.get("user_answer"),
        data.get("correct_move"),
        data.get("fen")
    )

    # Update puzzle progression rating
    if result.get("correct") is not None:
        from puzzle_progression_service import record_puzzle_attempt

        difficulty = data.get("difficulty", "intermediate")
        progression = await record_puzzle_attempt(
            db,
            user.user_id,
            data.get("puzzle_id", "unknown"),
            difficulty,
            result.get("correct", False)
        )

        # Include progression info in result
        result["progression"] = {
            "old_rating": progression["old_rating"],
            "new_rating": progression["new_rating"],
            "rating_change": progression["rating_change"],
            "leveled_up": progression["leveled_up"],
            "new_level": progression["new_level"] if progression["leveled_up"] else None,
            "current_streak": progression["current_streak"],
            "new_achievements": progression["new_achievements"]
        }

    return result


@router.get("/training/puzzle-progress")
async def get_puzzle_progress(user: User = Depends(get_current_user)):
    """
    Get user's puzzle progression data including rating, level, and stats.
    """
    from puzzle_progression_service import get_user_puzzle_progress

    progress = await get_user_puzzle_progress(db, user.user_id)
    return progress


@router.get("/training/puzzle-difficulty-recommendation")
async def get_puzzle_difficulty(user: User = Depends(get_current_user)):
    """
    Get recommended puzzle difficulty range for the user.
    """
    from puzzle_progression_service import get_recommended_puzzle_difficulty

    recommendation = await get_recommended_puzzle_difficulty(db, user.user_id)
    return recommendation


@router.get("/training/puzzle-leaderboard")
async def get_puzzle_leaderboard_endpoint(limit: int = 20):
    """
    Get global puzzle rating leaderboard.
    """
    from puzzle_progression_service import get_puzzle_leaderboard

    leaderboard = await get_puzzle_leaderboard(db, limit)
    return {"leaderboard": leaderboard}


@router.get("/training/weakness-patterns")
async def get_weakness_patterns(user: User = Depends(get_current_user)):
    """
    Get analysis of user's weakness patterns.

    Identifies:
    - Weakest game phase (opening/middlegame/endgame)
    - Common mistake types
    - Training recommendations
    """
    from interactive_training_service import get_user_weakness_patterns

    patterns = await get_user_weakness_patterns(db, user.user_id)

    return patterns


@router.get("/training/openings")
async def get_user_openings(user: User = Depends(get_current_user)):
    """
    Get user's most played openings with mastery levels.

    For future opening trainer feature.
    """
    from interactive_training_service import get_user_openings

    openings = await get_user_openings(db, user.user_id)

    return {
        "openings": openings,
        "total": len(openings)
    }


@router.get("/training/openings/stats")
async def get_opening_stats(user: User = Depends(get_current_user)):
    """
    Get detailed statistics on user's most-played openings with training content availability.
    Includes community comparison showing how user's accuracy compares to others at their rating level.
    """
    from opening_trainer_service import get_user_opening_stats, enrich_with_community_comparison

    stats = await get_user_opening_stats(db, user.user_id)

    # Enrich with community comparison data
    stats = await enrich_with_community_comparison(db, user.user_id, stats)

    return {
        "openings": stats,
        "total": len(stats)
    }


@router.get("/training/openings/{opening_key}")
async def get_opening_training_content(opening_key: str, user: User = Depends(get_current_user)):
    """
    Get training content for a specific opening including:
    - Key variations and move orders
    - Common traps (to set and avoid)
    - Typical plans and ideas
    - User's mistakes in this opening
    """
    from opening_trainer_service import get_opening_training_content

    content = await get_opening_training_content(db, user.user_id, opening_key)

    return content


@router.get("/training/openings/{opening_key}/quiz")
async def get_opening_quiz(opening_key: str, user: User = Depends(get_current_user)):
    """
    Generate quiz questions for an opening to test user's knowledge.
    """
    from opening_trainer_service import get_opening_quiz

    questions = await get_opening_quiz(db, user.user_id, opening_key)

    return {
        "opening": opening_key,
        "questions": questions
    }


@router.post("/training/openings/{opening_key}/quiz/submit")
async def submit_opening_quiz(opening_key: str, request: Request, user: User = Depends(get_current_user)):
    """
    Submit quiz answers and get score with feedback.
    """
    data = await request.json()
    answers = data.get("answers", [])

    from opening_trainer_service import get_opening_quiz, OPENINGS_DATABASE

    opening = OPENINGS_DATABASE.get(opening_key)
    if not opening:
        raise HTTPException(status_code=404, detail="Opening not found")

    # Get questions to compare answers
    questions = await get_opening_quiz(db, user.user_id, opening_key)

    # Score the quiz
    results = []
    correct_count = 0
    total = len(questions)

    for i, q in enumerate(questions):
        user_answer = answers[i] if i < len(answers) else None

        is_correct = False
        if q["type"] == "position":
            # Check if user found the winning move
            is_correct = user_answer and user_answer.lower() == q["correct_move"].lower()
        elif q["type"] == "concept":
            # Check if answer is in the options
            is_correct = user_answer in q.get("options", [q["correct_answer"]])
        elif q["type"] == "move_order":
            # Check if user got the main line
            is_correct = user_answer and user_answer.lower().replace(" ", "") == q["correct_answer"].lower().replace(" ", "")

        if is_correct:
            correct_count += 1

        results.append({
            "question_index": i,
            "type": q["type"],
            "user_answer": user_answer,
            "correct_answer": q.get("correct_move") or q.get("correct_answer"),
            "is_correct": is_correct,
            "explanation": q.get("explanation", "")
        })

    # Calculate score and mastery level
    score = (correct_count / total * 100) if total > 0 else 0

    if score >= 90:
        mastery_feedback = "Excellent! You've mastered this opening."
        new_level = "mastered"
    elif score >= 70:
        mastery_feedback = "Good job! Keep practicing the traps."
        new_level = "practiced"
    elif score >= 50:
        mastery_feedback = "Getting there. Focus on the key ideas."
        new_level = "learning"
    else:
        mastery_feedback = "This opening needs more study. Let's practice it in games!"
        new_level = "introduced"

    # Update user progress
    await db.user_opening_progress.update_one(
        {"user_id": user.user_id, "opening_name": opening["name"]},
        {
            "$set": {
                "last_quiz_score": score,
                "last_quiz_date": datetime.now(timezone.utc).isoformat(),
                "mastery_level": new_level
            },
            "$push": {
                "quiz_scores": {
                    "score": score,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "questions_count": total,
                    "correct_count": correct_count
                }
            }
        },
        upsert=True
    )

    return {
        "opening": opening_key,
        "opening_name": opening["name"],
        "score": score,
        "correct": correct_count,
        "total": total,
        "mastery_level": new_level,
        "mastery_feedback": mastery_feedback,
        "results": results
    }


@router.get("/training/opening-progress")
async def get_opening_progress(user: User = Depends(get_current_user)):
    """
    Get combined opening progress: coach lessons + real game stats.
    Used by Lab page Habits tab to show complete opening journey.
    """
    from opening_trainer_service import get_user_opening_stats

    # Get coach lesson progress
    coach_progress = await db.user_opening_progress.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(50)

    # Get real game stats
    real_stats = await get_user_opening_stats(db, user.user_id)

    # Create lookup by name
    real_stats_by_name = {}
    for stat in real_stats:
        name_key = stat.get("name", "").lower().strip()
        real_stats_by_name[name_key] = stat

    # Combine the data
    combined = []
    seen_openings = set()

    # First, add all coach-taught openings with their real game stats
    for progress in coach_progress:
        opening_name = progress.get("opening_name", "")
        name_key = opening_name.lower().strip()
        seen_openings.add(name_key)

        # Find matching real game stats
        real = real_stats_by_name.get(name_key, {})

        # Get loss phase data
        loss_phases = progress.get("loss_phases", {})
        total_losses = progress.get("total_losses", 0)
        dominant_loss_phase = None
        if loss_phases and total_losses > 0:
            # Find which phase has the most losses
            max_losses = 0
            for phase, count in loss_phases.items():
                if count > max_losses:
                    max_losses = count
                    dominant_loss_phase = phase

        combined.append({
            "opening_name": opening_name,
            "mastery_level": progress.get("mastery_level", "unknown"),
            "times_practiced": progress.get("times_practiced", 0),
            "times_applied_in_games": progress.get("times_applied_in_games", 0),  # Theory applied tracking
            "correct_applications": progress.get("correct_applications", 0),
            "last_practiced": progress.get("last_practiced_at"),
            "last_quiz_score": progress.get("last_quiz_score"),
            "coach_taught": True,
            "real_games": real.get("games_played", 0),
            "real_win_rate": real.get("win_rate", 0),
            "real_accuracy": real.get("avg_accuracy", 0),
            "needs_work": real.get("games_played", 0) > 2 and real.get("win_rate", 0) < 50,
            "loss_phases": loss_phases,  # {"opening": 2, "middlegame": 5, "endgame": 1}
            "total_losses": total_losses,
            "dominant_loss_phase": dominant_loss_phase  # "middlegame" - where user loses most
        })

    # Add openings played in real games but not taught by coach
    for stat in real_stats:
        name_key = stat.get("name", "").lower().strip()
        if name_key not in seen_openings and stat.get("games_played", 0) >= 2:
            combined.append({
                "opening_name": stat.get("name", "Unknown"),
                "mastery_level": "unknown",
                "times_practiced": 0,
                "coach_taught": False,
                "real_games": stat.get("games_played", 0),
                "real_win_rate": stat.get("win_rate", 0),
                "real_accuracy": stat.get("avg_accuracy", 0),
                "needs_work": stat.get("win_rate", 0) < 50
            })

    # Sort: needs_work first, then by real_games
    combined.sort(key=lambda x: (-int(x.get("needs_work", False)), -x.get("real_games", 0)))

    return {
        "progress": combined,
        "total_taught": len([c for c in combined if c.get("coach_taught")]),
        "total_learned": len([c for c in combined if c.get("mastery_level") in ["mastered", "comfortable", "practiced"]]),
        "total_played": len([c for c in combined if c.get("real_games", 0) > 0]),
        "needs_attention": len([c for c in combined if c.get("needs_work")])
    }



@router.get("/training/openings-database")
async def get_openings_database():
    """
    Get the full openings database for reference/browsing.
    """
    from opening_trainer_service import OPENINGS_DATABASE

    # Format for frontend consumption
    openings = []
    for key, data in OPENINGS_DATABASE.items():
        openings.append({
            "key": key,
            "name": data["name"],
            "eco": data.get("eco", ""),
            "color": data["color"],
            "description": data["description"],
            "main_line": data["main_line"],
            "variations_count": len(data.get("common_variations", [])),
            "traps_count": len(data.get("traps", []))
        })

    return {
        "openings": openings,
        "total": len(openings)
    }


# =============================================================================
# SECTION D: Tricks/traps
# =============================================================================

@router.get("/training/tricks")
async def get_all_tricks():
    """
    Get all traps in the trick library with metadata.
    """
    from trick_library_service import get_all_traps, get_trap_statistics, TRAP_CATEGORIES

    traps = get_all_traps()
    stats = get_trap_statistics()

    return {
        "traps": traps,
        "categories": TRAP_CATEGORIES,
        "statistics": stats
    }


@router.get("/training/tricks/categories")
async def get_trick_categories():
    """
    Get all trap categories.
    """
    from trick_library_service import TRAP_CATEGORIES, get_traps_by_category

    categories = []
    for key, cat_data in TRAP_CATEGORIES.items():
        traps = get_traps_by_category(key)
        categories.append({
            "key": key,
            "name": cat_data["name"],
            "description": cat_data["description"],
            "trap_count": len(traps),
            "trap_keys": cat_data["traps"]
        })

    return {"categories": categories}


@router.post("/training/tricks/record-attempt")
async def record_trap_attempt_endpoint(request: Request, data: dict, user: User = Depends(get_current_user)):
    """
    Record a user's attempt on a trap practice mode.
    """
    from trap_stats_service import record_trap_attempt

    trap_key = data.get("trap_key")
    mode = data.get("mode")
    success = data.get("success")
    details = data.get("details", {})

    if not trap_key or not mode or success is None:
        raise HTTPException(status_code=400, detail="Missing required fields: trap_key, mode, success")

    if mode not in ["execution", "avoidance", "recognition"]:
        raise HTTPException(status_code=400, detail="Invalid mode")

    result = await record_trap_attempt(db, user.user_id, trap_key, mode, success, details)
    return result


@router.get("/training/tricks/stats")
async def get_user_trap_stats_endpoint(request: Request, user: User = Depends(get_current_user)):
    """Get comprehensive trap statistics for the current user."""
    from trap_stats_service import get_user_trap_stats
    stats = await get_user_trap_stats(db, user.user_id)
    return stats


@router.get("/training/tricks/recommendations")
async def get_trap_recommendations_endpoint(request: Request, user: User = Depends(get_current_user), limit: int = 5):
    """Get personalized trap recommendations for the current user."""
    from trap_stats_service import get_recommended_traps
    recommendations = await get_recommended_traps(db, user.user_id, limit)
    return {"recommendations": recommendations}


@router.get("/training/tricks/global-stats")
async def get_global_trap_stats_endpoint(request: Request):
    """Get global trap statistics across all users."""
    from trap_stats_service import get_global_trap_stats
    stats = await get_global_trap_stats(db)
    return stats


@router.get("/training/tricks/{trap_key}")
async def get_trick_details(trap_key: str):
    """
    Get detailed information about a specific trap.
    """
    from trick_library_service import get_trap_by_key

    trap = get_trap_by_key(trap_key)
    if not trap:
        raise HTTPException(status_code=404, detail="Trap not found")

    return trap


@router.get("/training/tricks/{trap_key}/practice")
async def get_trick_for_practice(trap_key: str, mode: str = "execution"):
    """
    Get a trap formatted for practice mode.

    Modes:
    - execution: Player tries to execute the trap (find the winning move)
    - avoidance: Player tries to avoid falling into the trap
    - recognition: Player identifies if there's a trap in the position
    """
    from trick_library_service import get_trap_for_practice

    if mode not in ["execution", "avoidance", "recognition"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use: execution, avoidance, recognition")

    practice_data = get_trap_for_practice(trap_key, mode)
    if not practice_data:
        raise HTTPException(status_code=404, detail="Trap not found")

    return practice_data


@router.post("/training/tricks/validate-avoidance")
async def validate_avoidance_move(data: dict):
    """
    Validate a move in avoidance mode.

    Checks if the user's move avoids the trap or falls into it.
    Uses Stockfish to evaluate if the move is safe.
    """
    import chess
    from stockfish_service import StockfishEngine

    fen = data.get("fen")
    user_move = data.get("user_move")
    data.get("trap_key")
    winning_move = data.get("winning_move")  # The trap move opponent would play if allowed

    if not fen or not user_move:
        raise HTTPException(status_code=400, detail="Missing fen or user_move")

    try:
        board = chess.Board(fen)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid FEN")

    # Parse user's move
    try:
        move_obj = board.parse_san(user_move)
        move_san = board.san(move_obj)
    except Exception:
        return {"valid": False, "fell_into_trap": False, "message": f"Invalid move: {user_move}"}

    # Make the user's move
    board.push(move_obj)
    new_fen = board.fen()

    # Check if opponent can still play the winning/trap move after user's move
    try:
        if winning_move:
            try:
                trap_move_obj = board.parse_san(winning_move)
                # If the trap move is still legal, check if it's still winning
                if trap_move_obj in board.legal_moves:
                    pass
            except Exception:
                pass

        # Use Stockfish to evaluate the position after user's move
        engine = StockfishEngine()
        engine.start()

        try:
            # First, evaluate the position BEFORE the user's move
            board_before = chess.Board(fen)
            eval_before, mate_before = engine.evaluate_position(board_before, depth=12)

            # Now evaluate AFTER the user's move
            eval_after, mate_after = engine.evaluate_position(board, depth=12)

            # Determine who is the victim
            is_victim_white = data.get("user_color", "black") == "white"

            # Adjust evals to be from the victim's perspective
            # Positive = good for victim, Negative = bad for victim
            if is_victim_white:
                victim_eval_before = eval_before
                victim_eval_after = eval_after
            else:
                victim_eval_before = -eval_before
                victim_eval_after = -eval_after

            # Calculate how much the position changed
            eval_change = victim_eval_after - victim_eval_before

            # Check for mate threats after the move
            if mate_after is not None:
                if (is_victim_white and mate_after < 0) or (not is_victim_white and mate_after > 0):
                    # User is getting mated - fell into trap!
                    return {
                        "valid": True,
                        "fell_into_trap": True,
                        "is_safe": False,
                        "evaluation": eval_after,
                        "mate_in": mate_after,
                        "message": f"Oops! After {move_san}, you're getting mated in {abs(mate_after)}!",
                        "new_fen": new_fen
                    }

            # If there was a mate threat BEFORE and now there isn't, the move avoided the trap!
            if mate_before is not None and mate_after is None:
                return {
                    "valid": True,
                    "fell_into_trap": False,
                    "is_safe": True,
                    "evaluation": eval_after,
                    "message": f"Excellent! {move_san} avoids the checkmate threat!",
                    "new_fen": new_fen
                }

            # If the position got significantly WORSE (>200cp loss), they fell into trap
            if eval_change < -200:
                return {
                    "valid": True,
                    "fell_into_trap": True,
                    "is_safe": False,
                    "evaluation": eval_after,
                    "eval_change": eval_change,
                    "message": f"That move makes things worse! After {move_san}, your position deteriorated.",
                    "new_fen": new_fen
                }

            # If they're still in a very bad position (>500cp worse) AND didn't improve
            if victim_eval_after < -500 and eval_change < 100:
                return {
                    "valid": True,
                    "fell_into_trap": True,
                    "is_safe": False,
                    "evaluation": eval_after,
                    "message": f"Your position is still critical. {move_san} doesn't fully avoid the danger.",
                    "new_fen": new_fen
                }

            # Move is safe - position either improved or stayed stable
            if eval_change > 50:
                return {
                    "valid": True,
                    "fell_into_trap": False,
                    "is_safe": True,
                    "evaluation": eval_after,
                    "message": f"Great! {move_san} improves your position and avoids the trap!",
                    "new_fen": new_fen
                }
            else:
                return {
                    "valid": True,
                    "fell_into_trap": False,
                    "is_safe": True,
                    "evaluation": eval_after,
                    "message": f"Good! {move_san} is a solid defensive move.",
                    "new_fen": new_fen
                }

        finally:
            engine.stop()

    except Exception as e:
        logger.error(f"Error validating avoidance move: {e}")
        return {"valid": True, "fell_into_trap": False, "is_safe": True, "message": "Move accepted", "new_fen": new_fen}


@router.post("/training/tricks/validate-recognition")
async def validate_recognition_answer(data: dict):
    """
    Validate user's answer in recognition mode.

    User must identify:
    1. Whether there's a trap (yes/no)
    2. What the winning move is (if yes)
    """
    trap_key = data.get("trap_key")
    user_answer_has_trap = data.get("has_trap")  # Boolean: does user think there's a trap?
    user_winning_move = data.get("winning_move")  # What move does user think wins?

    from trick_library_service import get_trap_by_key

    trap = get_trap_by_key(trap_key)
    if not trap:
        raise HTTPException(status_code=404, detail="Trap not found")

    correct_has_trap = True  # All positions in our DB have traps
    correct_winning_move = trap.get("winning_move", "")

    # Check if user correctly identified trap presence
    recognized_trap = user_answer_has_trap == correct_has_trap

    # Check if user found the correct winning move (normalize notation)
    found_move = False
    if user_winning_move and correct_winning_move:
        # Normalize move notation for comparison
        user_move_clean = user_winning_move.replace("+", "").replace("#", "").replace("=", "")
        correct_move_clean = correct_winning_move.replace("+", "").replace("#", "").replace("=", "")
        found_move = user_move_clean.lower() == correct_move_clean.lower()

    # Calculate score
    if recognized_trap and found_move:
        score = "perfect"
        message = f"Excellent! You correctly identified the trap and found {correct_winning_move}!"
    elif recognized_trap and not user_winning_move:
        score = "good"
        message = f"Good! You spotted the danger. The winning move is {correct_winning_move}."
    elif recognized_trap and not found_move:
        score = "partial"
        message = f"You spotted the trap but missed the key move. The winning move is {correct_winning_move}."
    else:
        score = "missed"
        message = f"There IS a trap here! The winning move is {correct_winning_move}."

    return {
        "correct_has_trap": correct_has_trap,
        "correct_winning_move": correct_winning_move,
        "recognized_trap": recognized_trap,
        "found_winning_move": found_move,
        "score": score,
        "message": message,
        "explanation": trap.get("explanation", ""),
        "why_it_works": trap.get("why_it_works", ""),
        "key_squares": trap.get("key_squares", [])
    }


@router.get("/training/tricks/opening/{opening_name}")
async def get_tricks_for_opening(opening_name: str):
    """
    Get traps relevant to a specific opening.
    """
    from trick_library_service import get_traps_by_opening, get_recommended_traps_for_opening

    # Get direct matches
    direct_traps = get_traps_by_opening(opening_name)

    # Get recommendations
    recommendations = get_recommended_traps_for_opening(opening_name)

    return {
        "opening": opening_name,
        "traps": direct_traps,
        "recommendations": recommendations
    }


@router.get("/training/tricks/difficulty/{difficulty}")
async def get_tricks_by_difficulty(difficulty: str):
    """
    Get traps by difficulty level (beginner, intermediate, advanced).
    """
    from trick_library_service import get_traps_by_difficulty

    if difficulty not in ["beginner", "intermediate", "advanced"]:
        raise HTTPException(status_code=400, detail="Invalid difficulty. Use: beginner, intermediate, advanced")

    traps = get_traps_by_difficulty(difficulty)

    return {
        "difficulty": difficulty,
        "traps": traps,
        "count": len(traps)
    }


@router.get("/training/tricks/{trap_key}/leaderboard")
async def get_trap_leaderboard_endpoint(request: Request, trap_key: str, mode: str = "execution"):
    """Get leaderboard for a specific trap."""
    from trap_stats_service import get_trap_leaderboard

    if mode not in ["execution", "avoidance", "recognition"]:
        raise HTTPException(status_code=400, detail="Invalid mode")

    leaderboard = await get_trap_leaderboard(db, trap_key, mode)
    return {"trap_key": trap_key, "mode": mode, "leaderboard": leaderboard}


# =============================================================================
# SECTION E: Community puzzles
# =============================================================================

@router.post("/community/puzzles/share")
async def share_community_puzzle(request: Request, data: dict, user: User = Depends(get_current_user)):
    """Share a puzzle from user's games to the community."""
    from community_learning_service import share_puzzle
    result = await share_puzzle(db, user.user_id, data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/community/puzzles")
async def get_community_puzzles_endpoint(
    request: Request,
    difficulty: str = None,
    theme: str = None,
    opening: str = None,
    sort_by: str = "newest",
    skip: int = 0,
    limit: int = 20
):
    """Browse community puzzles with filtering."""
    from community_learning_service import get_community_puzzles

    # Get current user if authenticated
    user_id = None
    try:
        user = await get_current_user(request)
        user_id = user.user_id
    except Exception:
        pass

    result = await get_community_puzzles(
        db, user_id, difficulty, theme, opening, sort_by, skip, limit
    )
    return result


@router.post("/community/puzzles/{puzzle_id}/attempt")
async def attempt_community_puzzle_endpoint(
    request: Request,
    puzzle_id: str,
    data: dict,
    user: User = Depends(get_current_user)
):
    """Attempt to solve a community puzzle."""
    from community_learning_service import attempt_community_puzzle

    user_move = data.get("user_move")
    time_taken = data.get("time_taken")

    if not user_move:
        raise HTTPException(status_code=400, detail="Missing user_move")

    result = await attempt_community_puzzle(db, user.user_id, puzzle_id, user_move, time_taken)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/community/puzzles/{puzzle_id}/rate")
async def rate_community_puzzle_endpoint(
    request: Request,
    puzzle_id: str,
    data: dict,
    user: User = Depends(get_current_user)
):
    """Rate a community puzzle (1-5 stars)."""
    from community_learning_service import rate_puzzle

    rating = data.get("rating")
    if not rating or not isinstance(rating, int):
        raise HTTPException(status_code=400, detail="Missing or invalid rating (must be 1-5)")

    result = await rate_puzzle(db, user.user_id, puzzle_id, rating)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/community/stats")
async def get_community_stats_endpoint(request: Request):
    """Get overall community puzzle statistics."""
    from community_learning_service import get_community_stats
    stats = await get_community_stats(db)
    return stats


@router.get("/community/my-contributions")
async def get_my_contributions_endpoint(request: Request, user: User = Depends(get_current_user)):
    """Get current user's puzzle contributions."""
    from community_learning_service import get_user_contributions
    contributions = await get_user_contributions(db, user.user_id)
    return contributions


# =============================================================================
# SECTION F: Community training positions
# =============================================================================

@router.post("/training/extract-positions/{game_id}")
async def extract_training_positions_endpoint(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """Extract training-worthy positions from a V5 decrypted game."""
    from services.community_training_service import extract_training_positions
    positions = await extract_training_positions(db, game_id, user.user_id)
    return {
        "extracted": len(positions),
        "game_id": game_id,
        "positions": [{"position_id": p["position_id"], "pattern_type": p["pattern_type"], "cp_loss": p["cp_loss"]} for p in positions]
    }


@router.get("/training/community-feed")
async def get_training_feed_endpoint(
    limit: int = 10,
    pattern: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """Get mixed training feed: own positions + community positions. Optionally filter by pattern_type."""
    from services.community_training_service import get_training_feed
    return await get_training_feed(db, user.user_id, limit, pattern_filter=pattern)


class SolveAttemptRequest(BaseModel):
    position_id: str
    user_move: str
    time_taken_seconds: int = 0


@router.post("/training/solve-attempt")
async def record_solve_attempt_endpoint(
    data: SolveAttemptRequest,
    user: User = Depends(get_current_user)
):
    """Record a training position solve attempt."""
    from services.community_training_service import record_solve_attempt
    return await record_solve_attempt(
        db, user.user_id, data.position_id, data.user_move, data.time_taken_seconds
    )


@router.get("/training/pattern-stats")
async def get_pattern_stats_endpoint(
    user: User = Depends(get_current_user)
):
    """Get user's pattern-level solve stats."""
    from services.community_training_service import get_user_pattern_stats
    stats = await get_user_pattern_stats(db, user.user_id)
    return {"patterns": stats}


@router.get("/training/community-count")
async def get_community_count_endpoint():
    """Get total community training positions count."""
    from services.community_training_service import get_community_position_count
    count = await get_community_position_count(db)
    return {"count": count}


# =============================================================================
# SECTION G: Endgames
# =============================================================================

@router.get("/endgames/categories")
async def get_endgame_categories():
    """Return all endgame categories and lessons."""
    from services.endgame_theory_service import get_all_categories
    return {"categories": get_all_categories()}


@router.get("/endgames/lesson/{category_key}/{lesson_key}")
async def get_endgame_lesson(category_key: str, lesson_key: str):
    """Return a specific endgame lesson with positions (no answers)."""
    from services.endgame_theory_service import get_lesson
    lesson = get_lesson(category_key, lesson_key)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


class EndgameCheckMoveRequest(BaseModel):
    category_key: str
    lesson_key: str
    position_index: int
    user_move_uci: str


@router.post("/endgames/check-move")
async def check_endgame_move(req: EndgameCheckMoveRequest):
    """Check if the user's move is correct for the given endgame position."""
    from services.endgame_theory_service import check_move
    result = check_move(req.category_key, req.lesson_key, req.position_index, req.user_move_uci)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
