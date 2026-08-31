from __future__ import annotations

import inspect

import chess

from services.concept_detectors.opening_plan_play import (
    detect_opening_plan_application,
    exact_opening_plan_content_ids,
)
from services.curriculum_content_validator import get_publishable_content_ids


def _marshall_position():
    board = chess.Board()
    for san in ("d4", "d5", "c4", "Nf6"):
        board.push_san(san)
    return board


def test_exact_marshall_plan_move_requires_stored_best_agreement():
    board = _marshall_position()
    move = board.parse_san("cxd5")

    assert detect_opening_plan_application(
        board, move, chess.WHITE, move_number=3, best_move_san="cxd5"
    ) == "applied"
    assert detect_opening_plan_application(
        board, move, chess.WHITE, move_number=3, best_move_san="Nc3"
    ) is None


def test_non_authored_move_does_not_inherit_the_plan_label():
    board = _marshall_position()
    move = board.parse_san("Nc3")

    assert detect_opening_plan_application(
        board, move, chess.WHITE, move_number=3, best_move_san="Nc3"
    ) is None


def test_every_publishable_opening_plan_is_exactly_indexed():
    assert set(exact_opening_plan_content_ids()) == get_publishable_content_ids(
        "opening_ideas"
    )


def test_opening_plan_detector_has_no_runtime_engine_llm_or_network_call():
    import services.concept_detectors.opening_plan_play as module

    source = inspect.getsource(module).lower()
    forbidden = (
        "import stockfish", "chess.engine", "call_llm", "openai",
        "anthropic", "requests.", "httpx", "subprocess",
    )
    assert not [token for token in forbidden if token in source]
