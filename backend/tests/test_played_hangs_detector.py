"""
Regression tests for played_hangs_detector — real flagged FENs (2026-06-06).

Validates the two gates that took the detector from 16 fires / 3 low-cpl
misfires to 6 fires / 0 misfires across 105 flagged user-move positions.

Run: python3 -m pytest backend/tests/test_played_hangs_detector.py
"""
import chess
from services.played_hangs_detector import detect_played_hangs, clause_for


def _move(fen, san):
    b = chess.Board(fen)
    mv = next((m for m in b.legal_moves if b.san(m) == san), None)
    assert mv is not None, f"{san} not legal in {fen}"
    return b, mv


def test_fires_on_real_hang_gxf4_loses_rook():
    # fb-flagged: gxf4 leaves the h4 rook hanging (cp_loss 564). Should fire.
    b, mv = _move("r1b2rk1/pp2q1p1/2p4p/4p3/3P1p1R/2P1Q1PN/P4P1P/5RK1 w - - 0 20", "gxf4")
    hang = detect_played_hangs(b, mv, cp_loss=564)
    assert hang is not None
    assert hang["piece"] == "rook"
    assert hang["square"] == "h4"
    assert "rook on h4 hanging" in clause_for(hang)


def test_gated_out_even_recapture_exd4():
    # exd4 with cp_loss=2 is a fine recapture, NOT a hang. The cp_loss gate
    # must suppress it (raw detection would false-positive on the pawn).
    b, mv = _move("rnbqkb1r/pppp1ppp/5n2/4p3/2PP4/4P3/PP3PPP/RNBQKBNR b KQkq - 0 3", "exd4")
    assert detect_played_hangs(b, mv, cp_loss=2) is None


def test_low_cp_loss_always_gated():
    # Any move under the 100-cp gate is suppressed regardless of position.
    b, mv = _move("r1b2rk1/pp2q1p1/2p4p/4p3/3P1p1R/2P1Q1PN/P4P1P/5RK1 w - - 0 20", "gxf4")
    assert detect_played_hangs(b, mv, cp_loss=40) is None


if __name__ == "__main__":
    test_fires_on_real_hang_gxf4_loses_rook()
    test_gated_out_even_recapture_exd4()
    test_low_cp_loss_always_gated()
    print("all played_hangs_detector tests passed")
