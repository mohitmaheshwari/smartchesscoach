"""The behavioural half of Mohit's drill rule may not invent a cause.

Mohit, 2026-11-27: "chess is just not calculation and tactics, chess is also
focus and behavioral tactics, so that's what we want to track."

Measured 2026-11-27 over 1,200 games and 5,466 eligible one-move piece-safety
decisions (base rate 8.29%), using the opportunities that went FINE as the
denominator:

    time pressure (<60s left)            14.68% vs  8.05%   1.82x
    unravelling (big error in last 3)    10.14% vs  7.56%   1.34x
    late game (move 31+)                 10.42% vs  7.99%   1.30x
    snap move (<= 1/3 his own pace)       6.02% vs  8.49%   0.71x

...and nothing at all covered 50.3% of the errors.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import player_behaviour_reading as pbr  # noqa: E402


def _row(ply, *, clock=600.0, move_no=10, cp=0):
    return {"game_id": "g1", "ply": ply, "move_number": move_no,
            "time_left_seconds": clock, "cp_loss": cp}


def test_a_low_clock_is_named():
    assert pbr.cause_for_move(_row(20, clock=30.0),
                              after_big_error=False) == "time_pressure"


def test_an_error_right_after_an_error_is_named_as_that():
    rows = [_row(10, cp=400), _row(12), _row(14)]
    assert pbr.prior_big_error(rows, 2) is True
    assert pbr.cause_for_move(rows[2], after_big_error=True) == "unravelling"


def test_an_old_error_does_not_count_as_unravelling():
    # Only the last UNRAVEL_PLIES moves. A mistake eight moves ago is not
    # the reason for this one.
    rows = [_row(2, cp=400)] + [_row(p) for p in range(4, 20, 2)]
    assert pbr.prior_big_error(rows, len(rows) - 1) is False


def test_late_in_the_game_is_named_when_nothing_stronger_applies():
    assert pbr.cause_for_move(_row(70, move_no=40),
                              after_big_error=False) == "late_game"


def test_the_strongest_measured_cause_wins_when_several_are_true():
    # Low clock (1.82x) outranks unravelling (1.34x) and late game (1.30x).
    # Naming all three would say nothing.
    assert pbr.cause_for_move(_row(70, clock=20.0, move_no=40),
                              after_big_error=True) == "time_pressure"


def test_moving_fast_is_never_a_cause():
    # THE REFUSED HYPOTHESIS. A snap move is measurably SAFER than a
    # considered one (6.02% against 8.49%, 0.71x). "Eyesight" and "he rushed"
    # are the same guess, and this is the third time the data has refused it:
    # the teaching triage carried a `rushed` rule that was backwards too.
    # If this test ever fails, someone has reintroduced it.
    assert "rushed" not in pbr.CAUSE_WORDS
    assert "snap" not in pbr.CAUSE_WORDS
    assert "eyesight" not in pbr.CAUSE_WORDS
    assert not any("rushed" in c or "snap" in c for c in pbr.CAUSE_ORDER)
    # A fast move with a full clock, early, after a clean move: no cause.
    fast = {**_row(8, clock=600.0, move_no=4), "time_spent_seconds": 0.2}
    assert pbr.cause_for_move(fast, after_big_error=False) == "not_explained"


def test_nothing_to_point_at_says_so():
    rows = {"g1": [_row(8, clock=600.0, move_no=4)]}
    got = pbr.reading(rows, [("g1", 8)])
    assert got["cause"] == "not_explained"
    assert got["measured"]["unexplained"] == 1


def test_a_cause_is_not_claimed_when_most_errors_are_unexplained():
    # Half the errors have no explanation at all in the real corpus, so a
    # thin cause must not speak for the whole set.
    rows = {"g1": [
        _row(2, clock=20.0),                      # time pressure
        _row(4, clock=600.0, move_no=4),          # nothing
        _row(6, clock=600.0, move_no=4),          # nothing
        _row(8, clock=600.0, move_no=4),          # nothing
    ]}
    got = pbr.reading(rows, [("g1", 2), ("g1", 4), ("g1", 6), ("g1", 8)])
    assert got["cause"] == "not_explained"
    assert got["measured"]["by_cause"]["time_pressure"] == 1
    assert got["measured"]["unexplained"] == 3


def test_a_dominant_cause_is_claimed():
    rows = {"g1": [_row(p, clock=25.0) for p in (2, 4, 6)]
                  + [_row(8, clock=600.0, move_no=4)]}
    got = pbr.reading(rows, [("g1", p) for p in (2, 4, 6, 8)])
    assert got["cause"] == "time_pressure"
    assert got["measured"]["errors"] == 4


def test_no_errors_reads_nothing():
    assert pbr.reading({"g1": [_row(2)]}, []) is None


def test_the_player_facing_words_carry_no_digits():
    # The plan's standing rule: counts live in `measured`.
    for title, text in pbr.CAUSE_WORDS.values():
        assert not any(ch.isdigit() for ch in title), title
        assert not any(ch.isdigit() for ch in text), text


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# ---------------------------------------------------------------------------
# Tracked axes. Measured per-user over ten games, 2026-11-27:
#   kept pieces safe            p25  4%  median  6%  max  30%   4 of 65 >= 25%
#   answered their threat       p25 26%  median 32%  max  64%  46 of 59 >= 25%
#   punished their mistake      p25 41%  median 54%  max  68%   9 of 10 >= 25%
#   found it when it mattered   p25 87%  median 94%  max 100%  62 of 62 >= 25%
# ---------------------------------------------------------------------------


def test_an_axis_is_a_rate_out_of_chances():
    rows = ([{"ignored_opponent_threat": True}] * 3
            + [{"responded_to_threat": True}] * 7)
    got = pbr.axis_rates(rows)["axis:threat_answered"]
    assert got["chances"] == 10 and got["wrong"] == 3
    assert got["rate"] == 0.3


def test_an_axis_with_no_chances_is_absent_not_zero():
    # A player who never faced a threat has no rate, not a perfect one.
    assert "axis:threat_answered" not in pbr.axis_rates([{"cp_loss": 10}])


PS = "gap:piece_safety:destination_safety_exact"


def test_mohits_absolute_bar_lives_only_where_he_put_it():
    # 25% is calibrated to one-move piece blunders (4 of 65 users). On
    # threats it would drill 48 of 59 and on punishing mistakes 40 of 43,
    # the opposite of the rule it came from. It stays on that one key.
    assert pbr.PEER_RATES[PS]["absolute_bar"] == 0.25
    for key, spec in pbr.PEER_RATES.items():
        if key != PS:
            assert spec["absolute_bar"] is None, key
    # And no axis carries a bare rate any more.
    for key, spec in pbr.AXES.items():
        assert "drill_bar" not in spec, key
        assert spec.get("peer_key") in pbr.PEER_RATES, key


def test_every_axis_is_calibrated_against_its_own_distribution():
    # The reason the 25% transfer failed: the base rates are nothing alike.
    rates = {k: v["pooled"] for k, v in pbr.PEER_RATES.items()}
    assert rates[PS] < 0.15 < rates["axis:threat_answered"]
    assert rates["axis:punished_their_mistake"] > 0.30


def test_the_binomial_is_exact():
    # P(X >= 2) for Bin(3, 0.5) = 3(.25)(.5) + .125 = 0.5, by hand.
    assert abs(pbr.binom_sf(2, 3, 0.5) - 0.5) < 1e-12
    assert pbr.binom_sf(0, 10, 0.3) == 1.0
    assert abs(pbr.binom_sf(10, 10, 0.5) - 0.5 ** 10) < 1e-12


def test_the_peer_rate_follows_his_level_not_the_corpus():
    # Piece safety runs 14.4% among beginners and 2.7% at intermediate, a
    # 5x spread. Pooling it would call a beginner worse-than-peers for being
    # ordinary at his level -- Mohit's Magnus objection, inverted.
    low = pbr.peer_rate(PS, "beginner_low")
    mid = pbr.peer_rate(PS, "intermediate")
    assert low > 2 * mid
    # An unknown or missing band falls back to pooled, never to a guess.
    assert pbr.peer_rate(PS, None) == pbr.PEER_RATES[PS]["pooled"]
    assert pbr.peer_rate(PS, "no_such_band") == pbr.PEER_RATES[PS]["pooled"]
    assert pbr.peer_rate("axis:nothing", "beginner_low") is None


def test_the_calibrated_rule_keeps_everyone_mohits_bar_picked():
    # Measured 2026-11-27: of the 4 users at or above 25% on piece safety,
    # the calibrated rule keeps 4. These are their real counts.
    for wrong, chances in [(21, 47), (13, 37), (10, 31), (9, 33)]:
        assert pbr.needs_drill(PS, wrong, chances, "beginner_low"), (wrong, chances)


def test_it_also_catches_the_two_the_absolute_bar_missed():
    # Both are under 25% but measurably worse than their own level:
    # 12/63 = 19% against a 6.7% band, and 5/47 = 11% against 2.7%.
    assert pbr.needs_drill(PS, 12, 63, "beginner_high")
    assert pbr.needs_drill(PS, 5, 47, "intermediate")
    # ...and the absolute bar alone would have let both through.
    assert 12 / 63 < 0.25 and 5 / 47 < 0.25


def test_a_player_in_line_with_his_level_is_not_drilled():
    # 3 of 44 is 6.8%, right at the beginner_high rate. Nothing to fix.
    assert pbr.needs_drill(PS, 3, 44, "beginner_high") is None
    # Three fires against 1.19 expected is p=0.12 even at intermediate:
    # a rate 2.5x the peer rate still proves nothing on three events.
    assert pbr.needs_drill(PS, 3, 44, "intermediate") is None


def test_the_same_count_can_be_fine_at_one_level_and_a_fault_at_another():
    # THE POINT OF BANDING. 5 of 63 is 7.9% either way: ordinary for a
    # beginner (p=0.42 against 6.7%) and a real fault at intermediate
    # (p=0.028 against 2.7%). One pooled number cannot say both.
    assert pbr.needs_drill(PS, 5, 63, "beginner_high") is None
    owed = pbr.needs_drill(PS, 5, 63, "intermediate")
    assert owed and owed["basis"] == "worse_than_level"
    assert owed["p_value"] < pbr.PEER_ALPHA


def test_too_few_chances_is_never_a_verdict():
    # A rate over 25% on 19 chances says nothing: at n=20 a player truly at
    # 30% shows under 25% about a quarter of the time.
    assert pbr.MIN_CHANCES == 20
    assert pbr.needs_drill(PS, 8, 19, "beginner_low") is None
    assert pbr.worse_than_peers(PS, 8, 19, "beginner_low") is None


def test_an_uncalibrated_axis_refuses_to_judge():
    # No measured peer rate means no level to compare against. Returning a
    # verdict here would be inventing the number the rule rests on.
    assert pbr.needs_drill("gap:something:unmeasured", 30, 40, "beginner_low") is None
    assert pbr.worse_than_peers("gap:something:unmeasured", 30, 40) is None


def test_punishing_mistakes_reads_a_wider_window():
    # 1.3 chances a game: at ten games 10 of 65 users reached twenty
    # chances, at twenty games 43 of 59. Ten games cannot speak at all.
    assert pbr.window_games("axis:punished_their_mistake") == 20
    assert pbr.window_games(PS) == 10
    assert pbr.window_games("axis:threat_answered") == 10
    assert pbr.window_games("axis:unknown", default=10) == 10


def test_what_everyone_fails_is_not_tracked_as_a_weakness():
    # found_best_in_critical has a 94% median across 62 users. A number
    # everyone fails measures being human, not a fault.
    assert "found_best_in_critical" in pbr.NOT_AN_AXIS
    assert not any("critical" in k for k in pbr.AXES)


def test_axis_titles_carry_no_digits():
    for spec in pbr.AXES.values():
        assert not any(ch.isdigit() for ch in spec["title"])
        assert not any(ch.isdigit() for ch in spec["good"])


def test_each_axis_counts_only_its_own_window():
    # Threats read ten games, punishing reads twenty. Given fifteen games of
    # rows, threats must ignore games 11-15 and punishing must use them.
    order = [f"g{i}" for i in range(1, 16)]
    rows = []
    for gid in order:
        rows.append({"game_id": gid, "ignored_opponent_threat": True})
        rows.append({"game_id": gid, "missed_opponent_blunder": True})
    got = pbr.axis_rates(rows, game_order=order)
    assert got["axis:threat_answered"]["chances"] == 10
    assert got["axis:threat_answered"]["window_games"] == 10
    assert got["axis:punished_their_mistake"]["chances"] == 15
    assert got["axis:punished_their_mistake"]["window_games"] == 20


def test_no_game_order_counts_everything_as_before():
    order = [f"g{i}" for i in range(1, 16)]
    rows = [{"game_id": g, "ignored_opponent_threat": True} for g in order]
    got = pbr.axis_rates(rows)
    assert got["axis:threat_answered"]["chances"] == 15
    assert "window_games" not in got["axis:threat_answered"]


def test_an_axis_judges_only_when_it_knows_his_level():
    rows = ([{"game_id": "g1", "ignored_opponent_threat": True}] * 24
            + [{"game_id": "g1", "responded_to_threat": True}] * 16)
    # 24 of 40 = 60% against a 39.2% beginner rate.
    judged = pbr.axis_rates(rows, band="beginner_low")["axis:threat_answered"]
    assert judged["needs_drill"] is True
    assert judged["peer_rate"] == 0.392
    # Without a band it reports the rate and says nothing about drilling.
    bare = pbr.axis_rates(rows)["axis:threat_answered"]
    assert "needs_drill" not in bare
    assert bare["rate"] == 0.6


def test_thin_evidence_reads_as_unknown_not_as_fine():
    # Ten chances, all wrong. "needs_drill: False" would be a lie; the
    # honest answer is that we have not seen enough.
    rows = [{"game_id": "g1", "ignored_opponent_threat": True}] * 10
    got = pbr.axis_rates(rows, band="beginner_low")["axis:threat_answered"]
    assert got["needs_drill"] is None
    assert got["too_few_chances"] == pbr.MIN_CHANCES
