"""The why button must not tell a player to make a move it would fault them for.

Two of our own constants disagreed. `why_on_demand.CLOSENESS_CP` was 50, the
window inside which a move may be recommended; `services.severity` calls
anything 30cp or worse an inaccuracy. So the function was free to prescribe a
move it would itself grade a mistake, and it did:

    "c5 wins their pawn."        engine approves of Be7, Nc6, Nf6
    "Qe8 wins their knight."     engine approves of Qe7
    "g5 chases their bishop."    engine approves of f5, Bxc4, Na6

Measured over 309 faulted positions, the same positions at both settings:

    window   answered    missed answers   wrong   received   wrong
      50cp   248 (80%)        59            8       189        0
      30cp   240 (78%)        51            0       189        0

Every error in the engine was in the `missed` direction and every one of them
was this. Tightening loses 8 answers and all 8 are the wrong ones; not a single
correct answer is lost.

The test below is on the RELATIONSHIP, not the number: the window may never
exceed the floor at which we would fault the move, however either is later
tuned. A literal `== 30` would pass while someone raised the floor to 40 and
reopened the hole.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.severity import SEVERITY_THRESHOLDS, classify_severity  # noqa: E402
from services.why_on_demand import CLOSENESS_CP, explain  # noqa: E402


class TestTheWindowCannotExceedTheFloor:
    def test_the_recommendation_window_is_the_inaccuracy_floor(self):
        assert CLOSENESS_CP <= SEVERITY_THRESHOLDS["inaccuracy"]

    def test_a_move_inside_the_window_is_never_graded_a_fault(self):
        """The relationship stated as chess: anything we may recommend must
        grade `good` by the same evaluator the card's badge uses."""
        for gap in range(0, CLOSENESS_CP):
            assert classify_severity(gap, mover_is_user=True).tier == "good", gap

    def test_the_first_cp_outside_the_window_is_a_fault(self):
        """...and the boundary is exactly where faulting begins, so the window
        is not needlessly narrow either."""
        assert classify_severity(
            CLOSENESS_CP, mover_is_user=True).tier == "inaccuracy"


class TestItDeclinesToRecommendAMoveTheEngineRejects:
    # Black to move; Nf6 and d5 are sensible, and a 40cp-worse move exists.
    FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"

    def _candidates(self, *pairs):
        out = []
        for san, cp in pairs:
            board = chess.Board(self.FEN)
            mv = board.parse_san(san)
            out.append({"move_san": san, "move_uci": mv.uci(),
                        "eval_cp": cp, "line_san": [san]})
        return out

    def test_a_move_forty_centipawns_below_best_is_not_prescribed(self):
        """40cp is inside the old 50 window and outside the new one. Nothing
        else about the position has changed, so if an answer comes back naming
        that move, the window has been widened again."""
        cands = self._candidates(("e5", 0), ("Nf6", -40))
        out = explain(self.FEN, "h5", ["e4"], cands, cp_loss=120)
        if out is not None and out.get("direction") == "missed":
            assert out.get("move_san") != "Nf6"

    def test_the_diagnosis_half_is_untouched_by_the_window(self):
        """189 `received` answers, zero errors, at either setting. The window
        only ever gated the prescription, and this is the guard against
        'fixing' correctness by silencing the half that was already right."""
        board = chess.Board(self.FEN)
        board.push(board.parse_san("d5"))
        # a capture is available to White; the received half reads the line it
        # is given and never consults CLOSENESS_CP at all
        import services.why_on_demand as W
        src = Path(W.__file__).read_text(encoding="utf-8")
        head, _, tail = src.partition("# 2. The opportunity we missed")
        assert "CLOSENESS_CP" not in head.split("def explain(")[-1], (
            "the received branch now reads CLOSENESS_CP; it must not")
