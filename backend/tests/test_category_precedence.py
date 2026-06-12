"""
Regression: engine-hard category precedence + phase gates in the shared
classifier (_precedence_adjust). Signed off 2026-06-11;
docs/move_classification_from_gold_scope.md.

Right-or-original: only reclassify when the board proves a higher-priority
category. Pure (python-chess only, no DB/LLM/Stockfish).

Run: python3 tests/test_category_precedence.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analysis_interpreter import _precedence_adjust


def test_rule_b_king_endgame():
    # The two losing king moves from game 33769172 (queens off, ≤6 non-pawn,
    # king move, not in check) — king ACTIVITY, not safety.
    m28 = {"fen_before": "8/p1p2p1p/2p3p1/5b2/P7/2k2P2/2p3PP/2R1K3 b - - 6 28",
           "move": "Kb4", "move_uci": "c3b4"}
    m48 = {"fen_before": "8/7R/6p1/5b2/3k1P1P/2p5/2p5/2K5 b - - 0 48",
           "move": "Kc4", "move_uci": "d4c4"}
    assert _precedence_adjust("king_safety", m28) == "endgame_technique"
    assert _precedence_adjust("king_safety", m48) == "endgame_technique"


def test_rule_b_does_not_overfire_with_queens_on():
    # Queens still on the board → king safety is a real concept; leave it.
    mid = {"fen_before": "r1bqk2r/ppp2ppp/2n5/3np3/2B5/3P1N2/PPP2PPP/RNBQ1RK1 b kq - 0 6",
           "move": "Kf8", "move_uci": "e8f8"}
    assert _precedence_adjust("king_safety", mid) == "king_safety"


def test_rule_a_hang_precedence():
    # White Rd5; the engine line is ...cxd5 winning the rook for nothing → an
    # engine-confirmed immediate material loss. piece_safety (#1) must win.
    hang = {"fen_before": "4k3/8/2p5/8/8/8/8/3RK3 w - - 0 1",
            "move": "Rd5", "move_uci": "d1d5", "pv_after_played": ["cxd5"]}
    assert _precedence_adjust("piece_activity", hang) == "piece_safety"
    assert _precedence_adjust("tactical_oversight", hang) == "piece_safety"


def test_rule_a_no_loss_does_not_override():
    # Same move shape but the engine line does NOT win material (opponent just
    # moves the king) → rule A must NOT override (this is the ~37% FP the
    # geometry checker used to mislabel). Gap is preserved.
    no_loss = {"fen_before": "4k3/8/8/8/8/8/8/3RK3 w - - 0 1",
               "move": "Rd5", "move_uci": "d1d5", "pv_after_played": ["Ke7"]}
    assert _precedence_adjust("piece_activity", no_loss) == "piece_activity"


def test_rule_a_no_pv_does_not_override():
    # No engine line to check → abstain, never guess from geometry.
    no_pv = {"fen_before": "4k3/8/2p5/8/8/8/8/3RK3 w - - 0 1",
             "move": "Rd5", "move_uci": "d1d5"}
    assert _precedence_adjust("piece_activity", no_pv) == "piece_activity"


def test_no_gap_passthrough():
    assert _precedence_adjust(None, {"fen_before": "8/8/8/8/8/8/8/4K2k w - - 0 1"}) is None


if __name__ == "__main__":
    test_rule_b_king_endgame()
    test_rule_b_does_not_overfire_with_queens_on()
    test_rule_a_hang_precedence()
    test_no_gap_passthrough()
    print("PASS: test_category_precedence")
