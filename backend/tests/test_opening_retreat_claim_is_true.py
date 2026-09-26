"""The retreat claim must be true, and must not be the old vacuous one.

`tempo_wasted_by_repeat` told the player he lost a tempo "by moving the same
piece twice". Measured over all 557 fires on 2026-09-26:

  557 of 557  the piece had indeed moved before -- a knight or bishop off its
              home square must have, so the claim was VACUOUS and was never
              computed anyway.
  240 of 557  (43.1%) the engine's own best move moves THAT SAME PIECE, so
              moving it again was not the error. Negative control over 4,000
              opening mistakes: 13.9%.
  163 of 557  (29.3%) the piece was under attack and had to move.

These tests hold the two gates that reduce 557 to 154.
"""
import sys
from pathlib import Path

import chess

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.cognitive_gap_subtypes import (  # noqa: E402
    _has_legal_capture_of,
    classify_opening_knowledge,
)

# A real fire from game 1a6e31d3, move 7: Black's Nf6-d7 costing 192cp, with
# nothing attacking f6. Taken from production rather than hand-built -- an
# invented position whose move is not actually punished tests nothing.
RETREAT_FEN = "r1bq1rk1/ppp1ppbp/2n2np1/3p4/3P1B2/2NBPN2/PPP2PPP/R2Q1RK1 b - - 6 7"


def _mv(fen, uci, san, best_uci, cp_loss=192, move_number=7):
    return {"fen_before": fen, "move_uci": uci, "move": san,
            "best_move_uci": best_uci, "cp_loss": cp_loss,
            "move_number": move_number}


def test_a_free_retreat_the_engine_disagrees_with_is_named():
    subtype, severity = classify_opening_knowledge(
        _mv(RETREAT_FEN, "f6d7", "Nd7", "c6b4"), None, None)
    assert subtype == "retreated_a_developed_piece"
    assert severity


def test_the_old_vacuous_name_is_gone():
    """The name is the documentation. A label that says "moved the same piece
    twice" describes something this code never computes."""
    subtype, _ = classify_opening_knowledge(
        _mv(RETREAT_FEN, "f6d7", "Nd7", "c6b4"), None, None)
    assert subtype != "tempo_wasted_by_repeat"


def test_silent_when_the_engine_moves_that_same_piece():
    """43.1% of the old fires. If the engine wants this piece moved too, the
    error is where it went -- and we do not know where from this branch."""
    subtype, _ = classify_opening_knowledge(
        _mv(RETREAT_FEN, "f6d7", "Nd7", "f6e4"), None, None)
    assert subtype != "retreated_a_developed_piece"


def test_silent_when_the_piece_was_being_chased():
    """29.3% of the old fires. A chased piece has to move; the teachable error
    belongs to the move that walked it into the chase."""
    # Black knight on g4 with a white pawn on h3 legally attacking it.
    fen = "rnbqkb1r/pppppppp/8/8/6n1/7P/PPPPPPP1/RNBQKBNR b KQkq - 0 3"
    board = chess.Board(fen)
    assert _has_legal_capture_of(board, chess.G4, chess.WHITE), "fixture broken"
    subtype, _ = classify_opening_knowledge(
        _mv(fen, "g4f6", "Nf6", "d7d5", move_number=3), None, None)
    assert subtype != "retreated_a_developed_piece"


def test_silent_with_no_engine_best_move():
    """No engine truth, no accusation. Returning a subtype here would make the
    claim rest on geometry alone, which is how the 43.1% happened."""
    mv = _mv(RETREAT_FEN, "f6d7", "Nd7", "c6b4")
    for key in ("best_move_uci", "best_move", "pv_best_uci"):
        mv.pop(key, None)
    subtype, _ = classify_opening_knowledge(mv, None, None)
    assert subtype != "retreated_a_developed_piece"


def test_a_forward_move_is_not_a_retreat():
    subtype, _ = classify_opening_knowledge(
        _mv(RETREAT_FEN, "f6e4", "Ne4", "c6b4"), None, None)
    assert subtype != "retreated_a_developed_piece"


def test_a_pinned_attacker_does_not_count_as_a_chase():
    """board.attackers() is PSEUDO-legal. A pinned attacker cannot take, so
    counting it would excuse a retreat that was never forced."""
    # White knight on d5 is the only thing "attacking" c7, and it is pinned
    # against the white king on d1 by the black rook on d8.
    fen = "3rk3/2p5/8/3N4/8/8/8/3K4 w - - 0 1"
    board = chess.Board(fen)
    assert board.attackers(chess.WHITE, chess.C7), "pseudo-legal attacker gone"
    assert not _has_legal_capture_of(board, chess.C7, chess.WHITE)


def test_a_real_attacker_does_count():
    """Positive control for the helper: an absence proves nothing unless the
    same probe is shown returning True where it must."""
    board = chess.Board("4k3/2p5/1P6/8/8/8/8/4K3 w - - 0 1")
    assert _has_legal_capture_of(board, chess.C7, chess.WHITE)
