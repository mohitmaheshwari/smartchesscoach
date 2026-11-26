"""The live-play guard must actually refuse, and must actually stay out of the way.

`test_no_coaching_during_a_live_lichess_game.py` is the structural gate: it
proves the guard exists, denies unknown paths by default, is installed as
middleware, and covers the whole route table. All of that can be true of a
guard that never fires, or of one that fires on everybody.

So this drives the ASGI middleware directly, with a fake inner app and a fake
database, and asserts what happens to a real request. No Mongo, no network, no
uvicorn.

The two failures worth most here are opposite:

  - a guard that does not fire gets a real person's Lichess account marked as
    an engine user;
  - a guard that fires too widely takes the product down for everyone, which is
    why `test_a_bystander_is_never_blocked` and `test_nothing_is_blocked_when_
    nobody_is_playing` matter as much as the refusal test.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import live_play_guard as guard  # noqa: E402

PLAYER = "user_playing_right_now"
BYSTANDER = "user_minding_their_own_business"
BLOCKED_PATH = "/api/coach/decryption/v5/some-game"   # a review: engine-derived
ALLOWED_PATH = "/api/coach/play/live/move"            # relaying their own move


class FakeSessions:
    """Stands in for db.user_sessions."""

    def __init__(self, tokens: Dict[str, str]):
        self._tokens = tokens

    async def find_one(self, query, _projection=None):
        token = query.get("session_token")
        user_id = self._tokens.get(token)
        return {"user_id": user_id} if user_id else None


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def __aiter__(self):
        async def gen():
            for row in self._rows:
                yield row

        return gen()


class FakeLivePlay:
    """Stands in for db.lichess_live_play."""

    def __init__(self, playing: Optional[List[str]] = None):
        self.rows = {u: {"user_id": u, "status": "playing"} for u in (playing or [])}

    async def find_one(self, query, _projection=None):
        row = self.rows.get(query.get("user_id"))
        if row and row.get("status") == query.get("status", "playing"):
            return row
        return None

    def find(self, query, _projection=None):
        return FakeCursor(
            r for r in self.rows.values() if r.get("status") == query.get("status")
        )

    async def update_one(self, query, update, upsert=False):
        uid = query.get("user_id")
        row = self.rows.setdefault(uid, {"user_id": uid})
        row.update(update.get("$set", {}))


class FakeDb:
    def __init__(self, tokens, playing):
        self.user_sessions = FakeSessions(tokens)
        self._live = FakeLivePlay(playing)

    def __getitem__(self, name):
        assert name == guard.COLLECTION, f"unexpected collection {name}"
        return self._live


class Spy:
    """The inner ASGI app. Records whether the request got through."""

    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True
        body = b'{"ok":true}'
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})


def call(
    path: str,
    *,
    token: Optional[str] = None,
    method: str = "GET",
    scope_type: str = "http",
) -> Tuple[Spy, int, bytes]:
    """Drive the middleware once. -> (inner app spy, status, body)."""
    spy = Spy()
    middleware = guard.LivePlayGuardMiddleware(spy)

    headers = []
    if token:
        headers.append((b"cookie", f"session_token={token}".encode()))

    scope: Dict[str, Any] = {
        "type": scope_type,
        "method": method,
        "path": path,
        "headers": headers,
    }

    sent: List[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))

    status = next((m["status"] for m in sent if m["type"] == "http.response.start"), 0)
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return spy, status, body


@pytest.fixture(autouse=True)
def clean_guard_state():
    """The guard holds process state. Never leak it between tests."""
    guard._LIVE_PLAYERS.clear()
    guard.set_db_provider(None)
    yield
    guard._LIVE_PLAYERS.clear()
    guard.set_db_provider(None)


def arm(playing=(PLAYER,), tokens=None):
    """Put the guard in the state it is in while somebody is mid-game."""
    tokens = tokens or {"tok-player": PLAYER, "tok-bystander": BYSTANDER}
    db = FakeDb(tokens, list(playing))
    guard.set_db_provider(lambda: db)
    for user_id in playing:
        guard._LIVE_PLAYERS.add(user_id)
    return db


# ------------------------------------------------- it stays out of the way

def test_nothing_is_blocked_when_nobody_is_playing():
    """The negative control, and the one that protects the whole product.

    With no live game the guard must be inert even on the most engine-derived
    path there is -- and must not even look at the database to decide.
    """
    guard.set_db_provider(lambda: pytest.fail("guard touched the DB on the fast path"))
    spy, status, _ = call(BLOCKED_PATH, token="tok-player")
    assert spy.called, "the guard blocked a request while nobody was mid-game"
    assert status == 200


def test_a_bystander_is_never_blocked():
    """One player mid-game must not degrade anyone else's session."""
    arm()
    spy, status, _ = call(BLOCKED_PATH, token="tok-bystander")
    assert spy.called, "a user with no live game was blocked because someone else had one"
    assert status == 200


def test_the_player_can_still_play():
    """Everything on the allowlist must get through, or they cannot move."""
    arm()
    for path in sorted(guard.PLAY_ALLOWLIST):
        spy, status, _ = call(path, token="tok-player")
        assert spy.called, f"the guard blocked {path}, which playing requires"
        assert status == 200


def test_a_cors_preflight_is_never_refused():
    """A refused OPTIONS shows the browser a CORS error, not our explanation."""
    arm()
    spy, status, _ = call(BLOCKED_PATH, token="tok-player", method="OPTIONS")
    assert spy.called and status == 200


def test_non_api_requests_are_untouched():
    arm()
    spy, status, _ = call("/play-with-coach", token="tok-player")
    assert spy.called and status == 200


def test_websockets_and_lifespan_pass_through():
    arm()
    spy, _status, _ = call(BLOCKED_PATH, token="tok-player", scope_type="websocket")
    assert spy.called, "the guard tried to answer a non-http scope"


# ------------------------------------------------------------ it refuses

def test_the_player_is_refused_an_engine_derived_path():
    """The whole point. A live game means no review, no eval, no best move."""
    arm()
    spy, status, body = call(BLOCKED_PATH, token="tok-player")
    assert not spy.called, "the request reached the route -- the engine was in reach"
    assert status == 403
    payload = json.loads(body)
    assert payload["live_lichess_game"] is True
    # The player must learn this is deliberate and that nothing is lost.
    assert "Lichess" in payload["detail"]
    # The intent, not one word of the wording: the player must be told the
    # review is still coming, and be given somewhere to go. A refusal that
    # only says "no" reads as a broken page, which is how this shipped on
    # 2026-11-25 -- correct, and indistinguishable from the app being down.
    assert "review" in payload["detail"].lower()
    assert payload["open"] == "/play-with-coach"
    assert payload["open_label"]


def test_an_endpoint_invented_next_month_is_refused():
    """Default-deny is the only property that survives new routes."""
    arm()
    spy, status, _ = call("/api/brand/new/thing/nobody/allowlisted", token="tok-player")
    assert not spy.called and status == 403


def test_a_trailing_slash_does_not_open_a_hole():
    """Both directions, because only one of them can actually fail.

    A trailing slash on a blocked path is refused anyway, by default-deny, so
    that half cannot fail and is here only to record the behaviour. The half
    that CAN fail is the allowlist side: without normalisation,
    `/api/coach/play/live/move/` is not in the frozenset, so the guard would
    refuse the player's own move and they would sit there and lose on time.

    Checked by mutation on 2026-11-25: deleting `_normalise` leaves the first
    assertion passing and the second failing, which is the right way round.
    """
    arm()
    spy, status, _ = call(BLOCKED_PATH + "/", token="tok-player")
    assert not spy.called and status == 403

    spy, status, _ = call(ALLOWED_PATH + "/", token="tok-player")
    assert spy.called, "a trailing slash locked the player out of their own move"
    assert status == 200


def test_duplicate_slashes_do_not_open_a_hole():
    """`//api//coach//...` must normalise, not slip past the allowlist check."""
    arm()
    assert guard.is_blocked_during_live_game("//api//coach//decryption//v5//g") is True
    # and the inverse: an allowlisted path with a stray slash still works
    assert guard.is_blocked_during_live_game("/api/coach/play/live/move/") is False


# ------------------------------------------------- the state is keyed on the game

def test_the_guard_comes_off_when_the_game_ends():
    """Keyed on the game's own state, never on a flag."""
    db = arm(playing=())

    asyncio.run(guard.register_live_game(db, PLAYER, "abc12345"))
    spy, status, _ = call(BLOCKED_PATH, token="tok-player")
    assert not spy.called and status == 403

    asyncio.run(guard.release_live_game(db, PLAYER))
    spy, status, _ = call(BLOCKED_PATH, token="tok-player")
    assert spy.called, "the guard stayed on after the game ended -- review never opens"
    assert status == 200


def test_a_restart_mid_game_does_not_unguard_the_player():
    """A deploy during somebody's game is the quiet way to get them marked."""
    db = FakeDb({"tok-player": PLAYER}, [PLAYER])
    guard._LIVE_PLAYERS.clear()          # as if the process just started
    guard.set_db_provider(lambda: db)

    restored = asyncio.run(guard.load_live_players_from_db(db))
    assert restored == 1, "startup load did not restore the mid-game player"

    spy, status, _ = call(BLOCKED_PATH, token="tok-player")
    assert not spy.called and status == 403


def test_the_durable_row_is_consulted_before_the_set_is_warm():
    """Belt and braces: even with an empty set, a live row must still refuse.

    This is the window between a restart and `load_live_players_from_db`.
    """
    db = FakeDb({"tok-player": PLAYER}, [PLAYER])
    guard._LIVE_PLAYERS.clear()
    assert asyncio.run(guard.user_has_live_lichess_game(db, PLAYER)) is True
    assert asyncio.run(guard.user_has_live_lichess_game(db, BYSTANDER)) is False
