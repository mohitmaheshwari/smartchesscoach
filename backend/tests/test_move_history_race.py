"""A coach move must never be lost or duplicated by a concurrent writer.

Every writer used to read the whole move_history array, append locally, and
$set it all back. Five sites did that, and THREE appended a COACH move
(trigger_coach_move_endpoint, _apply_coach_move, _process_move_and_respond), so
two writers could resolve the same turn. Last writer won; the other move was
silently discarded.

Observed in a real game on 2026-09-10:

  * /coach/play/trigger-coach-move returned coach_move "e5" and a FEN with the
    pawn on e5, while the stored history recorded "e6" -- so a black pawn
    appeared to move backwards after the player's next move.
  * The same game stored "dxe4" twice, with byte-identical fen_before and
    fen_after.
  * The HAR showed paired requests landing in the same millisecond four times.

A sixth site was worse: the evaluation-enrichment write mutated one existing
entry and then wrote the WHOLE array back from a stale read, erasing any coach
move that had landed in between. That is the likeliest mechanism behind e5->e6.

_append_move_atomically replaces all of it with a compare-and-swap: $push to
append atomically, and the update only applies when current_fen still matches
the board the caller reasoned from AND move_history is still exactly N long.
"""
import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from routes.coach_play import _append_move_atomically  # noqa: E402

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
AFTER_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
AFTER_E6 = "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"


class _Sessions:
    """Minimal store with MongoDB's actual semantics for $push and dotted filters."""

    def __init__(self, doc):
        self.doc = doc
        self.writes = 0

    async def update_one(self, flt, update):
        self.writes += 1
        doc = self.doc
        for key, want in flt.items():
            if key.startswith("move_history."):
                idx = int(key.split(".")[1])
                exists = idx < len(doc.get("move_history", []))
                if want.get("$exists") is not exists:
                    return type("R", (), {"modified_count": 0})()
            elif doc.get(key) != want:
                return type("R", (), {"modified_count": 0})()
        for k, v in (update.get("$push") or {}).items():
            doc.setdefault(k, []).append(v)
        for k, v in (update.get("$set") or {}).items():
            doc[k] = v
        return type("R", (), {"modified_count": 1})()


class _DB:
    def __init__(self, doc):
        self.coach_sessions = _Sessions(doc)


def _entry(san, by, before, after):
    return {"move": san, "by": by, "fen_before": before, "fen_after": after}


@pytest.mark.asyncio
async def test_the_first_writer_wins_and_the_second_is_rejected():
    """The e5/e6 case: two paths resolve the same turn."""
    db = _DB({"session_id": "s1", "current_fen": AFTER_E4, "move_history": [
        _entry("e4", "player", START, AFTER_E4)]})

    first = await _append_move_atomically(
        db, "s1", entry=_entry("e5", "coach", AFTER_E4, AFTER_E5),
        fen_before=AFTER_E4, fen_after=AFTER_E5, expected_history_length=1)
    second = await _append_move_atomically(
        db, "s1", entry=_entry("e6", "coach", AFTER_E4, AFTER_E6),
        fen_before=AFTER_E4, fen_after=AFTER_E6, expected_history_length=1)

    assert first is True
    assert second is False, "the second writer must not overwrite the first"
    hist = db.coach_sessions.doc["move_history"]
    assert [m["move"] for m in hist] == ["e4", "e5"]
    assert db.coach_sessions.doc["current_fen"] == AFTER_E5, (
        "the board must agree with the move that was actually stored"
    )


@pytest.mark.asyncio
async def test_the_same_move_is_never_appended_twice():
    """The duplicated dxe4 case: identical entry submitted twice."""
    db = _DB({"session_id": "s1", "current_fen": AFTER_E4, "move_history": [
        _entry("e4", "player", START, AFTER_E4)]})
    e = _entry("e5", "coach", AFTER_E4, AFTER_E5)

    assert await _append_move_atomically(
        db, "s1", entry=e, fen_before=AFTER_E4, fen_after=AFTER_E5,
        expected_history_length=1) is True
    assert await _append_move_atomically(
        db, "s1", entry=e, fen_before=AFTER_E4, fen_after=AFTER_E5,
        expected_history_length=1) is False
    assert len(db.coach_sessions.doc["move_history"]) == 2


@pytest.mark.asyncio
async def test_one_hundred_concurrent_writers_produce_exactly_one_move():
    """The gate: no duplicated and no lost move under real concurrency."""
    db = _DB({"session_id": "s1", "current_fen": AFTER_E4, "move_history": [
        _entry("e4", "player", START, AFTER_E4)]})

    async def attempt(n):
        return await _append_move_atomically(
            db, "s1",
            entry=_entry(f"cand{n}", "coach", AFTER_E4, AFTER_E5),
            fen_before=AFTER_E4, fen_after=AFTER_E5,
            expected_history_length=1)

    results = await asyncio.gather(*(attempt(i) for i in range(100)))
    assert sum(1 for r in results if r) == 1, (
        f"{sum(1 for r in results if r)} writers believed they moved"
    )
    assert len(db.coach_sessions.doc["move_history"]) == 2


@pytest.mark.asyncio
async def test_a_stale_board_is_rejected_even_at_the_right_length():
    """Length alone is not enough -- the board must match too."""
    db = _DB({"session_id": "s1", "current_fen": AFTER_E5, "move_history": [
        _entry("e4", "player", START, AFTER_E4),
        _entry("e5", "coach", AFTER_E4, AFTER_E5)]})
    assert await _append_move_atomically(
        db, "s1", entry=_entry("e6", "coach", AFTER_E4, AFTER_E6),
        fen_before=AFTER_E4, fen_after=AFTER_E6,
        expected_history_length=2) is False


@pytest.mark.asyncio
async def test_the_winner_may_set_extra_fields_and_the_loser_may_not():
    db = _DB({"session_id": "s1", "current_fen": AFTER_E4, "move_history": [
        _entry("e4", "player", START, AFTER_E4)]})
    await _append_move_atomically(
        db, "s1", entry=_entry("e5", "coach", AFTER_E4, AFTER_E5),
        fen_before=AFTER_E4, fen_after=AFTER_E5, expected_history_length=1,
        extra_set={"coach_move_pending": False, "status": "active"})
    assert db.coach_sessions.doc["coach_move_pending"] is False

    await _append_move_atomically(
        db, "s1", entry=_entry("e6", "coach", AFTER_E4, AFTER_E6),
        fen_before=AFTER_E4, fen_after=AFTER_E6, expected_history_length=1,
        extra_set={"status": "clobbered"})
    assert db.coach_sessions.doc["status"] == "active", (
        "a rejected writer must not apply its side effects either"
    )


def test_no_writer_still_replaces_the_whole_array():
    """Static guard: the read-modify-write pattern must not come back."""
    import io
    src = io.open(BACKEND / "routes" / "coach_play.py", encoding="utf-8").read()
    offenders = [
        line.strip() for line in src.splitlines()
        if '"move_history": move_history' in line
        and not line.strip().startswith("#")
        and "write it ALL back" not in line
    ]
    assert not offenders, (
        "a writer is replacing the whole move_history array again:\n  "
        + "\n  ".join(offenders)
    )
