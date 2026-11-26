"""The clock on our board must be Lichess's clock, running.

Lichess sends a clock reading with each board update and nothing in between.
Two things therefore have to come out of this module, and neither of them is
the remaining time on its own:

  * **how stale the reading is** (`clock_age_ms`), so the browser can subtract
    the wait instead of drawing a number that was true a poll ago;
  * **whose clock is running** (`ticking`), because the browser cannot know
    that -- it does not know whether our stream to Lichess is still alive.

The failure these guard against is a clock that looks live and is not: frozen
through a long think, or running the wrong player down after the stream drops.
A frozen clock in a 10+0 game is the difference between "I have time" and
flagging.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.lichess_board_play import LiveGame, _apply_state  # noqa: E402


def a_game(**kw) -> LiveGame:
    base = dict(user_id="u1", game_id="g1", color="white", stream_alive=True)
    base.update(kw)
    return LiveGame(**base)


# --------------------------------------------------------------- the age


def test_a_reading_is_stamped_when_it_arrives():
    game = a_game()
    assert game.clock_age_ms() is None, "no reading yet means no age, not zero"

    _apply_state(game, {"moves": "e2e4", "wtime": 600_000, "btime": 600_000})

    age = game.clock_age_ms()
    assert age is not None
    assert age < 200, f"freshly applied reading should be ~0ms old, got {age}"


def test_the_age_grows_while_no_new_reading_arrives(monkeypatch):
    """This is the whole point: a poll three seconds later must say so."""
    import services.lichess_board_play as play

    fake = {"t": 1000.0}
    monkeypatch.setattr(play.time, "monotonic", lambda: fake["t"])

    game = a_game()
    _apply_state(game, {"moves": "e2e4", "wtime": 600_000, "btime": 600_000})
    assert game.clock_age_ms() == 0

    fake["t"] = 1003.5
    assert game.clock_age_ms() == 3500

    # A new reading resets it. Lichess's number is authoritative again.
    _apply_state(game, {"moves": "e2e4 e7e5", "wtime": 600_000, "btime": 596_500})
    assert game.clock_age_ms() == 0
    assert game.black_time_ms == 596_500


def test_a_state_without_a_clock_does_not_restamp(monkeypatch):
    """Lichess omits wtime/btime on some updates; that is not a new reading."""
    import services.lichess_board_play as play

    fake = {"t": 500.0}
    monkeypatch.setattr(play.time, "monotonic", lambda: fake["t"])

    game = a_game()
    _apply_state(game, {"moves": "e2e4", "wtime": 600_000, "btime": 600_000})
    fake["t"] = 502.0
    _apply_state(game, {"moves": "e2e4", "wdraw": True})

    assert game.clock_age_ms() == 2000, "a clockless update must not look fresh"


# ------------------------------------------------------------ who is running


def test_the_side_to_move_is_the_one_running_down():
    one = a_game(moves="e2e4")
    assert one.ticking() == "black"

    two = a_game(moves="e2e4 e7e5")
    assert two.ticking() == "white"


def test_nothing_runs_before_the_first_move():
    # Lichess's own handling of the clock before move one is not something we
    # have verified, and a clock that counts down then jumps back up on the
    # first reading reads as broken. Still, then stepping down, does not.
    assert a_game(moves="").ticking() is None


def test_nothing_runs_once_the_game_is_over():
    for status in ("mate", "resign", "outoftime", "draw", "aborted"):
        game = a_game(moves="e2e4 e7e5", status=status)
        assert game.finished
        assert game.ticking() is None, f"{status} must stop both clocks"


def test_nothing_runs_while_the_stream_is_down():
    """With no stream we do not know the position, so we do not know whose turn
    it is -- and a clock run down against the wrong player is worse than one
    that has visibly stopped."""
    game = a_game(moves="e2e4", stream_alive=False)
    assert game.ticking() is None


# ----------------------------------------------------------------- payload


def test_the_board_payload_carries_both():
    game = a_game()
    _apply_state(game, {"moves": "e2e4", "wtime": 600_000, "btime": 598_200})
    payload = game.as_payload()

    assert payload["white_time_ms"] == 600_000
    assert payload["black_time_ms"] == 598_200
    assert payload["ticking"] == "black"
    assert isinstance(payload["clock_age_ms"], int)
    # And still nothing an engine produced.
    for forbidden in ("eval", "cp_loss", "best_move", "evaluation", "caption"):
        assert forbidden not in payload


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
