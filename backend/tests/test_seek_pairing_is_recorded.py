"""How long a player waited in the pool must survive the pairing.

The question a player asks before pressing "Find opponent" is "how long will
I wait", and Chessiro answers the adjacent one by showing Lichess's
site-wide online count ("Searching among 88,998 users"). We have no
sanctioned way to read that number -- Lichess's published API exposes only
/api/users/status and /api/bot/online -- so the honest answer is a number we
measure ourselves.

The seek already knew when it started. At the moment of pairing the code did
`_SEEKS.pop(user_id, None)` and threw that away, so the wait could never be
reported. These tests hold the recording in place, and hold the two
properties that make it trustworthy:

  * it is append-only, one row per pairing, so a distribution can be built.
    The guard's own lichess_live_play document upserts on user_id and is
    overwritten every game -- 25,620 games in the corpus and exactly one row
    in that collection.
  * a failed write never stops a game starting. The player is about to move.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.lichess_board_play import (  # noqa: E402
    PAIRINGS,
    LiveGame,
    SeekState,
    _record_pairing,
)


class FakeCollection:
    def __init__(self, explode: bool = False) -> None:
        self.rows = []
        self.explode = explode

    async def insert_one(self, doc):
        if self.explode:
            raise RuntimeError("mongo said no")
        self.rows.append(doc)


class FakeDb:
    def __init__(self, explode: bool = False) -> None:
        self.collections = {PAIRINGS: FakeCollection(explode)}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


def a_seek(seconds_ago: float, time_control: str = "10+0", rated: bool = True):
    started = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return SeekState(
        user_id="user_x",
        time_control=time_control,
        rated=rated,
        created_at=started.isoformat(),
    )


def a_game():
    return LiveGame(
        user_id="user_x",
        game_id="abc123",
        color="black",
        initial_fen="startpos",
        rated=True,
        speed="rapid",
        opponent={"username": "someone", "rating": 1500},
    )


def test_the_wait_is_recorded_not_discarded():
    db = FakeDb()
    asyncio.run(_record_pairing(db, "user_x", "abc123", a_seek(8.8), a_game()))

    rows = db[PAIRINGS].rows
    assert len(rows) == 1
    row = rows[0]
    # The number itself, which is the whole point.
    assert 8.0 <= row["waited_seconds"] <= 10.0
    assert row["lichess_game_id"] == "abc123"
    assert row["time_control"] == "10+0"
    assert row["rated"] is True


def test_it_is_append_only_so_a_distribution_can_be_built():
    # The guard's own document upserts on user_id; this one must not, or a
    # second game silently erases the first and the median is unknowable.
    db = FakeDb()
    for waited in (0.5, 8.8, 31.0):
        asyncio.run(
            _record_pairing(db, "user_x", f"g{waited}", a_seek(waited), a_game())
        )
    rows = db[PAIRINGS].rows
    assert len(rows) == 3
    assert sorted(round(r["waited_seconds"]) for r in rows) == [0, 9, 31]


def test_the_casual_and_rated_pools_are_told_apart():
    # They pair at very different speeds, so one pooled number would be a lie
    # to whichever player picked the other one.
    db = FakeDb()
    asyncio.run(_record_pairing(db, "user_x", "g1",
                                a_seek(4, rated=True), a_game()))
    asyncio.run(_record_pairing(db, "user_x", "g2",
                                a_seek(90, "15+10", rated=False), a_game()))
    rows = db[PAIRINGS].rows
    assert [r["rated"] for r in rows] == [True, False]
    assert [r["time_control"] for r in rows] == ["10+0", "15+10"]


def test_a_failed_write_does_not_stop_the_game_starting():
    db = FakeDb(explode=True)
    # Must not raise. A metric is never worth an exception on the path where
    # a human is about to make a move.
    asyncio.run(_record_pairing(db, "user_x", "abc123", a_seek(5), a_game()))


def test_nothing_is_written_when_there_was_no_seek():
    # A game can arrive from elsewhere (reconnect, a game started on lichess
    # itself). With no seek there is no wait, and inventing a zero would drag
    # every future median towards it.
    db = FakeDb()
    asyncio.run(_record_pairing(db, "user_x", "abc123", None, a_game()))
    assert db[PAIRINGS].rows == []


def test_no_database_is_not_an_error():
    asyncio.run(_record_pairing(None, "user_x", "abc123", a_seek(5), a_game()))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
