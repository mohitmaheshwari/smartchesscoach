"""A forced mate in two is still a mate.

`classify_missed_tactic` checked for mate by pushing the engine's move and
asking `is_checkmate()`, which only ever catches mate in ONE. Everything
longer fell through to `missed_generic_tactic`. Measured over 2,000 of those
observations, 41.5% had a forced mate the played move threw away -- roughly
2,990 of the 7,195 in that bucket, about seven times the entire current
missed_mate population.

Mohit's instruction, when a mate had been filed as a skewer, was that mate
outranks every other name. These pin that it now does regardless of distance,
and that the reading of `mate_info` cannot invent a mate the mover never had.
"""
import chess

from services.cognitive_gap_subtypes import (
    _lost_forced_mate_plies,
    classify_missed_tactic,
)

# Black to move, nothing forced; used only so the classifier has a legal board.
QUIET_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w kq - 0 1"


class TestReadingMateInfo:
    def test_a_mate_the_mover_had_and_lost_is_reported_with_its_distance(self):
        assert _lost_forced_mate_plies(
            {"mate_info": {"before": 3, "after": None}}, True) == 3
        # Black mates with a negative score; the sign is white-relative.
        assert _lost_forced_mate_plies(
            {"mate_info": {"before": -4, "after": None}}, False) == 4

    def test_keeping_the_mate_is_not_missing_it(self):
        assert _lost_forced_mate_plies(
            {"mate_info": {"before": 3, "after": 2}}, True) is None

    def test_a_mate_against_the_mover_is_not_theirs_to_miss(self):
        """The failure this guards is the whole reason the helper exists.

        A player being mated has a non-zero mate score too. Reading the
        magnitude without the sign would report every one of their moves as a
        missed mate -- the same defect the severity classifier had, where a
        player already being mated was labelled a blunder on every move.
        """
        assert _lost_forced_mate_plies(
            {"mate_info": {"before": -3, "after": -2}}, True) is None
        assert _lost_forced_mate_plies(
            {"mate_info": {"before": 3, "after": 2}}, False) is None

    def test_a_delivered_mate_is_not_a_missed_one(self):
        # Zero means the mate landed.
        assert _lost_forced_mate_plies(
            {"mate_info": {"before": 0, "after": 0}}, True) is None

    def test_absent_or_malformed_mate_info_is_not_a_mate(self):
        assert _lost_forced_mate_plies({}, True) is None
        assert _lost_forced_mate_plies({"mate_info": None}, True) is None
        assert _lost_forced_mate_plies({"mate_info": "mate in 3"}, True) is None
        assert _lost_forced_mate_plies(
            {"mate_info": {"before": "3"}}, True) is None


class TestTheLabelItself:
    def _classify(self, mate_info, cp_loss=400):
        board = chess.Board(QUIET_FEN)
        best = next(iter(board.legal_moves)).uci()
        return classify_missed_tactic(
            {"fen_before": QUIET_FEN, "best_move_uci": best,
             "cp_loss": cp_loss, "mate_info": mate_info},
            None, None,
        )

    def test_a_lost_mate_in_three_is_named_missed_mate(self):
        subtype, severity = self._classify({"before": 3, "after": None})
        assert subtype == "missed_mate"
        assert severity == "critical"

    def test_a_long_lost_mate_gets_the_same_label_as_a_short_one(self):
        """Depth changes neither the label nor, in practice, the severity.

        Renaming a distant mate would be deleting a true detection to fix a
        framing problem. A depth-based SEVERITY split was built and then
        measured as inert -- all 831 lost mates in the sample are promoted by
        cp_loss regardless -- so it was removed rather than shipped as a knob
        that does nothing. Framing a mate in nine kindly is the caption
        layer's job.
        """
        short = self._classify({"before": 3, "after": None})
        long_mate = self._classify({"before": 9, "after": None})
        assert long_mate[0] == short[0] == "missed_mate"
        assert long_mate[1] == short[1]

    def test_without_a_mate_it_does_not_become_missed_mate(self):
        subtype, _ = self._classify(None)
        assert subtype != "missed_mate"

    def test_a_player_being_mated_is_not_told_they_missed_a_mate(self):
        # White to move in the fixture, so a negative score is Black's mate.
        subtype, _ = self._classify({"before": -3, "after": -2})
        assert subtype != "missed_mate"
