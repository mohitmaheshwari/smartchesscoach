"""Solving a position has to stop it coming back.

The picker skips positions you have already solved by reading
`puzzle_attempts`:

    solved = db.puzzle_attempts.find({"user_id": ..., "correct": True})
    own = [p for p in supply if not p["already_solved"]]

The personalized lesson never wrote there. It recorded into
`learning_sessions`, and nothing joined the two. Measured on production:

  - newest row in `puzzle_attempts`      2026-08-13
  - newest personalized lesson session   six weeks later
  - one account: 88 completed sessions, ONE distinct position, 0 attempts

So the same board came back for ever, and it was never a dedup bug -- the two
halves were simply not connected.

The id matters as much as the write. The picker matches `str(_id)` of the
community_puzzles row, which the item carries as `_puzzle_id` (underscored,
and easy to confuse with the `puzzle_id` key that is None on these items).
Recording under anything else would look fixed and change nothing, which is
what `test_the_id_recorded_is_the_id_the_picker_matches` is here to stop.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.teaching_engine import _record_puzzle_solve


class _Attempts:
    def __init__(self):
        self.rows = []
        self.calls = []

    async def update_one(self, query, update, upsert=False):
        self.calls.append((query, update, upsert))
        doc = dict(update.get("$setOnInsert") or {})
        if not any(r.get("puzzle_id") == doc.get("puzzle_id")
                   and r.get("user_id") == doc.get("user_id")
                   for r in self.rows):
            self.rows.append(doc)

    async def find(self, query, projection=None):
        return [r for r in self.rows
                if r.get("user_id") == query.get("user_id")
                and r.get("correct") is True]


class _DB:
    def __init__(self):
        self.puzzle_attempts = _Attempts()


SESSION = {"user_id": "u1", "session_id": "s1"}
ITEM = {"_puzzle_id": "69f2bc392bfd85c3af6cd0cf", "puzzle_id": None,
        "item_id": "69f2bc392bfd85c3af6cd0cf", "fen": "8/8/8/8/8/8/8/K6k w - - 0 1"}


def test_a_correct_answer_is_recorded():
    db = _DB()
    asyncio.run(_record_puzzle_solve(db, SESSION, ITEM, True))
    assert len(db.puzzle_attempts.rows) == 1
    row = db.puzzle_attempts.rows[0]
    assert row["user_id"] == "u1"
    assert row["correct"] is True
    assert row["source"] == "personalized_lesson"


def test_the_id_recorded_is_the_id_the_picker_matches():
    """`_puzzle_id`, not `puzzle_id`.

    The item carries both. `puzzle_id` is None on every one of these; the
    underscored key holds str(_id) of the community_puzzles row, which is what
    get_pattern_training_puzzles compares against.
    """
    db = _DB()
    asyncio.run(_record_puzzle_solve(db, SESSION, ITEM, True))
    assert db.puzzle_attempts.rows[0]["puzzle_id"] == "69f2bc392bfd85c3af6cd0cf"


def test_the_picker_would_now_skip_it():
    """The round trip, in the shape the picker actually uses."""
    db = _DB()
    asyncio.run(_record_puzzle_solve(db, SESSION, ITEM, True))

    solved = asyncio.run(
        db.puzzle_attempts.find({"user_id": "u1", "correct": True}))
    solved_ids = {row.get("puzzle_id") for row in solved}

    supply = [{"puzzle_id": "69f2bc392bfd85c3af6cd0cf", "fen": "..."},
              {"puzzle_id": "other0000000000000000000", "fen": "..."}]
    remaining = [p for p in supply if p["puzzle_id"] not in solved_ids]

    assert len(remaining) == 1, "the solved position must drop out of the pool"
    assert remaining[0]["puzzle_id"] == "other0000000000000000000"


def test_a_wrong_answer_records_nothing():
    db = _DB()
    asyncio.run(_record_puzzle_solve(db, SESSION, ITEM, False))
    assert db.puzzle_attempts.rows == []


def test_solving_the_same_position_twice_does_not_double_count():
    db = _DB()
    asyncio.run(_record_puzzle_solve(db, SESSION, ITEM, True))
    asyncio.run(_record_puzzle_solve(db, SESSION, ITEM, True))
    assert len(db.puzzle_attempts.rows) == 1
    assert all(call[2] is True for call in db.puzzle_attempts.calls), "must upsert"


def test_an_item_with_no_id_is_skipped_quietly():
    """Authored endgame/opening items have no puzzle to mark."""
    db = _DB()
    asyncio.run(_record_puzzle_solve(
        db, SESSION, {"item_id": "rook_endgames/active_rook:1"}, True))
    assert db.puzzle_attempts.rows == []


def test_a_broken_write_never_fails_the_answer():
    """Bookkeeping must not cost the player a move they got right."""
    class _Exploding:
        async def update_one(self, *a, **k):
            raise RuntimeError("mongo is having a day")

    class _BadDB:
        puzzle_attempts = _Exploding()

    asyncio.run(_record_puzzle_solve(_BadDB(), SESSION, ITEM, True))
