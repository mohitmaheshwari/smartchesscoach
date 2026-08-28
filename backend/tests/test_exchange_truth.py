import chess

from services.caption_facts import (
    _p_tac_hanging_piece,
    _see_for_played_move,
    legal_exchange_gain,
)
from services.shape_detectors import detect_free_piece
from scripts.audit_caption_principles_per_fire import _verify_tac_hanging_piece
from scripts.audit_shape_patterns_per_fire import _verify_free_piece


XRAY_RECAPTURE_FEN = "7k/8/8/8/8/2n5/1B6/b6K w - - 0 1"


def test_free_piece_rejects_defender_revealed_by_capture():
    board = chess.Board(XRAY_RECAPTURE_FEN)
    fires = detect_free_piece(board)
    assert not any(
        event["executing_move"] == "b2c3" and event["targets"] == ["c3"]
        for event in fires
    )
    assert any(event["executing_move"] == "b2a1" for event in fires)


def test_independent_free_piece_audit_rejects_xray_recapture():
    board = chess.Board(XRAY_RECAPTURE_FEN)
    passed, reason = _verify_free_piece(board, "b2", ["c3"], "b2c3")
    assert passed is False
    assert "legal recapture" in reason


def test_legal_exchange_replays_xray_recapture():
    board = chess.Board(XRAY_RECAPTURE_FEN)
    move = chess.Move.from_uci("b2c3")
    assert legal_exchange_gain(
        board, chess.C3, chess.WHITE, first_move=move
    ) == 0
    assert _see_for_played_move(board, move) == 0


def test_played_capture_is_forced_instead_of_grading_cheaper_attacker():
    board = chess.Board("7k/8/5n2/3p4/2P5/8/8/3Q3K w - - 0 1")
    queen_capture = chess.Move.from_uci("d1d5")

    assert queen_capture in board.legal_moves
    # Qxd5 Nxd5 cxd5: pawn + knight won (400), queen lost (900).
    assert _see_for_played_move(board, queen_capture) == -500


def test_hanging_principle_rejects_check_when_piece_cannot_be_taken():
    board = chess.Board("3r1r2/2p3pk/5q1p/3P4/4P2P/P5b1/1PQ2PP1/2B2K2 w - - 1 27")
    move = board.parse_san("e5+")
    after = board.copy(stack=False)
    after.push(move)
    assert legal_exchange_gain(after, chess.E5, after.turn) == 0

    facts = {
        "cp_loss": 67,
        "played_san": "e5+",
        "best_move_san": "Qc7",
        "mover_is_user": True,
        "is_exchange_losing": False,
        "pieces_now_undefended": [],
    }
    assert _p_tac_hanging_piece(facts, board) is None

    passed, reason, scope = _verify_tac_hanging_piece(
        board,
        {
            "evidence": {
                "hanging_piece_square": "e5",
                "piece_color": "white",
            }
        },
        "e5+",
    )
    assert (passed, scope) == (False, "GEOMETRIC")
    assert "not winning" in reason


def test_legal_exchange_counts_real_hang():
    board = chess.Board("7k/8/8/8/8/8/4r3/3Q3K w - - 0 1")
    assert legal_exchange_gain(board, chess.E2, chess.WHITE) == 500
