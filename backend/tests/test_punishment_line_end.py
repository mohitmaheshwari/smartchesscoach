"""The punishment line stops where the punishment lands.

Mohit 2026-09-26, on a one-move blunder that played out nine moves: "this
straight up is one move blunder, our detector would have fired here and
should have stopped directly on the first move."

He was right that it should stop and wrong that a detector was stopping it.
Nothing was: the line is [played] + pv_after_played[:8], a fixed slice, so
every stored line came out exactly nine moves long whatever the mistake was
-- 19 of 19 measured in the corpus.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.game_decryption_v5_service import punishment_line_end  # noqa: E402


class TestTheDetectorNamesTheSquare:
    def test_stops_on_the_capture_of_the_hung_piece(self):
        # The reported card: Nf4 hangs the knight, Bxf4+ takes it, and the
        # seven moves after that are the game continuing.
        pv = ["Bxf4+", "Kb1", "Bg4", "h3", "Bc8", "Rhe1", "Bb8", "Nd4"]
        assert punishment_line_end(pv, "f4") == 0

    def test_a_later_capture_on_the_square_still_ends_it(self):
        pv = ["Kb1", "Bg4", "Nxf4", "h3"]
        assert punishment_line_end(pv, "f4") == 2

    def test_check_and_mate_marks_do_not_hide_the_square(self):
        assert punishment_line_end(["Bxf4#"], "f4") == 0
        assert punishment_line_end(["Bxf4+"], "f4") == 0

    def test_a_capture_somewhere_else_does_not_count(self):
        # Taking on d5 is not the knight on f4 being lost.
        pv = ["Nxd5", "Qxd5", "Bxf4+"]
        assert punishment_line_end(pv, "f4") == 2

    def test_case_is_not_load_bearing(self):
        assert punishment_line_end(["Bxf4+"], "F4") == 0


class TestNoDetectorFact:
    def test_falls_back_to_the_last_capture(self):
        # The case the fixed slice was built for: eb189840 move 8 loses a
        # pawn over a run of forced captures and needs all of them.
        pv = ["Bxf6", "Nxc3", "Bxe7", "Nxd1", "Bxd8", "Nxb2"]
        assert punishment_line_end(pv, None) == 5

    def test_trailing_quiet_moves_are_dropped(self):
        pv = ["Nxc5", "Ne7", "d3", "Nbc6"]
        assert punishment_line_end(pv, None) == 0


class TestAbstaining:
    def test_a_positional_punishment_keeps_the_existing_behaviour(self):
        # No capture and no hang means no honest stopping point. Returning a
        # guess here would cut a line in the middle of the idea, which is
        # worse than showing it whole.
        pv = ["Bb5+", "c6", "Bc4", "Qe7", "Nb3"]
        assert punishment_line_end(pv, None) is None

    def test_a_hung_square_nothing_ever_takes_falls_through(self):
        pv = ["Bb5+", "c6", "Bc4"]
        assert punishment_line_end(pv, "h7") is None

    def test_an_empty_line_is_not_an_error(self):
        assert punishment_line_end([], "f4") is None
        assert punishment_line_end(None, "f4") is None

    def test_blank_entries_do_not_crash_it(self):
        assert punishment_line_end(["", None, "Bxf4+"], "f4") == 2
