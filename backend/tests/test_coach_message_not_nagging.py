"""The coach may correct a player. It may not shout, and it may not keep score.

From one real 90-second game on 2026-09-10:

    Qxe6+ was a piece-safety blunder - 348cp lost   (x1)
    Qxe6+ was a piece-safety blunder - 356cp lost   (x1)
    Qxe6+ was a piece-safety blunder - 397cp lost   (x4)

Six messages for one move, with the cp figure drifting as async
re-evaluations landed. Each one ended "That's your 14th destination safety
exact today." The player's reaction, verbatim, was "i am just too shit stuff
man". The product told him that, six times, using an internal detector id.

Two rules follow, and these tests hold them:
  1. One move produces at most one message of a given type.
  2. Player-facing text never carries a running failure count or a detector id.
"""
import ast
import io
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

ROUTE = BACKEND / "routes" / "coach_play.py"
FOCUS = BACKEND / "services" / "focus_move_coaching.py"


class _FakeCollection:
    def __init__(self):
        self.docs = []

    async def update_one(self, key, update, upsert=False):
        for d in self.docs:
            if all(d.get(k) == v for k, v in key.items()):
                return type("R", (), {"upserted_id": None})()
        doc = dict(update.get("$setOnInsert") or {})
        self.docs.append(doc)
        return type("R", (), {"upserted_id": len(self.docs)})()

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return type("R", (), {"inserted_id": len(self.docs)})()


class _FakeDB:
    def __init__(self):
        self.coach_messages = _FakeCollection()


@pytest.mark.asyncio
async def test_one_move_yields_one_message_however_often_the_pipeline_reruns():
    from routes.coach_play import _insert_coach_message_once

    db = _FakeDB()
    for cp in (348, 356, 397, 397, 397, 397):   # the six real re-evaluations
        await _insert_coach_message_once(db, {
            "session_id": "s1",
            "type": "focus_coach",
            "move_san": "Qxe6+",
            "message": f"blunder - {cp}cp lost",
        })
    assert len(db.coach_messages.docs) == 1, (
        f"{len(db.coach_messages.docs)} messages for one move; the player is "
        "being shouted at once per async re-evaluation"
    )
    assert "348" in db.coach_messages.docs[0]["message"], (
        "the first verdict should stand; later passes must not rewrite it"
    )


@pytest.mark.asyncio
async def test_a_different_move_still_gets_its_own_message():
    from routes.coach_play import _insert_coach_message_once

    db = _FakeDB()
    for san in ("a4", "Qe2", "Qxe6+"):
        await _insert_coach_message_once(db, {
            "session_id": "s1", "type": "impulse_warning",
            "move_san": san, "message": san,
        })
    assert len(db.coach_messages.docs) == 3, "dedupe must not silence real moves"


def test_no_running_failure_count_in_player_text():
    """No "that's your Nth <thing> today" anywhere a player can read it."""
    offenders = []
    for path in (ROUTE, FOCUS):
        text = io.open(path, encoding="utf-8").read()
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue          # commentary explaining the removal is fine
            low = stripped.lower()
            if "impulsive move today" in low or "_ordinal(today" in low:
                offenders.append(f"{path.name}: {stripped[:90]}")
    assert not offenders, (
        "player-facing text keeps a running tally of failures:\n  "
        + "\n  ".join(offenders)
    )


def test_no_raw_detector_id_reaches_the_player():
    """"destination safety exact" is an internal id, not English."""
    text = io.open(FOCUS, encoding="utf-8").read()
    assert 'dominant_subtype.replace("_", " ")' not in text, (
        "a detector subtype id is being de-underscored and shown to the "
        "player; name the pattern in words instead"
    )


def test_impulse_warning_does_not_accuse_on_a_missing_timer():
    """0.0s means no thinking time arrived, not that they moved instantly."""
    source = io.open(ROUTE, encoding="utf-8").read()
    assert "_timed = isinstance(_tspent, (int, float)) and _tspent >= 0.5" in source, (
        "the impulse warning must check the timer is credible before quoting "
        "it; it accused a player of a 0.0s move while the same game recorded "
        "2057ms and 1694ms for earlier moves"
    )
