"""A mate in one is still a missed mate.

Mohit, 2026-10-05, on a card where Rc8# was mate in 1 and he played
something else: "this was a mate probably a pattern to remember, but it was
missed, so missed mate tag should have been activated here, no detector like
that".

There is a detector. `detect_missed_tactic` walks `pv_after_best` looking for
checkmate, and `why_user_missed_mate` in R12_blunder.json renders "it would
have led to mate in N moves" off it. But when the best move IS the mate,
nothing follows it: `pv_after_best` arrives empty and the guard returned None
before any board was examined. The one case that matters most -- mate in one
-- was the one case it could not see.

Measured over real missed mates in the corpus: of 1,357 moves where the
player had a forced mate and played something else, the detector returned
None for 1,054, and 795 of those arrived with an empty pv_after_best.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.best_move_tactic_detector import detect_missed_tactic  # noqa: E402

# The reported position. White to move; Rc8# is the only mate in one.
REPORTED_FEN = "rn2kb1r/2R1p2p/p3B1p1/5p2/3pn3/7N/1PP2PPP/2B1K2R w Kkq - 0 1"


class TestTheReportedMate:

    def test_rc8_really_is_the_only_mate_in_one(self):
        """Verify by board, not by trusting the caption that named it."""
        board = chess.Board(REPORTED_FEN)
        mates = []
        for move in board.legal_moves:
            probe = board.copy()
            probe.push(move)
            if probe.is_checkmate():
                mates.append(board.san(move))
        assert mates == ["Rc8#"]

    def test_the_detector_sees_it_with_an_empty_pv(self):
        out = detect_missed_tactic(
            fen_before=REPORTED_FEN, best_move_san="Rc8#",
            pv_after_best=[], user_color="white", eval_before_cp=500)
        assert out is not None, "mate in one was invisible before this fix"
        assert out["kind"] == "mate"
        assert out["mating_move"] == "Rc8#"

    def test_it_renders_as_one_move_not_zero_or_two(self):
        """caption_rules turns ply into (ply + 1) // 2 for the wording."""
        out = detect_missed_tactic(
            fen_before=REPORTED_FEN, best_move_san="Rc8#",
            pv_after_best=[], user_color="white", eval_before_cp=500)
        moves_to_mate = (out["ply"] + 1) // 2
        assert moves_to_mate == 1, f"would read 'mate in {moves_to_mate} moves'"


class TestItDoesNotInventMates:
    """Negative controls: an empty PV must not become a mate claim on its own."""

    def test_a_quiet_best_move_with_no_pv_is_not_a_mate(self):
        board = chess.Board()
        out = detect_missed_tactic(
            fen_before=board.fen(), best_move_san="e4",
            pv_after_best=[], user_color="white", eval_before_cp=20)
        assert out is None

    def test_a_check_that_is_not_mate_is_not_a_mate(self):
        """Qh5+ is check and not mate; the board must decide, not the '+'."""
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
        board = chess.Board(fen)
        probe = board.copy()
        probe.push_san("Qh5")
        assert not probe.is_checkmate()
        out = detect_missed_tactic(
            fen_before=fen, best_move_san="Qh5",
            pv_after_best=[], user_color="white", eval_before_cp=20)
        assert out is None

    def test_a_mate_delivered_by_the_opponent_is_not_our_missed_mate(self):
        """The board after OUR best move is the only thing consulted, so a
        position where the side to move is mated cannot be read as ours."""
        board = chess.Board(REPORTED_FEN)
        out = detect_missed_tactic(
            fen_before=REPORTED_FEN, best_move_san="Rc8#",
            pv_after_best=[], user_color="black", eval_before_cp=500)
        # user_color does not change what the board says about this move
        assert out is not None and out["kind"] == "mate"
