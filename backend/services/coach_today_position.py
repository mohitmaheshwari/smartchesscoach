"""Today's position: his board, his move, and a question before any answer.

docs/home_as_a_coach_scope.md

This is the coaching moment and the thing no competitor does. A puzzle app shows
a position and marks the answer. A coach shows YOUR position, names the move YOU
played, and asks what you were checking before it says a word.

ASKING BEFORE TELLING IS THE WHOLE MECHANISM. A conclusion handed over is nodded
at and forgotten; a belief you committed to and got wrong is remembered. The
options are not decoration -- they are real misconceptions whose corrections are
already authored in `lesson_question_spec`, and the wrong one is named back as
something the player believed rather than something they failed.

THE ANSWER NEVER LEAVES THE SERVER until they have answered.

THE POSITION IS NOT ALWAYS ABOUT THE NAMED FOCUS, and that is deliberate.
Measured over the 49 players with an active weakness focus (2026-10-07):

    position must be about the focus topic .... reaches 33
    focus topic, else their largest topic ..... reaches 48

The sixteen it misses are not a data gap. Eight are focused on time_management,
which is behavioural and has no board positions by construction, and seven on
king_safety, where their own games have none. Mohit's own focus is
time_management -- so the strict rule shows nothing to the person looking at the
page, and would have looked fine to me because I would have tested on someone
else. A coach whose read is "the clock" still puts a board in front of you.

So the copy never claims the position is the focus. It says what is true: this
is a position from your game.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, Optional, Tuple

# Topics `lesson_question_spec` can ask a real question about AND for which a
# pool of the player's own positions exists. A topic missing from here is not
# unsupported chess, it is an unauthored question, and asking a made-up one is
# worse than showing no board.
ASKABLE_TOPICS: Tuple[str, ...] = (
    "piece_safety",
    "missed_tactic",
    "tactical_oversight",
    "calculation_depth",
    "king_safety",
)

# Same gap -> pool mapping the supply function uses. Imported there rather than
# restated, so the two cannot drift.


async def _own_counts(db, user_id: str) -> Dict[str, int]:
    """How many positions from this player's own games exist, per topic.

    A counting query, not a supply query -- it decides WHICH topic to ask the
    supply function for. The serving filters are not applied here on purpose:
    this only ranks candidates, and the supply function is still the thing that
    decides what is servable.
    """
    from services.puzzle_extraction_service import GAP_TO_PWC_PATTERNS

    counts: Dict[str, int] = {}
    cursor = db.community_puzzles.find(
        {"shared_by": user_id, "approved": True}, {"_id": 0, "issue_type": 1})
    async for doc in cursor:
        topic = doc.get("issue_type")
        if topic in ASKABLE_TOPICS:
            counts[topic] = counts.get(topic, 0) + 1

    pattern_to_gap = {}
    for gap, patterns in GAP_TO_PWC_PATTERNS.items():
        for pattern in patterns:
            pattern_to_gap.setdefault(pattern, gap)

    cursor = db.community_training_positions.find(
        {"source_user_id": user_id}, {"_id": 0, "pattern_type": 1})
    async for doc in cursor:
        gap = pattern_to_gap.get(doc.get("pattern_type"))
        if gap in ASKABLE_TOPICS:
            counts[gap] = counts.get(gap, 0) + 1

    return counts


async def choose_topic(db, user_id: str,
                       focus_topic: Optional[str]) -> Optional[str]:
    """The focus topic when their own games can show it, else their biggest.

    Returns None only when the player has no own position for any topic we have
    a question for -- one player of forty-nine, who gets no board rather than
    somebody else's.
    """
    counts = await _own_counts(db, user_id)
    if not counts:
        return None
    if focus_topic in counts:
        return focus_topic
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _options_for(spec) -> List[Dict[str, str]]:
    """The belief options, in an order that does not give the answer away.

    `spec.expected_reason` is `reason_options[0].id`, so the authored order puts
    the right answer first every time. Shipping that order would make the
    question answerable without looking at the board.
    """
    options = [{"id": o.id, "label": o.label} for o in spec.reason_options]
    random.shuffle(options)
    return options


async def todays_position(db, user_id: str,
                          focus_topic: Optional[str]) -> Optional[Dict[str, Any]]:
    """One position from this player's own games, with the question.

    Never falls back to a community or Lichess position: the sentence is "you
    played X here", and that is only true of their own game.
    """
    from services.lesson_question_spec import get_spec
    from services.puzzle_extraction_service import get_pattern_training_puzzles

    topic = await choose_topic(db, user_id, focus_topic)
    if not topic:
        return None

    # No authored question means no board. `get_spec` returns None rather than
    # the generic fallback for exactly this reason.
    spec = get_spec(topic)
    if spec is None or not spec.reason_options:
        return None

    try:
        supply = await get_pattern_training_puzzles(
            db, user_id, topic, 8, private=True)
    except Exception:
        return None

    own = [p for p in (supply.get("own_puzzles") or [])
           if p.get("fen") and p.get("played_move")
           and not p.get("already_solved")]
    if not own:
        return None
    position = own[0]

    return {
        "position_id": str(position.get("puzzle_id") or ""),
        "fen": position["fen"],
        # What they played, so the board is theirs and not a puzzle.
        "played_move": str(position["played_move"]),
        "move_number": position.get("move_number"),
        "user_color": position.get("user_color") or "white",
        "source_game_id": position.get("source_game_id"),
        "topic": topic,
        # True of every path above, and the only claim the copy makes.
        "from_your_game": True,
        # Asked BEFORE anything is explained, and about their thinking rather
        # than about the position.
        "ask": spec.reason_prompt,
        "options": _options_for(spec),
    }


def answer_for(topic: str, reason_id: Optional[str]) -> Dict[str, Any]:
    """What the coach says once they have committed to a reason.

    The right answer is confirmed, not congratulated. Telling someone they were
    correct about a move they got wrong is how a coach starts sounding like a
    form.
    """
    from services.lesson_question_spec import get_spec

    spec = get_spec(topic)
    option = spec.reason(reason_id) if (spec and reason_id) else None
    if spec is None or option is None:
        return {"ok": False, "reason": "unknown_option"}

    expected = option.id == spec.expected_reason
    return {
        "ok": True,
        "expected": expected,
        # What they believed, named back to them.
        "belief": option.belief_lead or "",
        # And where that belief breaks, when it does.
        "correction": option.correction or "",
        "misconception_id": option.misconception_id or None,
    }
