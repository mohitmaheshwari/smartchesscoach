"""
Tests for missed_mate_detector (2026-06-07). Objective end of the why-gap —
mate is mate, so these are exact.
"""
import chess
from services.missed_mate_detector import detect_missed_mate, clause_for


def test_mate_in_one():
    # Back-rank mate: white Ra1, pawns f2 g2 h2; black Kg8, pawns f7 g7 h7.
    # Ra8# (8th-rank check, king boxed in by its own pawns).
    b = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1")
    mm = detect_missed_mate(b, "Ra8", None, cp_loss=500)
    assert mm is not None and mm["kind"] == "mate_in_1"
    assert "checkmate" in clause_for(mm)


def test_forced_mate_via_pv():
    # best move not itself mate, but PV carries the '#'.
    b = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1")
    mm = detect_missed_mate(b, "Kg1", ["Kg1", "Kh8", "Ra8#"], cp_loss=300)
    assert mm is not None and mm["kind"] == "forced_mate"
    assert mm["mate_in"] == 2


def test_no_mate_returns_none():
    b = chess.Board(chess.STARTING_FEN)
    assert detect_missed_mate(b, "e4", ["e4", "e5"], cp_loss=300) is None


def test_cp_loss_gate():
    b = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1")
    assert detect_missed_mate(b, "Ra8", None, cp_loss=20) is None


if __name__ == "__main__":
    test_mate_in_one()
    test_forced_mate_via_pv()
    test_no_mate_returns_none()
    test_cp_loss_gate()
    print("missed_mate_detector tests passed")
