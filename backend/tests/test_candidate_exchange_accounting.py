"""Constructed near-negatives: paid captures must not become free-piece losses.

These are small legal regression positions, not exports of Mohit's games.
"""
import chess
import pytest

from services.destination_safety_detector import (
    build_destination_safety_reason_bundle, derive_destination_safety_exact,
    grade_destination_safety_candidate,
)
from services.destination_safety_puzzle_proof import build_destination_safety_proof


@pytest.mark.parametrize("fen, played, reply, credit", [
    ("7k/8/8/8/8/6Qq/7P/6K1 b - - 0 1", "Qxg3", "hxg3", 900),
    ("7k/8/8/8/1b6/2N5/1P6/7K b - - 0 1", "Bxc3", "bxc3", 300),
    ("7k/8/8/8/1b6/2R5/1P6/7K b - - 0 1", "Bxc3", "bxc3", 500),
])
def test_capture_credit_in_detector_grade_and_explanation(fen, played, reply, credit):
    board = chess.Board(fen)
    move = board.parse_san(played)
    row = dict(fen_before=fen, move_uci=move.uci(), cp_loss=400, pv_after_played=[reply])
    fact = derive_destination_safety_exact(row)
    assert fact["fires"] is False
    assert fact["outcome"] == "handled"
    assert fact["played_material_gain_cp"] == credit
    assert fact["net_material_loss_cp"] <= 0
    grade = grade_destination_safety_candidate(fen, played)
    assert grade["status"] == "pass"
    bundle = build_destination_safety_reason_bundle(fen, played)
    assert bundle.safety_kind == "paid_for_exchange"
    assert any("first" in item.success_text for item in bundle.components)
    assert build_destination_safety_proof(board, row, played, "Kg8") is None


def test_bad_exchange_still_fails_after_crediting_the_pawn():
    fen = "3rk3/8/8/3p4/8/8/8/3QK3 w - - 0 1"
    grade = grade_destination_safety_candidate(fen, "Qxd5")
    assert grade["status"] == "fail"
    assert grade["net_material_loss_cp"] == 800


def test_paid_exchange_is_not_a_claim_that_the_move_is_best():
    fen = "7k/8/8/8/8/6Qq/7P/6K1 b - - 0 1"
    bundle = build_destination_safety_reason_bundle(fen, "Qxg3")
    assert bundle.target_result == "pass"
    assert "best" not in " ".join(c.success_text for c in bundle.components)
