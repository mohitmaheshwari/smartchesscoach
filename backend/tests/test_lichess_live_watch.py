"""The Lichess live watcher: does it fire a sync exactly when a game ends?

The watcher's whole job is to turn "within 5 minutes" into "within ~10
seconds" for a finished Lichess game. Everything risky about it is in one
state machine -- deciding, from two consecutive `users/status` replies, that a
game has ended -- so that is what these tests pin down, including the cases
where it must stay silent.

No network and no Mongo: the HTTP getter and the sync function are injected.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.lichess_live_watch import (  # noqa: E402
    MAX_IDS_PER_REQUEST,
    PER_USER_SYNC_COOLDOWN_SECONDS,
    WatchState,
    fetch_statuses,
    run_cycle,
)


# ---------------------------------------------------------------- fakes


class FakeResponse:
    def __init__(self, body: Any, status_code: int = 200, raises: bool = False):
        self._body = body
        self.status_code = status_code
        self._raises = raises

    def json(self):
        if self._raises:
            raise ValueError("not json")
        return self._body


class FakeCursor:
    def __init__(self, docs: List[dict]):
        self._docs = docs

    async def to_list(self, _limit):
        return self._docs


class FakeUsers:
    def __init__(self, docs: List[dict]):
        self._docs = docs
        self.queries: List[dict] = []

    def find(self, query, _projection=None):
        self.queries.append(query)
        return FakeCursor(self._docs)


class FakeDb:
    def __init__(self, docs: List[dict]):
        self.users = FakeUsers(docs)


def status(name: str, playing: bool, game_id: Optional[str] = None) -> dict:
    entry = {"id": name, "name": name, "online": True, "playing": playing}
    if playing and game_id:
        entry["playingId"] = game_id
    return entry


# ------------------------------------------------- the state machine


def test_first_sighting_of_a_player_mid_game_is_not_a_finished_game():
    """We only learn a game ended by seeing it stop. Seeing it start is not that."""
    state = WatchState()
    assert state.games_that_just_ended([status("mohit", True, "abc")]) == []
    assert state.playing["mohit"] == "abc"


def test_a_game_that_stops_is_reported_once():
    state = WatchState()
    state.games_that_just_ended([status("mohit", True, "abc")])
    assert state.games_that_just_ended([status("mohit", False)]) == ["mohit"]
    # And not again on the next quiet cycle.
    assert state.games_that_just_ended([status("mohit", False)]) == []


def test_the_same_game_continuing_reports_nothing():
    state = WatchState()
    state.games_that_just_ended([status("mohit", True, "abc")])
    for _ in range(5):
        assert state.games_that_just_ended([status("mohit", True, "abc")]) == []


def test_straight_into_the_next_game_still_counts_as_one_finished():
    """Rematch: the id changes without ever passing through "not playing"."""
    state = WatchState()
    state.games_that_just_ended([status("mohit", True, "abc")])
    assert state.games_that_just_ended([status("mohit", True, "def")]) == ["mohit"]
    assert state.playing["mohit"] == "def"


def test_a_player_lichess_omits_is_left_alone():
    """Absence is not evidence. Guessing here would fire a sync every cycle."""
    state = WatchState()
    state.games_that_just_ended([status("mohit", True, "abc")])
    assert state.games_that_just_ended([]) == []
    # Still remembered as playing, so the real finish is caught later.
    assert state.playing["mohit"] == "abc"
    assert state.games_that_just_ended([status("mohit", False)]) == ["mohit"]


def test_several_players_are_tracked_independently():
    state = WatchState()
    state.games_that_just_ended(
        [status("a", True, "g1"), status("b", True, "g2"), status("c", False)]
    )
    ended = state.games_that_just_ended(
        [status("a", False), status("b", True, "g2"), status("c", True, "g3")]
    )
    assert ended == ["a"]


def test_junk_entries_do_not_crash_the_cycle():
    state = WatchState()
    assert state.games_that_just_ended(
        ["nonsense", None, {}, {"id": ""}, 42]  # type: ignore[list-item]
    ) == []


def test_case_is_normalised_so_stored_and_returned_names_match():
    state = WatchState()
    state.games_that_just_ended([{"id": "MoHiT", "playing": True, "playingId": "abc"}])
    assert "mohit" in state.playing
    assert state.games_that_just_ended([{"id": "mohit", "playing": False}]) == ["mohit"]


# ---------------------------------------------------------- cooldown


def test_the_cooldown_stops_a_rapid_replay_of_syncs():
    state = WatchState()
    assert state.may_sync("mohit", now=1000.0) is True
    assert state.may_sync("mohit", now=1000.0 + PER_USER_SYNC_COOLDOWN_SECONDS - 1) is False
    assert state.may_sync("mohit", now=1000.0 + PER_USER_SYNC_COOLDOWN_SECONDS + 1) is True


def test_the_cooldown_is_per_player():
    state = WatchState()
    assert state.may_sync("a", now=1000.0) is True
    assert state.may_sync("b", now=1000.0) is True


# ------------------------------------------------------ fetch_statuses


def test_ids_are_chunked_at_the_lichess_cap():
    names = [f"p{i}" for i in range(MAX_IDS_PER_REQUEST * 2 + 7)]
    calls: List[dict] = []

    async def http_get(url, params=None, headers=None):
        calls.append(params or {})
        return FakeResponse([status(n, False) for n in (params or {})["ids"].split(",")])

    out = asyncio.run(fetch_statuses(names, http_get))
    assert len(calls) == 3
    assert all(len(c["ids"].split(",")) <= MAX_IDS_PER_REQUEST for c in calls)
    assert len(out) == len(names)
    assert calls[0]["withGameIds"] == "true"


def test_a_user_agent_is_always_sent():
    """Lichess may reject or throttle a request without one."""
    seen: List[dict] = []

    async def http_get(url, params=None, headers=None):
        seen.append(headers or {})
        return FakeResponse([])

    asyncio.run(fetch_statuses(["a"], http_get))
    assert seen and seen[0].get("User-Agent")


def test_rate_limiting_stops_the_cycle_rather_than_hammering():
    calls: List[int] = []

    async def http_get(url, params=None, headers=None):
        calls.append(1)
        return FakeResponse(None, status_code=429)

    names = [f"p{i}" for i in range(MAX_IDS_PER_REQUEST * 2)]
    assert asyncio.run(fetch_statuses(names, http_get)) == []
    assert len(calls) == 1, "a 429 must abandon the cycle, not try the next chunk"


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(None, status_code=503),
        FakeResponse(None, raises=True),
        FakeResponse({"not": "a list"}),
    ],
)
def test_a_bad_reply_yields_nothing_and_does_not_raise(response):
    async def http_get(url, params=None, headers=None):
        return response

    assert asyncio.run(fetch_statuses(["a"], http_get)) == []


def test_a_network_error_yields_nothing_and_does_not_raise():
    async def http_get(url, params=None, headers=None):
        raise OSError("connection reset")

    assert asyncio.run(fetch_statuses(["a"], http_get)) == []


# ----------------------------------------------------------- run_cycle


def _db_with(*names: str) -> FakeDb:
    return FakeDb(
        [{"user_id": f"user_{n}", "lichess_username": n} for n in names]
    )


def test_a_finished_game_syncs_exactly_that_user():
    db = _db_with("mohit", "arjun")
    state = WatchState()
    synced: List[str] = []

    async def sync(_db, user_id, _doc):
        synced.append(user_id)
        return 1

    replies = [
        [status("mohit", True, "abc"), status("arjun", True, "xyz")],
        [status("mohit", False), status("arjun", True, "xyz")],
    ]

    async def http_get(url, params=None, headers=None):
        return FakeResponse(replies.pop(0))

    # Cycle 1: both start playing -- nothing finished yet (the positive control
    # for the zero below).
    assert asyncio.run(run_cycle(db, state, http_get, sync)) == 0
    assert synced == []

    # Cycle 2: only mohit's game ended.
    assert asyncio.run(run_cycle(db, state, http_get, sync)) == 1
    assert synced == ["user_mohit"]


def test_the_user_query_cannot_regress_to_the_duplicate_key_form():
    """`{"$ne": None, "$ne": ""}` silently drops the None test. Pin `$nin`."""
    db = _db_with("mohit")

    async def http_get(url, params=None, headers=None):
        return FakeResponse([])

    async def sync(_db, _uid, _doc):
        return 0

    asyncio.run(run_cycle(db, WatchState(), http_get, sync))
    assert db.users.queries == [{"lichess_username": {"$nin": [None, ""]}}]


def test_a_failing_sync_does_not_stop_the_other_users():
    db = _db_with("a", "b")
    state = WatchState()
    done: List[str] = []

    async def sync(_db, user_id, _doc):
        if user_id == "user_a":
            raise RuntimeError("lichess 500")
        done.append(user_id)
        return 1

    replies = [
        [status("a", True, "g1"), status("b", True, "g2")],
        [status("a", False), status("b", False)],
    ]

    async def http_get(url, params=None, headers=None):
        return FakeResponse(replies.pop(0))

    asyncio.run(run_cycle(db, state, http_get, sync))
    fired = asyncio.run(run_cycle(db, state, http_get, sync))
    assert done == ["user_b"]
    assert fired == 1, "only the successful sync counts"


def test_no_connected_users_means_no_http_call_at_all():
    calls: List[int] = []

    async def http_get(url, params=None, headers=None):
        calls.append(1)
        return FakeResponse([])

    async def sync(_db, _uid, _doc):
        return 0

    assert asyncio.run(run_cycle(FakeDb([]), WatchState(), http_get, sync)) == 0
    assert calls == [], "do not call Lichess when nobody has connected an account"
