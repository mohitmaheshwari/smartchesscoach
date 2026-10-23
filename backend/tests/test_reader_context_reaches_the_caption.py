"""The arrow shows WHAT. This is how long they took and whether it keeps
happening.

Mohit: "one move blunder is there, but that can be easily showed by arrow
... where is the teaching and the memory of player ... game review should
also consider the time taken to make that move, why he made that move?"

Measured before building any of it, over 400 games:

    time present on                         69.4% of moves
    MEDIAN time on a blunder of 200cp+      7 seconds
    user+gap pairs that recur               93%

Half of all blunders are played in under seven seconds. That is the answer
to "why did he play it", and it is a different lesson from the 8% that took
over thirty.

Two rules this file exists to hold:

  NO SCOREBOARD. 93% of pairs recur and one user's missed_tactic is 157.
  The repeat signal is the decay service's own word -- active, declining,
  fading -- and never a count.

  THE CHESS SURVIVES. The first version of the prompt produced "you played
  this in four seconds; this one keeps coming back", with no mention of the
  move that punished it. The context is the frame, not a replacement.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import reader_context as rc  # noqa: E402
from services.llm_caption import build_facts  # noqa: E402


def _game(times):
    return [{"time_spent_seconds": t} for t in times]


class TestThePaceComesFromTheirOwnGame:
    def test_the_median_is_the_baseline(self):
        assert rc.game_pace(_game([10, 20, 30, 40, 50, 60, 70, 80])) == 50.0

    def test_too_few_timed_moves_is_no_baseline(self):
        """Four timed moves says nothing about a player's normal pace."""
        assert rc.game_pace(_game([3, 4, 5, 6])) is None

    def test_a_move_with_no_clock_gets_no_time_fact(self):
        """30.6% of moves have no time. A guess is worse than silence."""
        ctx = {"pace_seconds": 20.0, "decay": {}, "trained": set()}
        assert rc.for_move(ctx, {}) == {}

    def test_quick_is_relative_to_the_player_not_absolute(self):
        """Three seconds is fast for someone averaging thirty and ordinary
        in a fast game, so the judgement is made against their own pace."""
        slow = {"pace_seconds": 30.0, "decay": {}, "trained": set()}
        fast = {"pace_seconds": 4.0, "decay": {}, "trained": set()}
        mv = {"time_spent_seconds": 3}
        assert rc.for_move(slow, mv).get("quick_for_this_player") is True
        assert "quick_for_this_player" not in rc.for_move(fast, mv)

    def test_the_seconds_are_reported_either_way(self):
        ctx = {"pace_seconds": 30.0, "decay": {}, "trained": set()}
        got = rc.for_move(ctx, {"time_spent_seconds": 48})
        assert got["seconds_on_this_move"] == 48
        assert got["their_usual_seconds_this_game"] == 30
        assert "quick_for_this_player" not in got


class TestTheRepeatSignalIsNeverACount:
    CTX = {
        "pace_seconds": 20.0,
        "decay": {"piece_safety": {"state": "active", "clean_streak": 0},
                  "king_safety": {"state": "declining", "clean_streak": 5}},
        "trained": {"piece_safety"},
    }

    def test_a_live_weakness_travels_as_a_word(self):
        got = rc.for_move(self.CTX, {"time_spent_seconds": 5,
                                     "cognitive_gap": "piece_safety"})
        assert got["this_weakness_lately"] == "active"

    def test_no_count_of_past_mistakes_is_ever_included(self):
        """One user's missed_tactic is 157. No field may carry that."""
        got = rc.for_move(self.CTX, {"time_spent_seconds": 5,
                                     "cognitive_gap": "piece_safety"})
        for key in got:
            assert "count" not in key, key
            assert "times" not in key, key
        assert "raw_count" not in got
        assert "display_count" not in got

    def test_a_clean_streak_is_carried_because_it_is_good_news(self):
        got = rc.for_move(self.CTX, {"time_spent_seconds": 5,
                                     "cognitive_gap": "king_safety"})
        assert got["clean_games_in_a_row"] == 5

    def test_training_history_changes_the_lesson(self):
        """Solved puzzles on the pattern means they KNOW it, so the card is
        about looking, not learning."""
        trained = rc.for_move(self.CTX, {"time_spent_seconds": 5,
                                         "cognitive_gap": "piece_safety"})
        untrained = rc.for_move(self.CTX, {"time_spent_seconds": 5,
                                           "cognitive_gap": "king_safety"})
        assert trained["they_have_solved_puzzles_on_this"] is True
        assert "they_have_solved_puzzles_on_this" not in untrained

    def test_an_unknown_decay_state_is_not_passed_on(self):
        ctx = {"pace_seconds": 20.0,
               "decay": {"x": {"state": "weird"}}, "trained": set()}
        got = rc.for_move(ctx, {"time_spent_seconds": 5,
                                "cognitive_gap": "x"})
        assert "this_weakness_lately" not in got


class TestItReachesTheFactBundle:
    def test_the_bundle_carries_it_under_its_own_key(self):
        facts = build_facts("Nxc2", "Ng2", [], mover_is_user=True,
                            reader={"seconds_on_this_move": 4})
        assert facts["about_this_player"]["seconds_on_this_move"] == 4

    def test_no_reader_means_no_key_at_all(self):
        facts = build_facts("Nxc2", "Ng2", [], mover_is_user=True)
        assert "about_this_player" not in facts

    def test_the_prompt_forbids_a_tally_and_demands_the_board(self):
        import services.llm_caption as lc
        src = Path(lc.__file__).read_text(encoding="utf-8")
        assert "No scoreboard" in src
        assert "ALWAYS say what actually happened on the board" in src

    def test_gather_survives_a_broken_database(self):
        class Boom:
            def __getattr__(self, name):
                raise RuntimeError("mongo is down")
        got = rc.gather(Boom(), "u1", _game([5, 10, 15, 20, 25, 30, 35, 40]))
        assert got["pace_seconds"] == 25.0        # still computed locally
        assert got["decay"] == {}
