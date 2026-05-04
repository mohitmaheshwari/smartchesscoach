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
    "time_management":    {"name": "Clock Management",      "rule": "Track your time. If under 2 minutes, simplify the position."},
    "game_abandonment":   {"name": "Mental Discipline",     "rule": "Finish every game. Abandoning builds bad habits and hides the real lesson."},
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
    "time_management":   "Half your losses on time aren't chess problems — they're clock problems.",
    "game_abandonment":  "Finishing losing games teaches you more than winning easy ones.",
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


def _termination_display(termination: str, result: str) -> str:
    """Human-readable termination label."""
    labels = {
        "checkmate": "Checkmate",
        "resignation": "Resignation",
        "timeout": "Timeout",
        "abandonment": "Abandoned",
        "stalemate": "Stalemate",
        "draw_agreement": "Draw by agreement",
        "repetition": "Repetition",
        "insufficient": "Insufficient material",
    }
    base = labels.get(termination, "")
    if not base:
        return ""

    if result == "W":
        if termination == "checkmate":
            return "Won by checkmate"
        if termination == "resignation":
            return "Won by resignation"
        if termination == "timeout":
            return "Won on time"
        return f"Won — {base}"
    elif result == "L":
        if termination == "checkmate":
            return "Lost by checkmate"
        if termination == "resignation":
            return "Lost by resignation"
        if termination == "timeout":
            return "Lost on time"
        if termination == "abandonment":
            return "Abandoned"
        return f"Lost — {base}"
    else:
        return base


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

    # Human-readable behavior descriptions (not raw keys)
    BEHAVIOR_SENTENCE = {
        "ignore_threat": "You didn't check what your opponent was threatening.",
        "piece_safety": "You left a piece undefended.",
        "calculation_depth": "You didn't calculate deep enough.",
        "missed_tactic": "You missed a tactic that was there.",
        "tactical_oversight": "You didn't check your opponent's reply.",
        "king_safety": "Your king wasn't safe.",
        "time_pressure": "You rushed and made mistakes under time pressure.",
        "conversion": "You got creative when you should have kept it simple.",
        "pawn_structure": "You weakened your pawn structure.",
        "piece_activity": "Your pieces were passive.",
    }
    behavior_text = BEHAVIOR_SENTENCE.get(behavior_key, "")

    # ═══ PRIORITY 2: LOST WINNING POSITION ═══
    if lost_winning:
        moment = f"Winning until move {collapse_move}" if collapse_move else "Had the advantage"
        if behavior_text:
            return f"{moment}. {behavior_text}"
        return f"{moment}, then the position slipped away."

    if was_winning and is_draw:
        if behavior_text:
            return f"Winning position but drew. {behavior_text}"
        return "Had a winning position but couldn't convert."

    # ═══ PRIORITY 3: SINGLE CRITICAL MOVE ═══
    if not user_won and not is_draw and blunders == 1 and critical:
        mn = critical.get("move_number", "?")
        if behavior_text:
            return f"One mistake on move {mn} cost the game. {behavior_text}"
        return f"One mistake on move {mn} {phase} decided the game."

    # ═══ PRIORITY 4: PATTERN IN THIS GAME ═══
    if pattern_active and not user_won and behavior_text:
        return f"{behavior_text} This keeps happening."

    # ═══ PRIORITY 5: BLUNDER COUNT ═══
    if blunders >= 3:
        if rushed >= 2:
            return "Playing too fast. Mistakes came from rushing, not from chess."
        if behavior_text:
            return f"Several mistakes {phase}. {behavior_text}"
        return f"Rough game — {blunders} blunders {phase}."

    if blunders >= 2:
        if behavior_text:
            return f"Two critical moments {phase}. {behavior_text}"
        return f"Two blunders {phase} turned the game."

    # Won with mistakes
    if user_won and blunders == 1:
        mn = critical.get("move_number", "?") if critical else "?"
        return f"You won, but slipped on move {mn}. The rest was solid."

    if user_won and blunders >= 2:
        return "You won, but your opponent missed chances. Next opponent might not."

    # ═══ PRIORITY 6: GENERAL ═══
    if user_won and blunders == 0 and mistakes <= 2:
        return "Clean game. No major errors."

    if is_draw and blunders == 0:
        return "Solid, balanced game. Well handled."

    if user_won:
        return "Good result. You controlled the game."

    if not user_won and not is_draw and blunders == 0:
        return "No blunders, but your opponent outplayed you positionally."

    if not user_won and not is_draw:
        if behavior_text:
            return f"{behavior_text}"
        return f"A tough game with lessons {phase}."

    if is_draw:
        return "A balanced fight."

    return ""


async def _batch_generate_game_stories(games: list) -> dict:
    """
    Generate unique stories for multiple games in ONE LLM call.
    Returns {game_id: story} dict.
    """
    if not games:
        return {}

    try:
        from llm_service import call_llm
    except ImportError:
        return {}

    # Build compact context for each game
    game_contexts = []
    for g in games:
        result = g.get("result", "?")
        result_word = "won" if result == "W" else ("drew" if result == "D" else "lost")
        det_story = g.get("behavior", "")

        # Find critical moment from cognitive_gaps
        gaps = g.get("cognitive_gaps", [])
        dominant = gaps[0] if gaps else ""

        game_contexts.append(
            f"GAME {g['game_id'][:8]}: {result_word} vs {g.get('opponent', '?')}. "
            f"Opening: {g.get('opening', '?')}. "
            f"Blunders: {g.get('blunders', 0)}. Was winning: {g.get('was_winning', False)}. "
            f"Issue: {dominant.replace('_', ' ') if dominant else 'none'}. "
            f"Draft: {det_story}"
        )

    user_msg = "Write a unique 1-2 sentence story for each game below. Return as:\nGAME_ID: story\n\n" + "\n".join(game_contexts)

    system = """You write chess game summaries. Short. Unique. Coach voice.

STRICT RULES:
- MAX 20 words per game. Two sentences maximum.
- About BEHAVIOR (why they lost), not moves or squares.
- NO advice. NO "focus on" or "try to" or "in future games."
- NO scores, percentages, or ratings.
- Each story MUST sound different from the others.
- Won cleanly → brief praise. Lost → what went wrong (behavior, not move).

FORMAT: Each line starts with the 8-character game ID, then colon, then the story. One line per game. Nothing else."""

    try:
        response = await call_llm(system, user_msg, model="gpt-4o-mini")

        # Parse response into {game_id: story}
        result = {}
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            # Find the game ID prefix
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            gid_prefix = parts[0].strip().replace("GAME ", "").replace("GAME_", "").replace("**", "").strip()
            story = parts[1].strip().strip('"').strip("'").strip("*")

            if not story or len(story) < 5:
                continue

            # Match to actual game_id (flexible — prefix match)
            for g in games:
                if g["game_id"][:8] == gid_prefix or g["game_id"].startswith(gid_prefix) or gid_prefix in g["game_id"]:
                    # Enforce strict word limit
                    words = story.split()
                    if len(words) > 25:
                        story = " ".join(words[:20])
                        last_period = story.rfind(".")
                        if last_period > 10:
                            story = story[:last_period + 1]
                        elif not story.endswith("."):
                            story += "."
                    result[g["game_id"]] = story
                    break

        logger.info(f"[LAB] Batch LLM generated {len(result)} stories from {len(games)} games")
        return result
    except Exception as e:
        logger.warning(f"Batch LLM game stories failed: {e}")
        return {}


# =============================================================================
# SECTION A: Lab pick + puzzles
# =============================================================================

# Pattern → human language (short for home, detail for lab).
# Voice: coach, not accuser. Frame each gap as a habit to build, not a flaw —
# the home card is the first thing a user sees after a losing session.
COACHING_DIAGNOSIS = {
    "piece_safety":       {"short": "Let's make piece safety the first check.",         "detail": "Before each move, scan your pieces: which are defended, which aren't. That one habit fixes most hangs."},
    "ignore_threat":      {"short": "Start with: what did they just threaten?",          "detail": "Every move your opponent makes is a threat or a setup. Naming it first is how we stop walking into it."},
    "calculation_depth":  {"short": "One move deeper is where games turn.",              "detail": "A move isn't done until you've pictured their best reply. That's where the real decision lives."},
    "missed_tactic":      {"short": "Checks, captures, threats — every move.",           "detail": "Winning tactics hide inside forcing moves. Scanning them every turn is the habit that catches them."},
    "tactical_oversight": {"short": "Pick the move, then pause for their reply.",        "detail": "After choosing, take one more breath: what's their sharpest response? That pause catches most mistakes."},
    "king_safety":        {"short": "Safety first, attack second.",                      "detail": "Before launching anything, confirm your king has cover and escape squares. Attacks without safety come back."},
    "time_pressure":      {"short": "Spend time where it decides the game.",             "detail": "Move quickly when the answer is clear. Save the clock for critical positions — that's where thought pays."},
    "time_management":    {"short": "Let's budget the clock for decisions.",             "detail": "Games are won on the board, not the clock. Spend time choosing, not on moves you already know."},
    "conversion":         {"short": "When ahead, simplify.",                             "detail": "Winning positions reward clean technique, not creativity. Trade, defuse, squeeze — don't go hunting for flashy."},
    "endgame_technique":  {"short": "Endgames are a skill we can build.",                "detail": "Endgames reward technique over tactics. Active king, passed pawns, clean decisions — one step at a time."},
    "pawn_structure":     {"short": "Every pawn move is permanent.",                     "detail": "Before pushing a pawn, ask what square this weakens and whether you can defend it later."},
    "game_abandonment":   {"short": "Let's play every game to the end.",                 "detail": "The sharpest lessons come from defending worse positions. Resigning early skips the learning."},
}

# Deeper "why this matters" line shown alongside the diagnosis. Coach voice —
# explain the principle, frame the fix as a habit, no accusations.
COACHING_INSIGHTS = {
    "piece_safety":       "This isn't about seeing farther. It's the one-second check before committing — that's the muscle we're building.",
    "ignore_threat":      "Threat awareness comes before calculation. Name what they're doing first; plan your reply second.",
    "calculation_depth":  "Seeing one move ahead is natural. Seeing two is trained. The second move is where games are decided.",
    "missed_tactic":      "Tactics rarely hide. They live inside checks, captures, and threats — scanning those every turn is the habit.",
    "tactical_oversight": "The move feels done the moment you choose it. The pause that follows — picturing their reply — is where the mistake gets caught.",
    "king_safety":        "Attack and defense share one rule: check the king first. Without that, every attack carries its own punishment.",
    "time_pressure":      "Clock trouble is a budgeting problem, not a speed problem. Move fast on clear positions so the hard ones get their minutes.",
    "time_management":    "Time well spent goes into decisions, not into moves you already know. Reclaim that budget for the critical turns.",
    "conversion":         "Winning positions reward clean technique — trades, defusing threats, simple plans. The creative move is the opponent's escape route.",
    "endgame_technique":  "Endgames are a learnable skill, not a personality trait. King activity and passed pawns, practiced a little at a time, close these out.",
    "pawn_structure":     "Pawns don't come back. Every push is a permanent trade: a square gained somewhere for a weakness somewhere else.",
    "game_abandonment":   "The hardest positions teach the most. Playing them out — even when they look lost — is how defensive skill actually forms.",
}

COACHING_RULES = {
    "piece_safety":       {"name": "Piece Safety Check",    "rule": "Before every move, ask: is anything I own under attack?"},
    "ignore_threat":      {"name": "Threat Awareness",      "rule": "Before every move, ask: what is my opponent attacking right now?"},
    "calculation_depth":  {"name": "Calculation Depth",     "rule": "Don't stop at your move. Ask: what will they do next?"},
    "missed_tactic":      {"name": "Tactics Scan",          "rule": "Before deciding, check: captures, checks, threats — in that order."},
    "tactical_oversight": {"name": "Opponent Response",     "rule": "After picking your move, pause. What can your opponent do?"},
    "king_safety":        {"name": "King Safety First",     "rule": "Before attacking, check: is my king safe?"},
    "time_pressure":      {"name": "Clock Discipline",      "rule": "When under 2 minutes, play simple moves. No complications."},
    "time_management":    {"name": "Clock Management",      "rule": "Track your time. Spend it on critical moves, not obvious ones."},
    "conversion":         {"name": "Winning Discipline",    "rule": "When ahead, trade pieces. Don't give chances."},
    "endgame_technique":  {"name": "Endgame Activation",    "rule": "In endgames, activate your king and push passed pawns."},
    "pawn_structure":     {"name": "Structure Awareness",   "rule": "Before pushing a pawn, ask: what square does this weaken?"},
    "game_abandonment":   {"name": "Mental Discipline",     "rule": "Finish every game. You learn the most from losing positions."},
}

TRAINING_LOCK_TARGET = 5  # Puzzles required before unlocking game list


async def _build_lab_coaching(db, user_id, enriched_games, pattern_history, analyses):
    """
    Build the 5-section coaching structure for the Lab page.
    Returns: { root_problem, priority_game, insight, rule, training_lock }
    """
    if not pattern_history:
        return None

    # ── 1. ROOT PROBLEM — most frequent + damaging pattern ──
    # Score: frequency * damage (games where this pattern led to a loss)
    pattern_scores = {}
    for g in enriched_games:
        is_loss = g.get("result") == "L"
        was_winning = g.get("was_winning", False)
        for gap in g.get("cognitive_gaps", []):
            if gap not in pattern_scores:
                pattern_scores[gap] = {"count": 0, "losses": 0, "thrown": 0}
            pattern_scores[gap]["count"] += 1
            if is_loss:
                pattern_scores[gap]["losses"] += 1
            if was_winning and is_loss:
                pattern_scores[gap]["thrown"] += 1

    if not pattern_scores:
        return None

    # Rank by: losses caused + thrown games (most damaging first)
    ranked = sorted(pattern_scores.items(),
                    key=lambda x: (x[1]["thrown"] * 3 + x[1]["losses"] * 2 + x[1]["count"]),
                    reverse=True)

    root_pattern = ranked[0][0]
    root_data = ranked[0][1]
    root_label = root_pattern.replace("_", " ").title()

    total_games = len(enriched_games)
    root_problem = {
        "pattern": root_pattern,
        "label": root_label,
        "games_affected": root_data["count"],
        "losses_caused": root_data["losses"],
        "thrown_games": root_data["thrown"],
        "message": f"You are losing games because of {root_label.lower()}.",
        "detail": _root_detail(root_data, total_games),
    }

    # ── COMPUTE TOP PROBLEMS FIRST (needed for game matching) ──
    game_reasons = [g.get("game_reason") for g in enriched_games if g.get("game_reason")]
    top_problems = []
    try:
        from services.game_reason_classifier import aggregate_game_reasons
        top_problems = aggregate_game_reasons(game_reasons)
    except Exception:
        pass

    # ── CURRICULUM BRAIN OVERRIDE ──
    # Let the coach's persistent plan (coach_memory.learning.current_focus)
    # decide the #1 problem, sanity-checked against the fresh aggregate.
    # This keeps Lab / Home / training all pointing at the same ONE thing.
    active_focus = None
    try:
        from services.focus_resolver import get_active_focus, reorder_top_problems_by_focus
        active_focus = await get_active_focus(db, user_id, top_problems)
        if active_focus and active_focus.get("category"):
            top_problems = reorder_top_problems_by_focus(
                top_problems, active_focus["category"]
            )
    except Exception as e:
        logger.debug(f"Focus resolver failed (non-fatal): {e}")

    # The primary category to match games against
    primary_category = top_problems[0]["category"] if top_problems else None

    # ── 2. ALL GAMES MATCHING ROOT PROBLEM — with sub-causes ──
    SUB_CAUSE_MAP = {
        "ignore_threat":      "Stopped checking opponent",
        "piece_safety":       "Left a piece unprotected",
        "calculation_depth":  "Stopped calculating too early",
        "tactical_oversight": "Didn't check opponent's reply",
        "missed_tactic":      "Missed a winning tactic",
        "king_safety":        "Left king exposed",
        "time_pressure":      "Rushed under time pressure",
        "conversion":         "Got creative when ahead",
    }

    problem_games = []
    sub_cause_counts = {}

    for g in enriched_games:
        game_reason = g.get("game_reason", {})
        if not game_reason:
            continue

        # Match games by game_reason category (from classifier)
        matches_root = (
            (primary_category and game_reason.get("category") == primary_category)
            or (not primary_category and root_pattern in g.get("cognitive_gaps", []))
        )
        if not matches_root:
            continue
        if g.get("result") == "W":
            continue  # Only losses and draws matter

        gid = g.get("game_id", "")
        a = analyses.get(gid, {})
        evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        is_loss = g.get("result") == "L"
        was_winning = g.get("was_winning", False)
        is_reviewed = g.get("reviewed", False)

        # Pain score for sorting
        pain = 0
        if was_winning and is_loss:
            pain = 100
        elif is_loss:
            pain = 50
        elif g.get("result") == "D":
            pain = 20

        # Find the sub-cause — the dominant cognitive gap in THIS game
        # AND the critical move — the BIGGEST cp_loss move (regardless of gap tag)
        game_gaps = {}
        critical_move = None
        max_cp = 0
        for ev in evals:
            gap = ev.get("cognitive_gap", "")
            cp = ev.get("cp_loss", 0) or 0

            # Track cognitive gaps for sub-cause
            if gap and cp >= 100:
                game_gaps[gap] = game_gaps.get(gap, 0) + 1

            # Critical move = highest cp_loss, period. Not filtered by gap tag.
            if cp > max_cp:
                max_cp = cp
                critical_move = ev

        dominant_gap = max(game_gaps, key=game_gaps.get) if game_gaps else root_pattern
        sub_cause = SUB_CAUSE_MAP.get(dominant_gap, dominant_gap.replace("_", " ").title())

        # Track sub-cause counts
        sub_cause_counts[sub_cause] = sub_cause_counts.get(sub_cause, 0) + 1

        # Replay data will be computed for the actual priority game AFTER sorting
        replay_data = None
        if False:  # Disabled here — computed below for priority game
            try:
                import chess as chess_mod
                fen_before = critical_move.get("fen_before", "")
                user_move_san = critical_move.get("move", "")

                if fen_before and user_move_san:
                    board = chess_mod.Board(fen_before)

                    setup_fen = fen_before
                    mn = critical_move.get("move_number", 0)
                    for ev in reversed(evals):
                        ev_mn = ev.get("move_number", 0)
                        if ev_mn <= mn - 2 and ev.get("fen_before"):
                            setup_fen = ev.get("fen_before")
                            break

                    user_move = board.parse_san(user_move_san)
                    board.push(user_move)
                    fen_after_user = board.fen()

                    opponent_reply_fen = None
                    found_current = False
                    for ev in evals:
                        if found_current and ev.get("fen_before"):
                            opponent_reply_fen = ev.get("fen_before")
                            break
                        if ev.get("move_number") == mn and ev.get("move") == user_move_san:
                            found_current = True

                    if not opponent_reply_fen:
                        pv = critical_move.get("pv_after_played", [])
                        if pv:
                            try:
                                opp_move = board.parse_san(pv[0])
                                board.push(opp_move)
                                opponent_reply_fen = board.fen()
                            except Exception:
                                pass

                    replay_data = {
                        "setup_fen": setup_fen,
                        "mistake_fen": fen_before,
                        "after_move_fen": fen_after_user,
                        "after_reply_fen": opponent_reply_fen,
                    }
            except Exception:
                pass

        # Phase mini-analysis for this game
        phase_mini = {}
        try:
            uc = g.get("user_color", "white")
            opening_moves = [ev for ev in evals if (ev.get("move_number", 0) or 0) <= 12]
            middle_moves = [ev for ev in evals if 12 < (ev.get("move_number", 0) or 0) <= 30]
            end_moves = [ev for ev in evals if (ev.get("move_number", 0) or 0) > 30]

            def _phase_verdict(moves_list, phase_name):
                if not moves_list:
                    return None
                bl = sum(1 for e in moves_list if (e.get("cp_loss", 0) or 0) >= 300)
                ms = sum(1 for e in moves_list if 100 <= (e.get("cp_loss", 0) or 0) < 300)
                total = len(moves_list)
                errors = bl + ms
                acc = round(max(0, (1 - errors / total)) * 100) if total > 0 else 0
                if bl == 0 and ms == 0:
                    return {"phase": phase_name, "verdict": "Clean", "acc": acc}
                elif bl >= 2:
                    return {"phase": phase_name, "verdict": f"{bl} blunders", "acc": acc}
                elif bl == 1:
                    return {"phase": phase_name, "verdict": "1 critical error", "acc": acc}
                else:
                    return {"phase": phase_name, "verdict": f"{ms} inaccuracies", "acc": acc}

            op = _phase_verdict(opening_moves, "Opening")
            if op:
                phase_mini["opening"] = op
            mid = _phase_verdict(middle_moves, "Middlegame")
            if mid:
                phase_mini["middlegame"] = mid
            eg = _phase_verdict(end_moves, "Endgame")
            if eg:
                phase_mini["endgame"] = eg
        except Exception:
            pass

        # Trap detection — did this game's opening match a known trap?
        trap_found = None
        try:
            opening_name = g.get("opening", "")
            if opening_name:
                from services.opening_mastery_tracker import OPENING_MOVE_IDEAS
                from services.verified_opening_traps import get_all_for_opening

                # Match opening name to key
                opening_key = None
                for key in OPENING_MOVE_IDEAS:
                    name = key.replace("_", " ")
                    if name in opening_name.lower() or opening_name.lower() in name:
                        opening_key = key
                        break

                if opening_key:
                    traps = get_all_for_opening(opening_key)
                    if traps:
                        # Check if game moves match any trap setup
                        game_moves = [ev.get("move", "") for ev in evals if ev.get("move")]
                        for trap in traps:
                            setup = trap.setup_moves
                            if len(game_moves) >= len(setup):
                                match = all(
                                    (game_moves[i] or "").replace("+", "").replace("#", "").lower() ==
                                    (setup[i] or "").replace("+", "").replace("#", "").lower()
                                    for i in range(len(setup))
                                )
                                if match:
                                    trap_found = {
                                        "name": trap.name,
                                        "trap_move": trap.trap_move,
                                        "explanation": trap.explanation[:120],
                                        "victim": trap.victim_color,
                                    }
                                    break
        except Exception:
            pass

        # Generate behavioral story for this game
        # Use the behavior already computed in the enriched list
        game_behavior = g.get("behavior", "")
        if not game_behavior:
            try:
                sf = a.get("stockfish_analysis", {})
                _blunders = sf.get("blunders", 0) or g.get("blunders", 0)
                _mistakes = sf.get("mistakes", 0) or g.get("mistakes", 0)
                _accuracy = sf.get("accuracy", 0) or g.get("accuracy", 0)
                _is_draw = g.get("result") == "D"
                _user_won = g.get("result") == "W"
                _max_adv = (g.get("max_advantage", 0) or 0) * 100
                game_behavior = _generate_game_story(
                    evals, g.get("user_color", "white"),
                    _user_won, _is_draw, was_winning, _max_adv,
                    _blunders, _mistakes, _accuracy, 0,
                    pattern_history, 0,
                )
            except Exception as e:
                logger.debug(f"Game story for {gid} failed: {e}")

        problem_games.append({
            "game_id": gid,
            "opponent": g.get("opponent", "Opponent"),
            "opening": g.get("opening", ""),
            "result": g.get("result", ""),
            "was_winning": was_winning,
            "sub_cause": sub_cause,
            "behavior": game_behavior,
            "phases": phase_mini,
            "trap": trap_found,
            "pain": pain,
            "reviewed": is_reviewed,
            "user_color": g.get("user_color", "white"),
            "replay": replay_data,
        })

    # Sort by pain (most painful first), then unreviewed first
    problem_games.sort(key=lambda x: (-int(not x["reviewed"]), -x["pain"]))

    # Sub-causes sorted by frequency
    sub_causes = sorted(
        [{"cause": k, "count": v} for k, v in sub_cause_counts.items()],
        key=lambda x: -x["count"]
    )

    # Priority game = first unreviewed, or first overall
    priority_game = None
    for pg_candidate in problem_games:
        if not pg_candidate["reviewed"]:
            priority_game = pg_candidate
            break
    if not priority_game and problem_games:
        priority_game = problem_games[0]

    # Compute replay FENs for the priority game
    if priority_game and not priority_game.get("replay"):
        try:
            import chess as chess_mod
            pg_gid = priority_game["game_id"]
            pg_a = analyses.get(pg_gid, {})
            pg_evals = pg_a.get("stockfish_analysis", {}).get("move_evaluations", [])
            pg_uc = priority_game.get("user_color", "white")

            # Find the biggest cp_loss move in this game
            pg_critical = None
            pg_max_cp = 0
            for ev in pg_evals:
                cp = ev.get("cp_loss", 0) or 0
                if cp > pg_max_cp:
                    pg_max_cp = cp
                    pg_critical = ev

            if pg_critical:
                fen_before = pg_critical.get("fen_before", "")
                user_move_san = pg_critical.get("move", "")

                if fen_before and user_move_san:
                    board = chess_mod.Board(fen_before)

                    # Setup FEN — 2-3 moves before mistake
                    setup_fen = fen_before
                    mn = pg_critical.get("move_number", 0)
                    for ev in reversed(pg_evals):
                        ev_mn = ev.get("move_number", 0)
                        if ev_mn <= mn - 2 and ev.get("fen_before"):
                            setup_fen = ev.get("fen_before")
                            break

                    # FEN after user's move
                    user_move = board.parse_san(user_move_san)
                    board.push(user_move)
                    fen_after_user = board.fen()

                    # Opponent's reply
                    opponent_reply_fen = None
                    found_current = False
                    for ev in pg_evals:
                        if found_current and ev.get("fen_before"):
                            opponent_reply_fen = ev.get("fen_before")
                            break
                        if ev.get("move_number") == mn and ev.get("move") == user_move_san:
                            found_current = True

                    if not opponent_reply_fen:
                        pv = pg_critical.get("pv_after_played", [])
                        if pv:
                            try:
                                opp_move = board.parse_san(pv[0])
                                board.push(opp_move)
                                opponent_reply_fen = board.fen()
                            except Exception:
                                pass

                    priority_game["replay"] = {
                        "setup_fen": setup_fen,
                        "mistake_fen": fen_before,
                        "after_move_fen": fen_after_user,
                        "after_reply_fen": opponent_reply_fen,
                    }
                    priority_game["move_number"] = mn
        except Exception as replay_err:
            logger.debug(f"Priority game replay extraction failed: {replay_err}")

    # ── 3. INSIGHT from top problem (top_problems already computed above) ──
    if top_problems:
        top = top_problems[0]
        insight = top.get("description", "")
        insight_label = top.get("label", "")
    else:
        insight = COACHING_INSIGHTS.get(root_pattern,
            "You are making the same mistake repeatedly. Until you fix it, nothing else matters.")
        insight_label = ""

    # ── 4. RULE ──
    rule_data = COACHING_RULES.get(root_pattern, {"name": root_label, "rule": "Fix this before working on anything else."})

    # ── 5. TRAINING LOCK — 5 CORRECT solves, with streak reset ──
    try:
        from services.community_training_service import get_training_progress
        progress = await get_training_progress(db, user_id, root_pattern, TRAINING_LOCK_TARGET)
    except Exception:
        progress = {"correct": 0, "required": TRAINING_LOCK_TARGET, "completed": False, "streak": 0}

    training_lock = {
        "pattern": root_pattern,
        "label": root_label,
        "target": TRAINING_LOCK_TARGET,
        "progress": progress["correct"],
        "streak": progress.get("streak", 0),
        "unlocked": progress["completed"],
        "message": f"Solve {TRAINING_LOCK_TARGET} {root_label} puzzles correctly to unlock game review.",
    }

    # ── DIAGNOSIS (short for home, detail for lab) ──
    diag = COACHING_DIAGNOSIS.get(root_pattern, {"short": root_label, "detail": root_label})

    # ── PROBLEM LIFECYCLE — anger escalation ──
    lifecycle = None
    try:
        from services.problem_lifecycle import update_problem_lifecycle
        game_reasons_list = [g.get("game_reason") for g in enriched_games if g.get("game_reason")]
        lifecycle = await update_problem_lifecycle(db, user_id, enriched_games, game_reasons_list)
    except Exception as lc_err:
        logger.debug(f"Problem lifecycle failed (non-fatal): {lc_err}")

    # ── GAMES GROUPED BY ALL TOP 3 PROBLEMS ──
    grouped_games = {}
    for tp in top_problems[:3]:
        cat = tp["category"]
        grouped_games[cat] = {
            "label": tp["label"],
            "description": tp.get("description", ""),
            "count": tp["count"],
            "games": [],
        }

    # Helper: one-line coach commentary built from existing game signals.
    # Deterministic — no LLM, no DB queries. 4-10 words, past tense.
    def _coach_take(g: Dict, critical_move_num: Optional[int]) -> str:
        result = g.get("result", "")
        was_winning = g.get("was_winning", False)
        blunders = g.get("blunders", 0) or 0
        mistakes = g.get("mistakes", 0) or 0
        gr = g.get("game_reason") or {}
        gr_label = gr.get("label", "") or ""
        gr_cat = gr.get("category", "") or ""

        mv = f" on move {critical_move_num}" if critical_move_num else ""

        # === WINS ===
        if result == "W":
            if blunders == 0 and mistakes <= 1:
                return "Clean win."
            if gr_cat == "opponent_blundered":
                return "Won — opponent cracked first."
            if blunders >= 1:
                return f"Won despite a wobble{mv}."
            return "Solid win."

        # === DRAWS ===
        if result == "D":
            if was_winning:
                return f"Drew from a winning position — slip{mv}."
            if blunders == 0:
                return "Even game throughout."
            return f"Drew after a mistake{mv}."

        # === LOSSES ===
        # Most specific categories first
        if gr_cat == "one_move_blunder" or (blunders >= 1 and mistakes == 0):
            return f"One-move blunder{mv}."
        if was_winning:
            return f"Winning, then let it slip{mv}."
        if blunders >= 2:
            return "Two big mistakes cost this one."
        if gr_label:
            return f"{gr_label}{mv}." if mv else f"{gr_label}."
        return f"Critical mistake{mv}." if mv else "Tough loss."

    # Helper: build the game dict the frontend expects (used by both
    # problem-category groups AND the flat all_games list).
    def _build_game_dict(g: Dict) -> Dict:
        gid = g.get("game_id", "")
        a = analyses.get(gid, {})
        evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        critical_move_num = None
        critical_fen = None
        critical_best = None
        critical_played = None
        critical_cp = 0
        for ev in evals:
            cp = ev.get("cp_loss", 0) or 0
            if cp > critical_cp:
                critical_cp = cp
                critical_move_num = ev.get("move_number")
                critical_fen = ev.get("fen_before", "")
                critical_best = ev.get("best_move", "")
                critical_played = ev.get("move", "")

        # Platform detection with fallback cascade
        raw_platform = g.get("platform") or g.get("source") or ""
        opponent_name = g.get("opponent", "") or ""
        if raw_platform in ("chess.com", "lichess", "coach"):
            platform = raw_platform
        elif opponent_name.lower() == "coach" or g.get("is_coach_session"):
            platform = "coach"
        elif g.get("chess_com_url") or "chess.com" in (g.get("url", "") or ""):
            platform = "chess.com"
        elif g.get("lichess_url") or "lichess" in (g.get("url", "") or ""):
            platform = "lichess"
        else:
            gid_lower = str(gid).lower()
            if "lichess" in gid_lower:
                platform = "lichess"
            elif gid_lower.startswith("session_") or "coach" in gid_lower:
                platform = "coach"
            else:
                platform = "chess.com"

        return {
            "game_id": gid,
            "opponent": opponent_name or "Opponent",
            "opening": g.get("opening", ""),
            "result": g.get("result", ""),
            "user_color": g.get("user_color", ""),
            "behavior": g.get("behavior", ""),
            "coach_take": _coach_take(g, critical_move_num),  # Short deterministic line
            "is_new": g.get("is_new", False),
            "was_winning": g.get("was_winning", False),
            "reviewed": g.get("reviewed", False),
            "critical_move": critical_move_num,
            "critical_fen": critical_fen,
            "critical_best": critical_best,
            "critical_played": critical_played,
            "critical_cp": critical_cp or None,
            "platform": platform,
            "analyzed_at": g.get("analyzed_at") or a.get("created_at"),
            "created_at": g.get("created_at") or g.get("imported_at"),
        }

    # Build TWO lists:
    # 1. grouped_games (by problem category) — for the "Other areas to work on"
    #    sections. Still filtered to loss categories (that's the point).
    # 2. all_games — flat list of EVERY analyzed game (wins + losses + draws).
    #    This is what the "Recently synced" / "Chess.com" / "Lichess" /
    #    "Games with Coach" sections read from.
    all_games = []
    for g in enriched_games:
        game_dict = _build_game_dict(g)
        all_games.append(game_dict)

        # Also add to category group if its reason matches a top_problem
        gr = g.get("game_reason", {}) or {}
        cat = gr.get("category", "")
        if cat in grouped_games:
            grouped_games[cat]["games"].append(game_dict)

    # ── PLAYER STRENGTHS ──
    # Built from ACTUAL game data — not just win categories
    # Must NOT conflict with weaknesses
    strengths = []
    weakness_categories = {tp["category"] for tp in top_problems[:3]}

    # Count specific positive signals from ALL games
    total_games = len(enriched_games)
    total_brilliants = sum(g.get("brilliant_moves", 0) for g in enriched_games)
    total_wins = sum(1 for g in enriched_games if g.get("result") == "W")
    total_losses = sum(1 for g in enriched_games if g.get("result") == "L")

    # Win categories (filtered to not conflict with weaknesses)
    CONFLICTING = {
        "threw_winning": {"opponent_blundered"},  # can't "capitalize" if you also "throw"
        "tactical_miss": {"tactical_win"},        # can't "find tactics" if you also "miss" them
        "time_collapse": set(),
        "opening_disaster": set(),
        "endgame_collapse": {"endgame_conversion"},
    }
    excluded_strengths = set()
    for wk in weakness_categories:
        excluded_strengths.update(CONFLICTING.get(wk, set()))

    win_categories = {}
    for g in enriched_games:
        if g.get("result") != "W":
            continue
        gr = g.get("game_reason", {})
        cat = gr.get("category", "")
        if cat and cat not in excluded_strengths:
            if cat not in win_categories:
                win_categories[cat] = 0
            win_categories[cat] += 1

    STRENGTH_DATA = {
        "brilliant_play":     {"label": "Deep calculation",      "desc": "You found {count} brilliant moves across your games"},
        "tactical_win":       {"label": "Tactical eye",          "desc": "You won {count} games through tactics"},
        "solid_play":         {"label": "Solid play",            "desc": "You played {count} clean games with few mistakes"},
        "endgame_conversion": {"label": "Endgame skill",         "desc": "You converted {count} endgames successfully"},
        "opponent_blundered": {"label": "Punishing mistakes",    "desc": "You capitalized on opponent errors in {count} games"},
    }

    # Always show brilliants if any — with type breakdown
    if total_brilliants > 0:
        # Count types across all games
        type_counts = {}
        for g in enriched_games:
            for bd in g.get("brilliant_detail", []):
                bt = bd.get("type", "Strong move")
                type_counts[bt] = type_counts.get(bt, 0) + 1

        type_parts = []
        for bt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            type_parts.append(f"{count} {bt.lower()}{'s' if count > 1 else ''}")
        type_text = ", ".join(type_parts[:3]) if type_parts else ""

        desc = f"You found {total_brilliants} brilliant moves"
        if type_text:
            desc += f" — {type_text}"

        strengths.append({
            "category": "brilliant_play",
            "label": "Deep calculation",
            "description": desc,
            "count": total_brilliants,
            "breakdown": type_counts,
        })

    # Add win-based strengths (filtered)
    sorted_wins = sorted(win_categories.items(), key=lambda x: -x[1])
    for cat, count in sorted_wins:
        if len(strengths) >= 3:
            break
        if cat == "brilliant_play":
            continue  # Already added above
        sd = STRENGTH_DATA.get(cat)
        if sd:
            strengths.append({
                "category": cat,
                "label": sd["label"],
                "description": sd["desc"].format(count=count),
                "count": count,
            })

    return {
        "root_problem": root_problem,
        "diagnosis": diag,
        "priority_game": priority_game,
        "problem_games": problem_games,
        "sub_causes": sub_causes,
        "total_problem_games": len(problem_games),
        "reviewed_problem_games": sum(1 for pg in problem_games if pg["reviewed"]),
        "insight": insight,
        "insight_label": insight_label,
        "top_problems": top_problems,
        "grouped_games": grouped_games,
        "all_games": all_games,  # Flat list of every analyzed game (wins too) for source sections
        "strengths": strengths,
        "rule": rule_data,
        "training_lock": training_lock,
        "lifecycle": lifecycle,
        "active_focus": active_focus,
    }


def _root_detail(data, total_games):
    """Generate the 'evidence' line for the root problem."""
    parts = []
    if data["thrown"] > 0:
        parts.append(f"You threw {data['thrown']} winning position{'s' if data['thrown'] > 1 else ''}")
    if data["losses"] > 0:
        parts.append(f"it caused {data['losses']} loss{'es' if data['losses'] > 1 else ''}")
    if parts:
        return ". ".join(parts) + ". That is where your rating is leaking."
    return f"This appeared in {data['count']} of your last {total_games} games."


def _describe_critical_moment(pattern, move_data):
    """One-line description of what happened at the critical move."""
    move = move_data.get("move", "?")
    best = move_data.get("best_move", "?")
    descs = {
        "piece_safety": f"you left a piece hanging with {move} instead of {best}",
        "ignore_threat": f"you ignored your opponent's threat and played {move}",
        "calculation_depth": f"you played {move} without calculating deep enough — {best} was winning",
        "missed_tactic": f"you missed a tactic — {best} was available but you played {move}",
        "tactical_oversight": f"you played {move} without checking your opponent's response",
        "king_safety": f"you attacked with {move} while your king was exposed",
        "conversion": f"you had the advantage but played {move} instead of the safe {best}",
    }
    return descs.get(pattern, f"you played {move} instead of {best}")


@router.get("/lab-coach-pick")
async def get_lab_coach_pick(user: User = Depends(get_current_user)):
    """
    Smart game picker for the Lab page.
    Returns the most educational unreviewed game + reason + all games with reviewed status.
    Caches coaching section for 5 minutes to avoid recomputing on every Home load.
    """
    # Check cache — coaching data doesn't change every second
    from datetime import datetime, timezone
    cache_doc = await db.coaching_cache.find_one(
        {"user_id": user.user_id}, {"_id": 0}
    )
    CACHE_TTL = 300  # 5 minutes

    if cache_doc and cache_doc.get("cached_at"):
        cached_at = cache_doc["cached_at"]
        if isinstance(cached_at, str):
            try:
                cached_at = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
            except Exception:
                cached_at = None
        if cached_at:
            age = (datetime.now(timezone.utc) - cached_at).total_seconds() if cached_at.tzinfo else 999
            if age < CACHE_TTL and cache_doc.get("data"):
                return cache_doc["data"]

    # Get all analyzed games with analysis data
    # Fetch imported games and coach games separately to ensure both show.
    # Coach games get imported_at=now when promoted from sessions, so sorting
    # the merged list by timestamp would push them ABOVE platform games the
    # user imported from Chess.com / Lichess (the bug this addresses).
    imported_games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True, "platform": {"$ne": "coach"}},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(40)

    coach_games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True, "platform": "coach"},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(10)

    # Imported platform games ALWAYS come first (the user's real competitive games).
    # Coach games appear at the bottom — they're for reference, not the review focus.
    games = imported_games + coach_games

    # Only load move_evaluations fields we actually use (not the full array)
    analyses_cursor = db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis.blunders": 1, "stockfish_analysis.mistakes": 1,
         "stockfish_analysis.accuracy": 1,
         "stockfish_analysis.move_evaluations.cognitive_gap": 1,
         "stockfish_analysis.move_evaluations.cp_loss": 1,
         "stockfish_analysis.move_evaluations.move_number": 1,
         "stockfish_analysis.move_evaluations.move": 1,
         "stockfish_analysis.move_evaluations.is_brilliant": 1,
         "stockfish_analysis.move_evaluations.is_sacrifice": 1,
         "stockfish_analysis.move_evaluations.eval_before": 1,
         "stockfish_analysis.move_evaluations.threat": 1,
         "stockfish_analysis.move_evaluations.fen_before": 1,
         "stockfish_analysis.move_evaluations.best_move": 1,
         "coach_summary": 1, "decryption_v5_data.core_lesson": 1, "llm_game_story": 1}
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

        # Termination-based weakness injection
        game_termination = g.get("termination", "unknown")
        if not user_won and not is_draw:
            if game_termination == "timeout":
                cognitive_gaps.append("time_management")
            elif game_termination == "abandonment":
                cognitive_gaps.append("game_abandonment")

        # Count brilliant moves and sacrifices in this game
        brilliant_count = sum(1 for e in evals if e.get("is_brilliant"))
        sacrifice_count = sum(1 for e in evals if e.get("is_sacrifice"))
        brilliant_moves_detail = []
        for e in evals:
            if not e.get("is_brilliant"):
                continue
            move_san = e.get("move", "")
            is_sac = e.get("is_sacrifice", False)
            cp_swing = abs((e.get("eval_after", 0) or 0) - (e.get("eval_before", 0) or 0))

            # Infer type — be specific, not "all sacrifices"
            if "#" in move_san:
                btype = "Checkmate"
            elif "+" in move_san and cp_swing > 300:
                btype = "Winning check"
            elif "x" in move_san and cp_swing > 300:
                btype = "Tactical strike"
            elif "x" in move_san and is_sac:
                btype = "Sacrifice"
            elif cp_swing > 400:
                btype = "Deep calculation"
            elif "+" in move_san:
                btype = "Forcing move"
            elif is_sac:
                btype = "Positional sacrifice"
            else:
                btype = "Strong move"

            brilliant_moves_detail.append({
                "move": move_san,
                "move_number": e.get("move_number", 0),
                "fen": e.get("fen_before", ""),
                "type": btype,
            })

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

        # Generate game story — cached LLM or deterministic fallback
        behavior = coach_sum.get("behavioral_insight") or coach_sum.get("key_observation") or ""
        # Check for cached LLM story first
        cached_story = a.get("llm_game_story", "")
        if cached_story:
            behavior = cached_story
        elif not behavior:
            try:
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
            except Exception as story_err:
                logger.warning(f"Game story generation failed for {gid}: {story_err}")
                behavior = ""

        termination = g.get("termination", "unknown")
        termination_label = _termination_display(termination, "W" if user_won else ("D" if is_draw else "L"))

        # Mark recently analyzed games
        is_new = False
        try:
            imported = g.get("imported_at") or g.get("created_at")
            if imported:
                if isinstance(imported, str):
                    from datetime import datetime, timezone
                    imported = datetime.fromisoformat(imported.replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - imported).total_seconds() / 3600
                is_new = age_hours < 24
        except Exception:
            pass

        # Classify game reason — WHY was this game won/lost?
        game_reason = None
        try:
            from services.game_reason_classifier import classify_game_reason
            game_reason = classify_game_reason(
                move_evaluations=evals,
                game_result=result,
                user_color=uc,
                termination=termination,
                accuracy=accuracy,
            )
        except Exception:
            pass

        # Move-grounded headline + subline for the Lab game list and Coach's Pick.
        # root_cause  = the coach's opening line (short, emotional, memorable)
        # subline     = the supporting specific-move sentence
        # Termination/opponent/decisive-moment live in context[] for detail views.
        root_cause = ""
        subline = ""
        diagnosis = ""
        try:
            from services.game_coach_summary import compute_game_summary
            _gs = compute_game_summary(evals, result, uc, g.get("opening", "") or "", termination=termination)
            diagnosis = _gs.get("diagnosis", "") or ""
            root_cause = _gs.get("root_cause", "") or ""
            subline = _gs.get("subline", "") or ""
        except Exception as _diag_err:
            logger.debug(f"game diagnosis failed for {gid}: {_diag_err}")

        enriched.append({
            "game_id": gid,
            "opponent": opp,
            "platform": g.get("platform", ""),
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
            "diagnosis": diagnosis,
            "root_cause": root_cause,
            "subline": subline,
            "summary_headline": g.get("summary", {}).get("headline") if isinstance(g.get("summary"), dict) else None,
            "behavior": behavior,
            "lesson_label": lesson_label,
            "lesson": core_les.get("lesson", ""),
            "brilliant_moves": brilliant_count,
            "sacrifices": sacrifice_count,
            "brilliant_detail": brilliant_moves_detail,
            "termination": termination,
            "termination_label": termination_label,
            "game_reason": game_reason,
            "is_new": is_new,
        })

    # ── BATCH LLM: fire-and-forget — generate stories in background ──
    # Don't block the response. Stories will be cached for next load.
    import asyncio
    try:
        games_needing_stories = [
            g for g in enriched
            if not g.get("reviewed") and not analyses.get(g["game_id"], {}).get("llm_game_story")
        ]
        if games_needing_stories:
            async def _bg_generate():
                try:
                    batch = games_needing_stories[:10]
                    llm_stories = await _batch_generate_game_stories(batch)
                    for gid, story in llm_stories.items():
                        if story:
                            await db.game_analyses.update_one(
                                {"game_id": gid}, {"$set": {"llm_game_story": story}}
                            )
                    # Invalidate cache so next load picks up LLM stories
                    await db.coaching_cache.delete_one({"user_id": user.user_id})
                    logger.info(f"[LAB] Background LLM generated {len(llm_stories)} stories")
                except Exception as e:
                    logger.warning(f"Background LLM stories failed: {e}")
            asyncio.create_task(_bg_generate())
    except Exception:
        pass

    # ── SMART PICK: find the best unreviewed game ──
    # Prefer platform games (Chess.com / Lichess) over coach-play games — real
    # competitive games have more teaching value than coach-session practice.
    # Only fall back to coach games when no platform games remain unreviewed.
    unreviewed_all = [g for g in enriched if not g["reviewed"]]
    unreviewed_platform = [g for g in unreviewed_all if g.get("platform") != "coach"]
    unreviewed = unreviewed_platform if unreviewed_platform else unreviewed_all
    pick = None
    pick_reason = ""
    pick_pattern = ""

    if unreviewed:
        # Use recency-weighted decay model instead of raw counts.
        # Also pull in puzzle-solve recoveries so practiced patterns fade
        # faster (closes the training → graduation loop).
        from services.pattern_decay_service import (
            compute_pattern_scores, pick_best_game, get_puzzle_recoveries,
        )

        puzzle_recoveries = await get_puzzle_recoveries(db, user.user_id)
        pattern_scores = compute_pattern_scores(enriched, puzzle_recoveries=puzzle_recoveries)

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

    # ── COACHING SECTION — root problem, priority game, insight, rule, training lock ──
    coaching = None
    try:
        coaching = await _build_lab_coaching(db, user.user_id, enriched, pattern_history, analyses)
    except Exception as coaching_err:
        logger.warning(f"Lab coaching section failed: {coaching_err}")

    result = {
        "pick": pick,
        "pick_reason": pick_reason,
        "pick_pattern": pick_pattern,
        "verdict": {"wins": wins, "losses": losses, "total": len(recent), "insight": insight},
        "games": enriched,
        "reviewed_count": sum(1 for g in enriched if g["reviewed"]),
        "total_count": len(enriched),
        "coaching": coaching,
    }

    # Add focus data (training lock, root problem)
    try:
        from services.focus_engine import get_user_focus
        focus = await get_user_focus(db, user.user_id)
        if focus:
            result["focus"] = {
                "name": focus.get("name"),
                "rule": focus.get("rule"),
                "cluster": focus.get("cluster"),
                "enforcement_level": focus.get("enforcement_level"),
                "training_locked": focus.get("training_locked", False),
                "puzzles_completed": focus.get("puzzles_completed", 0),
                "puzzles_required": focus.get("puzzles_required", 5),
                "description": focus.get("description", ""),
            }
    except Exception:
        pass

    # Spotlight: newest unreviewed game with the richest story
    spotlight = None
    try:
        new_unreviewed = [g for g in enriched if g.get("is_new") and not g.get("reviewed")]
        if not new_unreviewed:
            # Fallback: any unreviewed game
            new_unreviewed = [g for g in enriched if not g.get("reviewed")]

        if new_unreviewed:
            # Pick the one with highest pain (was_winning + loss > loss > draw)
            def _pain(g):
                if g.get("was_winning") and g.get("result") == "L":
                    return 100
                elif g.get("result") == "L":
                    return 50 + g.get("blunders", 0) * 10
                elif g.get("result") == "D":
                    return 20
                return 0

            best = max(new_unreviewed, key=_pain)
            if best.get("behavior") or best.get("game_reason"):
                # Check if this game repeats the top problem
                top_cat = coaching.get("top_problems", [{}])[0].get("category", "") if coaching else ""
                best_cat = best.get("game_reason", {}).get("category", "")
                repeats_problem = top_cat and best_cat == top_cat

                spotlight = {
                    "game_id": best.get("game_id"),
                    "opponent": best.get("opponent", "Opponent"),
                    "result": best.get("result"),
                    "opening": best.get("opening", ""),
                    "behavior": best.get("behavior", ""),
                    "was_winning": best.get("was_winning", False),
                    "blunders": best.get("blunders", 0),
                    "accuracy": best.get("accuracy", 0),
                    "is_new": best.get("is_new", False),
                    "repeats_problem": repeats_problem,
                    "problem_label": coaching.get("top_problems", [{}])[0].get("label", "") if repeats_problem and coaching else "",
                }
    except Exception:
        pass

    result["spotlight"] = spotlight

    # Cache for 5 minutes
    try:
        await db.coaching_cache.update_one(
            {"user_id": user.user_id},
            {"$set": {"data": result, "cached_at": datetime.now(timezone.utc).isoformat(), "user_id": user.user_id}},
            upsert=True
        )
    except Exception:
        pass

    return result


@router.post("/lab-mark-reviewed/{game_id}")
async def mark_game_reviewed(game_id: str, user: User = Depends(get_current_user)):
    """Mark a game as reviewed by the user."""
    result = await db.games.update_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"$set": {"reviewed": True, "reviewed_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}}
    )
    # Invalidate coaching cache so Lab/Home refresh
    try:
        await db.coaching_cache.delete_one({"user_id": user.user_id})
    except Exception:
        pass
    return {"success": result.modified_count > 0}


@router.post("/lab-refresh-stories")
async def refresh_game_stories(user: User = Depends(get_current_user)):
    """Clear cached LLM stories so they regenerate on next load."""
    try:
        result = await db.game_analyses.update_many(
            {"user_id": user.user_id},
            {"$unset": {"llm_game_story": ""}}
        )
        await db.coaching_cache.delete_one({"user_id": user.user_id})
        return {"cleared": result.modified_count}
    except Exception as e:
        return {"cleared": 0, "error": str(e)}


@router.get("/replay/{game_id}")
async def get_game_replay(game_id: str, user: User = Depends(get_current_user)):
    """
    Get multi-moment Coach Replay data for a game.
    Returns 3-4 key moments with board reading at each.
    """
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "stockfish_analysis.move_evaluations": 1, "stockfish_analysis.accuracy": 1}
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found")

    evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
    user_color = game.get("user_color", "white")

    # Extract moments
    from services.game_moments_service import extract_game_moments
    moments = extract_game_moments(
        move_evaluations=evals,
        game_result=game.get("result", ""),
        user_color=user_color,
        termination=game.get("termination", "unknown"),
    )

    # Add LLM board reading for each moment
    for moment in moments:
        if moment.get("fen_before"):
            try:
                from services.position_intelligence import read_board_deep
                board_read = await read_board_deep(
                    moment["fen_before"],
                    user_color=user_color,
                    user_rating=1200,
                )
                moment["board_reading"] = board_read.get("summary", "")
            except Exception:
                moment["board_reading"] = ""

    # Get the coaching rule for behavior connection
    coaching_data = None
    try:
        cache = await db.coaching_cache.find_one({"user_id": user.user_id}, {"_id": 0, "data.coaching.rule": 1, "data.coaching.diagnosis": 1})
        if cache:
            coaching_data = cache.get("data", {}).get("coaching", {})
    except Exception:
        pass

    return {
        "game_id": game_id,
        "opponent": game.get("opponent_name", "Opponent"),
        "opening": game.get("opening", ""),
        "result": game.get("result", ""),
        "user_color": user_color,
        "moments": moments,
        "rule": coaching_data.get("rule") if coaching_data else None,
        "behavior": coaching_data.get("diagnosis", {}).get("detail", "") if coaching_data else "",
    }


@router.get("/training/pattern-puzzles/{pattern}")
async def get_pattern_puzzles(
    pattern: str,
    limit: int = 15,
    user: User = Depends(get_current_user),
):
    """
    DEPRECATED — kept for backwards compat and tests only.

    As of 2026-04-21, the frontend consolidated all three training routes
    (`/training`, `/training/prescribed`, `/training/pattern/:pattern`) to
    render the single PrescribedTraining component, which calls the
    canonical endpoint `/api/training/prescribed/{weakness}`. This endpoint
    is no longer hit from the live UI.

    Kept because: backend/tests/test_decay_model_puzzles.py still calls it,
    and the auto-backfill trigger here is useful as a standalone warmup.

    Get training puzzles for a specific cognitive gap pattern.
    Returns user's own game positions first, then community puzzles.
    Excludes already-solved puzzles.
    Auto-triggers backfill if no puzzles exist yet.

    Pass `current` to use whatever the curriculum brain has set as
    coach_memory.learning.current_focus.
    """
    from services.puzzle_extraction_service import get_pattern_training_puzzles, backfill_puzzles_for_user
    from services.focus_resolver import get_active_focus

    resolved_focus = None
    if pattern in ("current", "auto", "focus"):
        resolved_focus = await get_active_focus(db, user.user_id, top_problems=None)
        if resolved_focus and resolved_focus.get("gap"):
            pattern = resolved_focus["gap"]
        else:
            pattern = "piece_safety"  # safe default for beginners

    # Check if user has ANY puzzles — if not, auto-backfill
    existing = await db.community_puzzles.count_documents({"shared_by": user.user_id})
    if existing == 0:
        try:
            created = await backfill_puzzles_for_user(db, user.user_id)
            if created > 0:
                logger.info(f"Auto-backfilled {created} puzzles for {user.user_id}")
        except Exception as e:
            logger.warning(f"Auto-backfill failed: {e}")

    result = await get_pattern_training_puzzles(db, user.user_id, pattern, limit)
    if resolved_focus:
        if isinstance(result, dict):
            result["active_focus"] = resolved_focus
    return result


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
    """DEPRECATED — kept for backwards compat and tests.

    This was the data source for ThinkingTraining.jsx (the community-feed
    browse page). As of 2026-04-21 the frontend consolidated training to a
    single page (PrescribedTraining) that uses /api/training/prescribed/{weakness}
    as its canonical endpoint. No live UI calls /community-feed anymore.

    Get mixed training feed: own positions + community positions.
    Optionally filter by pattern_type.
    """
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
async def check_endgame_move(
    req: EndgameCheckMoveRequest,
    user: User = Depends(get_current_user),
):
    """Check if the user's move is correct for the given endgame position.

    Also records completion on Engine 2's skill tree when a lesson ends:
      - Last position answered correctly → skill marked "correct"
      - Any wrong answer → skill marked "wrong"
    Because endgame/mate skills graduate on 1 correct (kind-aware is_learned),
    a clean first-time completion graduates the skill immediately.
    """
    from services.endgame_theory_service import check_move
    result = check_move(req.category_key, req.lesson_key, req.position_index, req.user_move_uci)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Record to Engine 2 skill progress when a lesson-level signal fires.
    # Signals:
    #   - is_last=True AND correct=True → "correct" once
    #   - correct=False at any position → "wrong" once
    try:
        should_record = (
            (result.get("correct") and result.get("is_last"))
            or (result.get("correct") is False)
        )
        if should_record:
            await _record_endgame_lesson_outcome(
                user_id=user.user_id,
                category_key=req.category_key,
                lesson_key=req.lesson_key,
                correct=bool(result.get("correct")),
            )
    except Exception as e:
        logger.debug(f"[engine2] endgame lesson recording non-fatal: {e}")

    return result


async def _record_endgame_lesson_outcome(
    user_id: str,
    category_key: str,
    lesson_key: str,
    correct: bool,
):
    """Look up which Engine 2 skill node has content_ref matching this lesson
    (direct match on lesson_key) and record the attempt to coach_memory.

    The skill kind in the tree determines graduation behavior — endgame &
    mate_pattern skills graduate on first correct (SkillProgress.is_learned()).
    """
    from services.engine2_skill_builder import list_skills_by_kind, get_skill_node
    from services.coach_memory import (
        get_or_create_memory, record_skill_attempt, _memory_to_doc
    )

    # Find matching Engine 2 skill by content_ref == lesson_key (e.g. "square_rule")
    matching_skill = None
    matching_kind = None
    for kind in ("endgame", "mate_pattern"):
        for sid in list_skills_by_kind(kind):
            node = get_skill_node(sid) or {}
            if node.get("content_ref") == lesson_key:
                matching_skill = sid
                matching_kind = kind
                break
        if matching_skill:
            break

    if not matching_skill:
        logger.debug(f"[engine2] no skill tree match for lesson '{lesson_key}' — skipping record")
        return

    memory = await get_or_create_memory(db, user_id)
    outcome = "correct" if correct else "wrong"
    record_skill_attempt(memory, matching_skill, matching_kind, outcome)

    # Persist
    await db.coach_memory.update_one(
        {"user_id": user_id},
        {"$set": _memory_to_doc(memory)},
        upsert=True,
    )
    logger.info(f"[engine2] {user_id}: {matching_skill} ({matching_kind}) recorded '{outcome}'")


# ==================== ENGINE 2 — generic skill-progress endpoints ====================
#
# Pages (opening lesson, trap study, etc.) call these when the user sees
# content or completes something. The endpoint validates the skill exists
# in the tree, looks up its kind, and records the attempt.
#
# Graduation is automatic — SkillProgress.is_learned() is kind-aware:
#   - Knowledge (endgame/mate/concept): 1 correct → learned
#   - Trap set: 1 seen + 1 correct → learned
#   - Opening: 5/3 classic rule
#   - Coached_play: 3 correct habit streak
#
# So "mark as seen" does not graduate knowledge-type skills (they need
# a correct signal). It just builds exposure.


class Engine2SkillRequest(BaseModel):
    skill_id: str
    outcome: Optional[str] = None  # "correct" | "wrong" | "seen" (defaults based on endpoint)


async def _record_engine2_skill(user_id: str, skill_id: str, outcome: str) -> dict:
    """Shared helper — validates skill is in the tree, records the attempt,
    saves memory, returns a summary of the skill's new state."""
    from services.engine2_skill_builder import get_skill_node
    from services.coach_memory import (
        get_or_create_memory, record_skill_attempt, _memory_to_doc
    )

    node = get_skill_node(skill_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not in tree")

    kind = node.get("kind", "concept")
    memory = await get_or_create_memory(db, user_id)
    before_learned = skill_id in (
        memory.learning.openings_learned
        + memory.learning.traps_learned
        + memory.learning.endgames_learned
        + memory.learning.concepts_mastered
    )

    record_skill_attempt(memory, skill_id, kind, outcome)

    await db.coach_memory.update_one(
        {"user_id": user_id},
        {"$set": _memory_to_doc(memory)},
        upsert=True,
    )

    # Look up the skill's updated state
    skill = next((s for s in memory.learning.skills if s.skill_id == skill_id), None)
    after_learned = skill and skill.learned_at is not None
    just_graduated = bool(after_learned and not before_learned)

    return {
        "skill_id": skill_id,
        "kind": kind,
        "outcome_recorded": outcome,
        "stats": {
            "seen": (skill.seen if skill else 0),
            "correct": (skill.correct if skill else 0),
            "wrong": (skill.wrong if skill else 0),
        },
        "learned": bool(after_learned),
        "just_graduated": just_graduated,
    }


@router.post("/engine2/skill-seen")
async def engine2_skill_seen(
    req: Engine2SkillRequest,
    user: User = Depends(get_current_user),
):
    """Record that the user has SEEN a skill (viewed the lesson/page).
    Outcome is always 'seen' — doesn't graduate knowledge kinds on its own,
    but increments exposure for opening-style skills.
    """
    return await _record_engine2_skill(user.user_id, req.skill_id, "seen")


@router.post("/engine2/skill-completed")
async def engine2_skill_completed(
    req: Engine2SkillRequest,
    user: User = Depends(get_current_user),
):
    """Record that the user has COMPLETED a lesson/attempt. Outcome must
    be 'correct' or 'wrong' (defaults to 'correct' if omitted).
    For knowledge-type skills (endgame/mate/concept), a single 'correct'
    graduates the skill. `just_graduated: true` in the response lets the
    UI celebrate.
    """
    outcome = req.outcome or "correct"
    if outcome not in ("correct", "wrong"):
        raise HTTPException(status_code=400, detail="outcome must be 'correct' or 'wrong'")
    return await _record_engine2_skill(user.user_id, req.skill_id, outcome)


@router.get("/engine2/mastery-summary")
async def engine2_mastery_summary(user: User = Depends(get_current_user)):
    """User-facing mastery roll-up across the full Engine 2 skill tree.

    Returns the four-state model (unseen/learning/learned/stale) per skill,
    grouped by kind. Read-only — the underlying promotion logic runs inside
    record_skill_outcome; this endpoint just inspects the resulting state.
    """
    from services.coach_memory import get_or_create_memory
    from services.concept_mastery_service import summarize_mastery

    memory = await get_or_create_memory(db, user.user_id)
    return summarize_mastery(memory)
