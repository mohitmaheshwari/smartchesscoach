"""The first ninety seconds of a new account.

Onboarding imports a player's games, bumps one to the front of the analysis
queue, and sends them straight to it, so their first session opens on their own
game rather than an empty dashboard. Two things broke that promise.

1. The game picker read `result` without `user_color`. Results are stored as
   "1-0"/"0-1", never as prose, so matching "0-1" as a loss meant a Black
   player's WIN was chosen as the game to learn from and their real loss was
   never found. Replayed across every production user with games, the picker
   opened on a game they had WON for 32 of 69 (46.4%).

2. The review endpoint returned {"error": "Game analysis not found"} whenever
   no game_analyses document existed -- and that document is only written when
   the Stockfish worker FINISHES. A new account always arrives before then, so
   the first screen was an amber warning triangle with a "Try Again" button
   and no auto-retry. Measured on production, 348 of 400 not-yet-complete
   queue rows (87%) had no document. Analysis takes 1.7 min at the median and
   3.0 at p90, so that error sat there for minutes.

   The frontend already polls every 5 seconds on status == "generating"; it
   only needed to be told the truth.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.game_outcome import DRAW, LOSS, UNKNOWN, WIN, user_lost, user_outcome


# --- the picker ------------------------------------------------------------

@pytest.mark.parametrize("result,colour,expected", [
    ("1-0", "white", WIN),
    ("1-0", "black", LOSS),
    ("0-1", "white", LOSS),
    ("0-1", "black", WIN),
    ("1/2-1/2", "white", DRAW),
    ("1/2-1/2", "black", DRAW),
])
def test_the_result_is_read_against_the_players_colour(result, colour, expected):
    assert user_outcome({"result": result, "user_color": colour}) == expected


def test_the_exact_case_that_was_wrong():
    # A Black player who lost. The old picker matched only "0-1", so this game
    # -- the one worth coaching -- was invisible to it.
    assert user_lost({"result": "1-0", "user_color": "black"}) is True


def test_a_black_players_win_is_not_treated_as_a_loss():
    # And this one was chosen instead.
    assert user_lost({"result": "0-1", "user_color": "black"}) is False


@pytest.mark.parametrize("game", [
    {"result": "1-0"},                      # no colour
    {"result": "*", "user_color": "white"},  # unfinished
    {"user_color": "white"},                 # no result
])
def test_it_says_unknown_rather_than_guessing(game):
    assert user_outcome(game) == UNKNOWN
    assert user_lost(game) is False


def test_records_that_already_resolved_the_outcome_still_work():
    assert user_outcome({"result": "loss"}) == LOSS
    assert user_outcome({"result": "win"}) == WIN


def test_the_picker_selects_the_most_recent_real_loss():
    # The ordering onboarding uses: newest first, then the first true loss.
    games = [
        {"game_id": "g3", "date_played": "2026.09.10", "result": "0-1",
         "user_color": "black"},   # a win
        {"game_id": "g2", "date_played": "2026.09.09", "result": "1-0",
         "user_color": "black"},   # the loss we want
        {"game_id": "g1", "date_played": "2026.09.08", "result": "1-0",
         "user_color": "white"},   # an older win
    ]
    losses = [g for g in games if user_lost(g)]
    assert [g["game_id"] for g in losses] == ["g2"]


# --- the first screen ------------------------------------------------------

class _Queue:
    def __init__(self, status):
        self.status = status

    async def find_one(self, query, projection=None):
        return {"status": self.status} if self.status else None


class _DB:
    def __init__(self, status):
        self.analysis_queue = _Queue(status)


def _payload(queue_status):
    """Call the REAL helper the endpoints use, not a copy of its logic."""
    import asyncio

    from routes.coach import _analysis_not_ready_payload

    return asyncio.run(_analysis_not_ready_payload(_DB(queue_status), "g1"))


@pytest.mark.parametrize("queue_status", ["pending", "processing"])
def test_a_queued_game_reports_generating_so_the_page_waits(queue_status):
    payload = _payload(queue_status)
    assert payload is not None
    assert payload["status"] == "generating", (
        "the frontend only polls on 'generating'; anything else leaves a new "
        "account staring at a warning triangle"
    )
    assert "error" not in payload
    assert payload["message"]


def test_a_failed_analysis_is_terminal_and_says_so():
    # Polling forever would be worse than an honest message.
    payload = _payload("failed")
    assert payload is not None
    assert payload.get("status") != "generating"
    assert "could not finish" in payload["error"]


def test_a_game_that_was_never_queued_falls_through_to_not_found():
    # None means "I have nothing to say about this" -- the caller then returns
    # its existing not-found response.
    assert _payload(None) is None


def test_a_completed_queue_row_also_falls_through():
    assert _payload("completed") is None


def test_the_waiting_message_never_shows_a_warning_to_a_new_player():
    text = _payload("pending")["message"].lower()
    for scary in ("error", "not found", "failed", "could not"):
        assert scary not in text, text


def test_both_decryption_endpoints_use_the_helper():
    # The review page calls the v5 endpoint; the older component calls v4.
    # Fixing only one leaves the bug live on the other.
    import io as _io
    from pathlib import Path

    source = _io.open(
        Path(__file__).resolve().parent.parent / "routes" / "coach.py",
        encoding="utf-8",
    ).read()
    assert source.count("await _analysis_not_ready_payload(db, game_id)") == 2
