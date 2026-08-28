import inspect
import json
from pathlib import Path

import chess

from services.concept_detectors.rule_of_the_square import (
    analyze_rule_of_square,
    detect_rule_of_the_square_application,
    is_rule_of_square_relevant,
)
from services.endgame_detectors.rule_of_square_detector import (
    detect_rule_of_square,
)
from services.caption_facts import _p_end_rule_of_square


def test_canonical_fact_handles_white_pawn_direction_from_color():
    board = chess.Board("7k/8/8/P7/8/8/8/4K3 w - - 0 1")
    fact = analyze_rule_of_square(board)

    assert fact is not None
    assert fact.pawn_color == chess.WHITE
    assert fact.promotion_square == chess.A8


def test_canonical_fact_handles_black_pawn_direction_from_color():
    board = chess.Board("4k3/8/8/8/8/p7/8/7K b - - 0 1")
    fact = analyze_rule_of_square(board)

    assert fact is not None
    assert fact.pawn_color == chess.BLACK
    assert fact.promotion_square == chess.A1


def test_mutual_pawn_race_abstains():
    board = chess.Board("8/8/8/8/P6p/8/K7/5k2 w - - 0 1")

    assert analyze_rule_of_square(board) is None
    assert not is_rule_of_square_relevant(board.fen())


def test_non_pawn_piece_abstains():
    board = chess.Board("7k/8/8/P7/8/8/8/R3K3 w - - 0 1")

    assert analyze_rule_of_square(board) is None


def test_mastery_and_legacy_adapters_share_one_grade():
    board = chess.Board("7k/8/8/P7/8/8/8/4K3 w - - 0 1")
    move = board.parse_san("a6")

    assert (
        detect_rule_of_the_square_application(board, move, chess.WHITE)
        == "applied"
    )
    assert detect_rule_of_square(board, move, chess.WHITE) == "applies"


def test_legacy_module_contains_no_independent_geometry():
    import services.endgame_detectors.rule_of_square_detector as legacy

    source = inspect.getsource(legacy)
    assert "square_distance" not in source
    assert "_can_king_catch_pawn" not in source
    assert "detect_rule_of_the_square_application" in source


def test_caption_module_contains_no_retired_square_formula():
    import services.caption_facts as caption_facts

    source = inspect.getsource(caption_facts)
    assert "def _king_inside_pawn_square" not in source
    assert "def _pawn_distance_to_promote" not in source
    assert "analyze_rule_of_square" in source


def test_committed_gold_packet_matches_canonical_truth():
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "detector_gold"
        / "rule_of_square_v1.json"
    )
    packet = json.loads(path.read_text(encoding="utf-8"))
    assert packet["claim"].startswith("Can the defending king catch")

    for case in packet["cases"]:
        fact = analyze_rule_of_square(chess.Board(case["fen"]))
        assert (fact is not None) is case["expected_applicable"], case["case_id"]
        if fact is not None:
            assert fact.catchable is case["expected_catchable"], case["case_id"]


def test_caption_adapter_accepts_immediate_catch_and_rejects_walk_away():
    board = chess.Board("8/8/8/8/8/8/2P5/K1k5 b - - 0 1")
    result = _p_end_rule_of_square(
        {
            "phase": "endgame",
            "cp_loss": 200,
            "best_move_san": "Kxc2",
            "played_san": "Kd2",
            "moving_piece_color": "black",
            "eval_before_cp": 0,
        },
        board,
    )

    assert result is not None
    assert result["principle_id"] == "END_RULE_OF_SQUARE"
    assert result["evidence"]["pawn_square"] == "c2"
    assert result["evidence"]["catchable_after_best"] is True
