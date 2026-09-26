"""A time flag must describe how fast the player moved FOR THEM.

`impulsive_critical` required `is_critical` and under 3 seconds, and both halves
were wrong. Measured on production 2026-09-26:

  11,984 of 11,984 fires had is_critical True -- VACUOUS, because is_critical is
         set by `cp_loss >= 100 or evaluation in (blunder, mistake)` and the
         quality gate already guarantees it.
  14.6%  of fires were played at or SLOWER than that player's own pace for that
         game. The median move in this corpus is 3.4s, so an absolute
         three-second rule calls an above-average think an impulse.
       0 slow_paralysis rows exist, against 11,984 and 489 of the other two,
         because it required `not was_critical` -- unreachable for a mistake.

And the finding these tests must not let anyone forget: mistakes are LESS
rushed than ordinary moves (13.2% against 23.5%), and not one of 42 players
makes their mistakes faster than their usual pace. The flag marks a move, never
a person.
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.move_observation_deriver import (  # noqa: E402
    MIN_CREDIBLE_MOVE_SECONDS,
    SLOW_THINK_SECONDS,
    SNAP_PACE_RATIO,
    _classify_time_flag,
)

# A mistake that changed the game, so the coaching-relevance gates let it past.
BAD = {"evaluation": "blunder", "is_critical": True,
       "eval_before": 0, "eval_after": -400}
PACE = 4.0


def _flag(seconds, pace=PACE, time_left=120, mv=None):
    return _classify_time_flag(dict(mv or BAD), seconds, time_left,
                               user_color="white", game_pace_seconds=pace)


def test_fast_for_this_player_is_flagged():
    assert _flag(PACE * SNAP_PACE_RATIO * 0.5) == "snap_decision"


def test_the_same_seconds_are_not_a_snap_in_a_slower_game():
    """The whole bug in one test. Two seconds is a snap for someone averaging
    twelve and an ordinary move for someone averaging four."""
    seconds = 2.0
    assert _flag(seconds, pace=12.0) == "snap_decision"
    assert _flag(seconds, pace=4.0) != "snap_decision"


def test_a_move_at_the_players_own_pace_is_never_a_snap():
    assert _flag(PACE) != "snap_decision"
    assert _flag(PACE * 0.9) != "snap_decision"


def test_a_move_slower_than_usual_is_never_a_snap():
    """14.6% of the old fires were exactly this: flagged as impulse for
    thinking LONGER than they normally do."""
    assert _flag(PACE * 2) != "snap_decision"


def test_no_pace_means_no_claim():
    """Falling back to an absolute threshold is the bug being fixed, so with
    nothing to compare against the flag stays silent."""
    assert _flag(0.2, pace=None) is None
    assert _flag(PACE * SNAP_PACE_RATIO * 0.5, pace=None) is None


def test_a_stalled_clock_is_not_a_decision():
    """Below the credible floor the clock was not really ticking -- an
    increment refresh, not a human choice."""
    assert _flag(MIN_CREDIBLE_MOVE_SECONDS * 0.5, pace=100.0) is None


def test_a_good_move_is_never_flagged():
    """These flags explain mistakes. A fast good move is just a fast good
    move, and saying otherwise would be a failure scoreboard."""
    assert _flag(0.6, mv={"evaluation": "good", "is_critical": False}) is None


def test_a_long_think_that_still_went_wrong_can_now_fire():
    """It never could: it required `not was_critical`, and every mistake is
    critical by that definition. Production holds zero of them."""
    assert _flag(SLOW_THINK_SECONDS + 10, time_left=600) == "slow_paralysis"


def test_time_pressure_still_beats_a_long_think():
    """Ordering matters: with seconds on the clock, the clock is the story."""
    assert _flag(SLOW_THINK_SECONDS + 10, time_left=5) == "time_pressure_blunder"


def test_an_already_decided_game_is_not_coached():
    """Both directions, kept from the previous version: an impulsive move when
    already winning or losing decisively is not a lesson."""
    for before, after in ((900, 950), (-900, -950)):
        mv = dict(BAD, eval_before=before, eval_after=after)
        assert _flag(0.6, mv=mv) is None


def test_the_severity_map_knows_both_the_new_and_the_legacy_key():
    """11,984 rows still carry the old key. Dropping it would render them as a
    raw slug in the badge and recall surfaces."""
    from services.move_observation_deriver import _time_flag_severity

    for key in ("snap_decision", "impulsive_critical"):
        assert _time_flag_severity(key, dict(BAD)) is not None, key
