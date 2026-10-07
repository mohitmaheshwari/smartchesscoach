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

from pymongo import ReturnDocument

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


ANSWERS = "home_today_answers"


async def ensure_answer_indexes(db) -> None:
    """Indexes for the two collections the home page reads on every load.

    `_answered_position_ids` scans every row for a user on each page load and
    `last_answer` sorts them, so both are on the critical path of a page that
    is already a three-second load. Declared here and called from the app
    lifespan, which is where the other `ensure_*_indexes` live -- the
    `ensure_product_event_indexes` next door is defined and never called by
    anything, which is how its collection ended up unindexed.
    """
    await db[ANSWERS].create_index([("user_id", 1), ("position_id", 1)],
                                   unique=True)
    await db[ANSWERS].create_index([("user_id", 1), ("topic", 1),
                                    ("answered_at", -1)])
    await db.user_misconceptions.create_index(
        [("user_id", 1), ("misconception_id", 1)], unique=True)
    await db.user_misconceptions.create_index([("user_id", 1), ("topic", 1)])


async def _answered_position_ids(db, user_id: str) -> set:
    """Positions this player has already answered on the home page.

    THE BOARD HAS TO ADVANCE AND IT DID NOT. Mohit, 2026-10-07: *"it won't
    change over time, or would it?"* It would not. Answering wrote
    `user_misconceptions`, keyed by misconception, while the supply function's
    `already_solved` filter reads `puzzle_attempts` -- a different collection
    that nothing on this path writes. The same position at move 49 would have
    come back every day forever.

    A separate record rather than `puzzle_attempts` with `correct: True`,
    because they did not solve anything: they named what they were checking.
    Writing a solve would be a lie, and `solve_rate` feeds the ordering of
    every other pool.
    """
    try:
        cursor = db[ANSWERS].find(
            {"user_id": user_id}, {"_id": 0, "position_id": 1})
        return {d.get("position_id") async for d in cursor if d.get("position_id")}
    except Exception:
        # A read failure must not freeze the board on the oldest position; an
        # empty set means they are offered one they may have seen, which is
        # the lesser of the two.
        return set()


async def last_answer(db, user_id: str,
                      topic: str) -> Optional[Dict[str, Any]]:
    """What they told me last time about this same topic, if anything.

    This is the beat that makes it a second session rather than a first one
    again. A coach opens with "last time you said you were checking the square
    it landed on" -- not because the fact is interesting, but because being
    remembered is the whole difference between a coach and a worksheet.
    """
    try:
        doc = await db[ANSWERS].find_one(
            {"user_id": user_id, "topic": topic},
            {"_id": 0, "reason_id": 1, "expected": 1, "answered_at": 1},
            sort=[("answered_at", -1)])
    except Exception:
        return None
    if not doc or not doc.get("reason_id"):
        return None

    from services.lesson_question_spec import get_spec
    spec = get_spec(topic)
    option = spec.reason(doc["reason_id"]) if spec else None
    if option is None:
        return None
    return {
        "reason_id": option.id,
        # Their own words back, not a paraphrase.
        "said": option.label,
        "was_expected": bool(doc.get("expected")),
    }


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

    answered = await _answered_position_ids(db, user_id)

    # Fetched deeper than one so that answering today leaves something for
    # tomorrow. At a limit of 8 a player who answers daily would run out
    # inside a fortnight and the board would silently vanish.
    try:
        supply = await get_pattern_training_puzzles(
            db, user_id, topic, 40, private=True)
    except Exception:
        return None

    own = [p for p in (supply.get("own_puzzles") or [])
           if p.get("fen") and p.get("played_move")
           and not p.get("already_solved")
           and str(p.get("puzzle_id") or "") not in answered]
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
        # "Last time you told me..." -- the continuity beat. None on the first
        # session, which is correct: there is nothing to remember yet.
        "last_time": await last_answer(db, user_id, topic),
        # How many of their own positions are left behind this one, so the page
        # can stop promising a board it is about to run out of.
        "remaining": len(own),
    }


def repeat_note(times_held: int) -> Optional[str]:
    """What changes when they tell me the same wrong thing again.

    SAYING THE SAME CORRECTION TWICE IS WHAT A WORKSHEET DOES. Three simulated
    sessions on real data produced the identical paragraph three times, which
    is the static feeling Mohit was pointing at even after the board started
    moving. A coach who has corrected you once does not repeat himself -- he
    notices, and he gets more concrete.

    No count is spoken. "That is the third time" is a failure scoreboard, and
    the standing rule against those exists for good reason.
    """
    if times_held <= 1:
        return None
    if times_held == 2:
        return ("You told me the same thing last time. That is worth knowing "
                "about yourself -- it is a habit, not a slip.")
    return ("This keeps being your answer. Let us make it mechanical: before "
            "you commit, say out loud what their best reply is.")


async def record_answer(db, user_id: str, position_id: Optional[str],
                        topic: str, reason_id: str,
                        answer: Mapping[str, Any]) -> int:
    """Remember what they said, so tomorrow is the next session not this one.

    Two writes, deliberately: one row per position answered, which is what
    advances the board, and the running count per misconception, which is what
    lets the coach notice a repeat rather than re-reading its script.

    Returns how many times they have now held this belief -- 0 when they were
    right, since being right is not a thing to count against anyone.
    """
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if position_id:
        await db[ANSWERS].update_one(
            {"user_id": user_id, "position_id": position_id},
            {"$set": {"topic": topic, "reason_id": reason_id,
                      "expected": bool(answer.get("expected")),
                      "misconception_id": answer.get("misconception_id"),
                      "answered_at": now},
             "$setOnInsert": {"first_answered_at": now}},
            upsert=True)

    if not answer.get("misconception_id"):
        # THEY GOT IT RIGHT, SO THE COUNT HAS TO BE ABLE TO COME DOWN.
        #
        # A lifetime counter that only rises is the same disease as the finding
        # that only counts up: it can never resolve, so "this keeps being your
        # answer" would follow someone around for a habit they fixed months
        # ago. One credit per right answer, not a reset, because one good
        # session does not undo a habit -- the same shape as the recovery
        # credit in pattern_decay_service.
        try:
            await db.user_misconceptions.update_many(
                {"user_id": user_id, "topic": topic,
                 "times_held": {"$gt": 0}},
                {"$inc": {"times_held": -1},
                 "$set": {"last_credited_at": now}})
        except Exception:
            pass
        return 0

    doc = await db.user_misconceptions.find_one_and_update(
        {"user_id": user_id, "misconception_id": answer["misconception_id"]},
        {"$inc": {"times_held": 1},
         "$set": {"last_held_at": now, "topic": topic},
         "$setOnInsert": {"first_held_at": now}},
        upsert=True,
        # AFTER, so the count includes the answer just given. BEFORE would be
        # off by one and the second repeat would read as the first.
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0, "times_held": 1},
    )
    return int((doc or {}).get("times_held") or 1)


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
