"""
Intent Selector — pick ONE teaching intent based on student profile + position.

Two-step process:
1. Rank intents by student need (what they struggle with)
2. Feasibility gate: verify the position can support the intent

If the top intent isn't feasible (no candidate move scores well for it),
fall through to the next. If nothing is feasible, return THREAT_AWARENESS
as the default (every position has some threats to notice).
"""

import logging
from typing import List, Optional, Dict

import chess

from .types import TeachingIntent, CandidateMove
from .teaching_evaluator import score_all_candidates, is_intent_feasible

logger = logging.getLogger(__name__)


# Maps student weakness clusters (from focus_engine) to teaching intents.
# Order within each list = priority when multiple intents match.
WEAKNESS_TO_INTENTS = {
    # Hangs pieces, doesn't see captures
    "threat_awareness": [
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.THREAT_AWARENESS,
        TeachingIntent.PIN_EXPLOITATION,
    ],
    # Misses tactics — broadest weakness, cycle through all patterns
    "calculation": [
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.DISCOVERED_ATTACK,
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.THREAT_AWARENESS,
    ],
    # Doesn't coordinate, leaves pieces loose
    "coordination": [
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.OVERLOADED_PIECE,
    ],
    # Rushed, doesn't check threats
    "patience": [
        TeachingIntent.THREAT_AWARENESS,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
    ],
    # No clear plan
    "planning": [
        TeachingIntent.OVERLOADED_PIECE,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.THREAT_AWARENESS,
    ],
    # Misses pins specifically
    "pin_blindness": [
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.THREAT_AWARENESS,
    ],
    # Misses multi-move tactical ideas
    "tactical_depth": [
        TeachingIntent.DISCOVERED_ATTACK,
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.OVERLOADED_PIECE,
    ],
    # ── Aliases for canonical CLAUDE.md cognitive_gap taxonomy ──
    # The Mirror and analysis pipelines produce these names. Mapping
    # them in directly avoids a translation layer between systems —
    # the Mirror's flagged pattern lands as a teaching intent on the
    # next coach session.
    "piece_safety": [
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.THREAT_AWARENESS,
    ],
    "king_safety": [
        TeachingIntent.THREAT_AWARENESS,
        TeachingIntent.DISCOVERED_ATTACK,
        TeachingIntent.PIN_EXPLOITATION,
    ],
    "tactical_oversight": [
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.DISCOVERED_ATTACK,
    ],
    "calculation_depth": [
        TeachingIntent.DISCOVERED_ATTACK,
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.OVERLOADED_PIECE,
    ],
    "missed_tactic": [
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
    ],
    "ignore_threat": [
        TeachingIntent.THREAT_AWARENESS,
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.PIN_EXPLOITATION,
    ],
    "piece_activity": [
        TeachingIntent.OVERLOADED_PIECE,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.FORK_OPPORTUNITY,
    ],
    "time_pressure": [
        TeachingIntent.THREAT_AWARENESS,
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
    ],
}

# Maps teaching_focus strings (from session) to intents
FOCUS_TO_INTENTS = {
    "tactics": [
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.DISCOVERED_ATTACK,
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.THREAT_AWARENESS,
    ],
    "prophylaxis": [
        TeachingIntent.THREAT_AWARENESS,
        TeachingIntent.OVERLOADED_PIECE,
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
    ],
    "king_safety": [
        TeachingIntent.DISCOVERED_ATTACK,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.THREAT_AWARENESS,
    ],
    "endgame_technique": [
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.THREAT_AWARENESS,
    ],
    "development": [
        TeachingIntent.THREAT_AWARENESS,
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.FORK_OPPORTUNITY,
    ],
    "piece_activity": [
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.OVERLOADED_PIECE,
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.THREAT_AWARENESS,
    ],
    "natural_play": [
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.DISCOVERED_ATTACK,
        TeachingIntent.OVERLOADED_PIECE,
        TeachingIntent.THREAT_AWARENESS,
    ],
}

# Default intent order: most specific first, broadest last.
# Hanging piece and fork are harder to satisfy but produce stronger teaching
# signals when they DO trigger. Threat awareness is the catch-all fallback.
DEFAULT_INTENT_ORDER = [
    TeachingIntent.PIN_EXPLOITATION,
    TeachingIntent.FORK_OPPORTUNITY,
    TeachingIntent.DISCOVERED_ATTACK,
    TeachingIntent.SKEWER_OPPORTUNITY,
    TeachingIntent.OVERLOADED_PIECE,
    TeachingIntent.HANGING_PIECE_PUNISHMENT,
    TeachingIntent.THREAT_AWARENESS,
]


# Intents available at each rating tier. A 900 shouldn't see skewers.
# Order within each tier = rough teaching progression.
INTENTS_BY_RATING = {
    # Under 1000: basics only — hanging pieces, simple forks, basic threats
    1000: {
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.THREAT_AWARENESS,
    },
    # 1000-1200: add absolute pins
    1200: {
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.THREAT_AWARENESS,
        TeachingIntent.PIN_EXPLOITATION,
    },
    # 1200-1500: add skewers and overloaded pieces
    1500: {
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.THREAT_AWARENESS,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.OVERLOADED_PIECE,
    },
    # 1500+: full range including discovered attacks
    9999: {
        TeachingIntent.HANGING_PIECE_PUNISHMENT,
        TeachingIntent.FORK_OPPORTUNITY,
        TeachingIntent.THREAT_AWARENESS,
        TeachingIntent.PIN_EXPLOITATION,
        TeachingIntent.SKEWER_OPPORTUNITY,
        TeachingIntent.DISCOVERED_ATTACK,
        TeachingIntent.OVERLOADED_PIECE,
    },
}


def _get_allowed_intents(user_rating: int) -> set:
    """Get the set of intents appropriate for this rating."""
    for threshold in sorted(INTENTS_BY_RATING.keys()):
        if user_rating < threshold:
            return INTENTS_BY_RATING[threshold]
    return INTENTS_BY_RATING[9999]


def rank_intents(
    teaching_focus: Optional[str] = None,
    student_weaknesses: Optional[List[str]] = None,
    last_game_violations: Optional[List[str]] = None,
    user_rating: int = 1200,
) -> List[TeachingIntent]:
    """
    Rank intents by student need. Returns ordered list, best first.

    Filters by rating — a 900 player only sees hanging pieces, forks,
    and basic threats. Pins, skewers, discoveries are added as they
    progress.

    Args:
        teaching_focus: Session-level focus string (e.g. "tactics", "prophylaxis")
        student_weaknesses: Weakness clusters from focus_engine
        last_game_violations: Fundamental violations from previous game session
            (for learning loop — bias toward repeating these patterns)
        user_rating: Student's rating — filters out complex patterns for beginners

    Returns:
        Ordered list of TeachingIntent, most relevant first
    """
    allowed = _get_allowed_intents(user_rating)

    # Start with an intent→score dict (only allowed intents)
    scores: Dict[TeachingIntent, float] = {
        intent: 0.0 for intent in TeachingIntent if intent in allowed
    }

    # 1. Teaching focus (strongest signal — explicit user/system choice)
    if teaching_focus and teaching_focus in FOCUS_TO_INTENTS:
        for i, intent in enumerate(FOCUS_TO_INTENTS[teaching_focus]):
            if intent in scores:
                scores[intent] += 3.0 - i * 0.5  # 3.0, 2.5, 2.0

    # 2. Student weaknesses from focus_engine
    if student_weaknesses:
        for weakness in student_weaknesses:
            if weakness in WEAKNESS_TO_INTENTS:
                for i, intent in enumerate(WEAKNESS_TO_INTENTS[weakness]):
                    if intent in scores:
                        scores[intent] += 2.0 - i * 0.5

    # 3. Learning loop: bias toward last game's violations
    if last_game_violations:
        violation_to_intent = {
            "check_opponents_move": TeachingIntent.THREAT_AWARENESS,
            "hanging_pieces": TeachingIntent.HANGING_PIECE_PUNISHMENT,
            "calculate": TeachingIntent.FORK_OPPORTUNITY,
            "missed_pin": TeachingIntent.PIN_EXPLOITATION,
            "missed_skewer": TeachingIntent.SKEWER_OPPORTUNITY,
            "missed_discovery": TeachingIntent.DISCOVERED_ATTACK,
            "missed_tactic": TeachingIntent.FORK_OPPORTUNITY,
            "piece_coordination": TeachingIntent.OVERLOADED_PIECE,
        }
        for violation in last_game_violations:
            intent = violation_to_intent.get(violation)
            if intent and intent in scores:
                scores[intent] += 1.5  # Meaningful but doesn't override explicit focus

    # 4. If nothing scored, use defaults (filtered by rating)
    if all(v == 0.0 for v in scores.values()):
        for i, intent in enumerate(DEFAULT_INTENT_ORDER):
            if intent in scores:
                scores[intent] = 1.0 - i * 0.1

    # Sort by score descending
    ranked = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    return ranked


def select_intent(
    board: chess.Board,
    candidates: List[CandidateMove],
    coach_color: chess.Color,
    teaching_focus: Optional[str] = None,
    student_weaknesses: Optional[List[str]] = None,
    last_game_violations: Optional[List[str]] = None,
    user_rating: int = 1200,
) -> tuple:
    """
    Select the best feasible teaching intent for this position.

    Two-step: rank by student need, then verify position supports it.

    Args:
        board: Current position (before coach's move)
        candidates: Generated candidate moves
        coach_color: Coach's color
        teaching_focus: Session focus string
        student_weaknesses: Focus engine clusters
        last_game_violations: Previous session violations (learning loop)

    Returns:
        (selected_intent, intent_reason, all_scores, fallback_count)
        - selected_intent: The TeachingIntent to use
        - intent_reason: Why this intent was chosen
        - all_scores: IntentScore list for the selected intent
        - fallback_count: How many intents were tried before finding a feasible one
    """
    ranked = rank_intents(teaching_focus, student_weaknesses, last_game_violations,
                          user_rating=user_rating)

    fallbacks = 0
    for intent in ranked:
        # Score all candidates for this intent
        scores = score_all_candidates(board, candidates, intent, coach_color,
                                       user_rating=user_rating)

        if is_intent_feasible(scores):
            reason = _build_reason(intent, teaching_focus, student_weaknesses,
                                   last_game_violations, fallbacks)
            logger.info(
                f"[INTENT] Selected {intent.value} "
                f"(fallbacks={fallbacks}, focus={teaching_focus})"
            )
            return intent, reason, scores, fallbacks

        fallbacks += 1
        logger.debug(f"[INTENT] {intent.value} not feasible, trying next")

    # Nothing feasible — fall back to THREAT_AWARENESS with whatever scores we get
    # (every position has SOME threats, even if weak)
    logger.warning("[INTENT] No intent feasible, defaulting to THREAT_AWARENESS")
    scores = score_all_candidates(
        board, candidates, TeachingIntent.THREAT_AWARENESS, coach_color,
        user_rating=user_rating,
    )
    return (
        TeachingIntent.THREAT_AWARENESS,
        "default fallback — no intent had feasible positions",
        scores,
        fallbacks,
    )


def _build_reason(
    intent: TeachingIntent,
    teaching_focus: Optional[str],
    student_weaknesses: Optional[List[str]],
    last_game_violations: Optional[List[str]],
    fallbacks: int,
) -> str:
    """Build a human-readable reason for the intent selection."""
    parts = []

    if fallbacks > 0:
        parts.append(f"after {fallbacks} fallback(s)")

    if teaching_focus:
        parts.append(f"session focus: {teaching_focus}")

    if student_weaknesses:
        parts.append(f"student struggles with: {', '.join(student_weaknesses)}")

    if last_game_violations:
        parts.append(f"repeated from last game: {', '.join(last_game_violations[:2])}")

    if not parts:
        parts.append("default priority order")

    return f"{intent.value} — {'; '.join(parts)}"
