"""
Smoke tests for opp_quiet_threat_detector (v0.1, 2026-06-07). See the module
docstring + MORNING_SUMMARY.md §5C for the review caveat (best-move gate).
"""
import chess
from services.opp_quiet_threat_detector import detect_quiet_when_threatened


def _move(fen, san):
    b = chess.Board(fen)
    mv = next((m for m in b.legal_moves if b.san(m) == san), None)
    assert mv is not None, f"{san} not legal in {fen}"
    return b, mv


def test_gated_out_below_cp_loss():
    # any move under the 100-cp gate returns None
    b, mv = _move(chess.STARTING_FEN, "e4")
    assert detect_quiet_when_threatened(b, mv, "d4", cp_loss=10) is None


def test_no_winnable_minor_no_fire():
    # starting position: nothing winnable, so never fires regardless of cp_loss
    b, mv = _move(chess.STARTING_FEN, "e4")
    assert detect_quiet_when_threatened(b, mv, "d4", cp_loss=300) is None


def test_requires_best_move():
    b, mv = _move(chess.STARTING_FEN, "e4")
    assert detect_quiet_when_threatened(b, mv, None, cp_loss=300) is None


if __name__ == "__main__":
    test_gated_out_below_cp_loss()
    test_no_winnable_minor_no_fire()
    test_requires_best_move()
    print("opp_quiet_threat_detector smoke tests passed")
