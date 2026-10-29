"""A forced mate is read from the engine's score, not from a six-ply replay.

`get_candidate_lines` reports every evaluation through
`score(mate_score=100000)`, so a forced mate arrives as 100000 minus its
distance. `_consequences` looked for mate by replaying `line[:_LINE_PLY]`
instead -- six plies -- so a mate in nine moves is eighteen plies away and
invisible, and the one verdict the engine states outright was the one we
discarded.

Measured on 320 positions run through the real button: 4 carry a mate score and
it was silent on all 4, while 0 of the 242 it could explain carry one. A mate
score predicted silence perfectly. Three of the four are stored at cp_loss
8640-9148 -- the worst moves in the sample.

Replaying all 320 with and without the score read: 4 new answers, all 4 of them
the mate-score positions, 0 answers changed and 0 lost.

The negative controls below are the point of this file. Three of them:

  * already lost -- when EVERY move loses to mate the move caused nothing, the
    same reasoning that stopped "already being mated" counting as walking into
    mate in services/severity.py;
  * no mate anywhere -- a change that reads mate scores must never invent an
    answer on a position that has none (measured: 0 leaks in 316);
  * the played move absent from the candidates -- then we do not know its
    evaluation, and we stay silent rather than guess.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.why_on_demand import (  # noqa: E402
    MATE_SCORE_FLOOR,
    _mate_from_score,
    explain,
)

# White: Ra1, Kg1, pawns f2 g2 h2.  Black: Kg8, pawns f7 g7 h7.
# Ra8+ is a back-rank check; Rb1 is a quiet rook move. Both legal, and after
# either of them ...Kh8 is legal for Black.
FEN = "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1"
PLAYED = "Rb1"
REPLY_LINE = ["Kh8", "Rb8+", "Kh8"]


def _cands(*pairs):
    """[(san, eval_cp)] -> the shape get_candidate_lines returns, best first."""
    return [{"move_san": san, "move_uci": "", "eval_cp": cp,
             "line_san": [san, "Kh8"]} for san, cp in pairs]


class TestTheMoveThatAllowsMate:
    def test_it_is_named_as_mate(self):
        out = explain(FEN, PLAYED, REPLY_LINE,
                      _cands(("Ra8+", 50), (PLAYED, -99990)), cp_loss=8877)
        assert out is not None
        assert out["mechanism"] == "MATE"
        assert out["direction"] == "received"
        assert "mate" in out["text"].lower()

    def test_the_sentence_names_their_move_not_ours(self):
        out = explain(FEN, PLAYED, REPLY_LINE,
                      _cands(("Ra8+", 50), (PLAYED, -99990)), cp_loss=8877)
        assert out["text"] == "After Rb1, Kh8 leads to mate."

    def test_the_line_starts_from_the_position_as_played(self):
        """The arrows are pushed from fen_before, so the played move has to
        lead the line or the first SAN is illegal and nothing is drawn."""
        out = explain(FEN, PLAYED, REPLY_LINE,
                      _cands(("Ra8+", 50), (PLAYED, -99990)), cp_loss=8877)
        assert out["line_san"][0] == PLAYED
        assert out["arrows"], "a proved mate must draw its line"

    def test_the_payoff_is_a_mate_distance_not_a_centipawn_count(self):
        out = explain(FEN, PLAYED, REPLY_LINE,
                      _cands(("Ra8+", 50), (PLAYED, -99990)), cp_loss=8877)
        assert out["payoff_cp"] == 10


class TestTheMoveThatMissesMate:
    def test_it_is_named_as_a_missed_mate(self):
        out = explain(FEN, PLAYED, REPLY_LINE,
                      _cands(("Ra8+", 99990), (PLAYED, 50)), cp_loss=9148)
        assert out is not None
        assert out["mechanism"] == "MATE"
        assert out["direction"] == "missed"
        assert out["text"] == "Ra8+ leads to mate."
        assert out["line_san"][0] == "Ra8+"


class TestTheNegativeControls:
    def test_already_lost_both_ways_says_nothing(self):
        """Every move loses to mate, so this move caused nothing."""
        assert _mate_from_score(
            _cands(("Ra8+", -99980), (PLAYED, -99990)), PLAYED, REPLY_LINE
        ) is None

    def test_a_position_with_no_mate_score_gains_nothing(self):
        assert _mate_from_score(
            _cands(("Ra8+", 120), (PLAYED, 40)), PLAYED, REPLY_LINE) is None

    def test_a_played_move_outside_the_candidates_says_nothing(self):
        """Without its own evaluation we cannot tell allowed from missed."""
        assert _mate_from_score(
            _cands(("Ra8+", 99990), ("Rc1", 50)), PLAYED, REPLY_LINE) is None

    def test_no_candidates_at_all_says_nothing(self):
        assert _mate_from_score([], PLAYED, REPLY_LINE) is None

    def test_a_mate_claim_needs_a_line_to_show(self):
        """Right-or-silent: no reply to name, no claim."""
        assert _mate_from_score(
            _cands(("Ra8+", 50), (PLAYED, -99990)), PLAYED, []) is None


class TestTheFloorIsBelowTheEncodingAndAboveRealEvals:
    def test_the_floor_sits_between_them(self):
        """mate_score=100000 in stockfish_service.get_candidate_lines, and the
        largest non-mate eval measured over 192,112 stored values is 8308."""
        assert 8308 < MATE_SCORE_FLOOR < 100_000

    def test_an_enormous_but_finite_eval_is_not_a_mate(self):
        assert _mate_from_score(
            _cands(("Ra8+", 50), (PLAYED, -8308)), PLAYED, REPLY_LINE) is None
