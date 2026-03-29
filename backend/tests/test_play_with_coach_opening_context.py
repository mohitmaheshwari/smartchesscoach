import chess
import sys

sys.path.insert(0, '/app/backend')

from coach_engine.opening_plans import build_opening_coaching_context
from services.move_by_move_coach import check_for_traps, get_variation_teaching


def test_qgd_context_inherits_family_variations():
    context = build_opening_coaching_context(["d4", "d5", "c4", "e6"])

    assert context is not None
    assert context["name"] == "Queen's Gambit Declined"
    assert context["family_name"] == "Queen's Gambit"
    assert "qgd_main" in context["variations"]


def test_slav_context_inherits_family_variations():
    context = build_opening_coaching_context(["d4", "d5", "c4", "c6"])

    assert context is not None
    assert context["name"] == "Slav Defense"
    assert context["family_name"] == "Queen's Gambit"
    assert "slav_main" in context["variations"]


def test_variation_teaching_guides_when_user_deviates():
    moves = ["d4", "d5", "c4", "e6", "Nf3"]
    context = build_opening_coaching_context(moves)

    teaching = get_variation_teaching(moves, context)

    assert teaching is not None
    assert teaching["expected_move"] == "Nc3"
    assert teaching["played_move"] == "Nf3"
    assert teaching["matched_expected"] is False
    assert "Complete development" in teaching["teaching"]


def test_qgd_trap_warning_is_available_in_live_position():
    moves = ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7"]
    context = build_opening_coaching_context(moves)
    board = chess.Board()

    for move in moves:
        board.push_san(move)

    trap = check_for_traps(moves, context, board)

    assert trap is not None
    assert "Elephant Trap" in trap["warning"]