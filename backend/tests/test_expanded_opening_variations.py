import sys

sys.path.insert(0, '/app/backend')

from coach_engine.opening_plans import build_opening_coaching_context
from services.move_by_move_coach import get_variation_teaching


def test_italian_two_knights_variation_detected():
    moves = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"]
    context = build_opening_coaching_context(moves)
    teaching = get_variation_teaching(moves, context, "white")

    assert context is not None
    assert teaching is not None
    assert teaching["variation_name"] == "Italian Game — Two Knights / Fried Liver Ideas"
    assert teaching["next_expected_move"] == "d5"


def test_sicilian_open_variation_returns_black_plans():
    moves = ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3"]
    context = build_opening_coaching_context(moves)
    teaching = get_variation_teaching(moves, context, "black")

    assert context["name"] == "Sicilian Defense"
    assert teaching is not None
    assert teaching["variation_name"] == "Sicilian Defense — Open Sicilian"
    assert teaching["plans_for_user"]
    assert any("queenside" in plan.lower() or "d5" in plan.lower() for plan in teaching["plans_for_user"])


def test_french_advance_variation_detected():
    moves = ["e4", "e6", "d4", "d5", "e5", "c5", "c3"]
    context = build_opening_coaching_context(moves)
    teaching = get_variation_teaching(moves, context, "black")

    assert context["name"] == "French Defense"
    assert teaching is not None
    assert teaching["variation_name"] == "French Defense — Advance Variation"
    assert teaching["next_expected_move"] == "Nc6"


def test_caro_kann_classical_variation_detected():
    moves = ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5"]
    context = build_opening_coaching_context(moves)
    teaching = get_variation_teaching(moves, context, "black")

    assert context["name"] == "Caro-Kann Defense"
    assert teaching is not None
    assert teaching["variation_name"] == "Caro-Kann Defense — Classical Development"
    assert teaching["next_expected_move"] == "Nf3"


def test_kings_indian_main_setup_detected():
    moves = ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6"]
    context = build_opening_coaching_context(moves)
    teaching = get_variation_teaching(moves, context, "black")

    assert context["name"] == "King's Indian Defense"
    assert teaching is not None
    assert teaching["variation_name"] == "King's Indian Defense — Main Setup"
    assert any("kingside" in plan.lower() or "...e5" in plan.lower() for plan in teaching["plans_for_user"])


def test_london_variation_detected_with_white_plans():
    moves = ["d4", "d5", "Nf3", "Nf6", "Bf4", "c5", "e3"]
    context = build_opening_coaching_context(moves)
    teaching = get_variation_teaching(moves, context, "white")

    assert context["name"] == "London System"
    assert teaching is not None
    assert teaching["variation_name"] == "London System — ...c5 Challenge"
    assert any("c3" in plan.lower() or "ne5" in plan.lower() for plan in teaching["plans_for_user"])