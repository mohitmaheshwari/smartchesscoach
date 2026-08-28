"""Regression tests for the causal Chess Brain king-safety adapter."""

import inspect

import chess
import pytest

from services.board_state_describer import king_safety_state
from services.chess_brain.detector_registry import (
    CAUSAL_MISTAKE_MIN_CP_LOSS,
    TRAPPED_PIECE_MIN_CP_LOSS,
    DetectorRegistry,
    detect_king_safety,
)


SHIELD_FEN = "2kr1b1r/1pp5/p2p4/3P1q1p/6pP/Q3B3/PP3PP1/2R2RK1 w - - 0 20"
ATTACK_FEN = "rn1q3r/ppp1nkpp/4b3/2b2pN1/8/1Q1P4/PP4PP/RNB1K2R b KQ - 3 10"
ENDGAME_FEN = "8/8/pk2R3/2p1P2B/2Prb1PP/1P1p4/P2K4/8 b - - 0 33"
ISSUE_SWAP_FEN = "1k2r3/p1p1r1p1/Bp1p3p/6qb/1PQ1P3/2P2PPn/P2N3P/R3R1K1 w - - 3 24"


def _detect(fen, played, best, cp_loss, move_number):
    return detect_king_safety(
        chess.Board(fen),
        played,
        best,
        {"cp_loss": cp_loss, "move_number": move_number},
    )


def test_pawn_shield_worsening_is_detected():
    result = _detect(SHIELD_FEN, "g3", "Qc3", 193, 20)

    assert result.detected
    assert result.details["subtype"] == "pawn_shield"
    assert result.details["issues"] == ["pawn_shield"]
    assert result.details["missing_shield"] == 2
    assert result.details["avoidable_with"] == "Qc3"


def test_king_zone_attack_worsening_is_detected():
    result = _detect(ATTACK_FEN, "Kf6", "Ke8", 9740, 10)

    assert result.detected
    assert result.details["subtype"] == "king_zone_attack"
    assert result.details["attackers_near"] == 3
    assert set(result.details["attacker_squares"]) == {"c1", "b3", "g5"}


def test_canonical_state_owns_subtype_thresholds():
    board = chess.Board(SHIELD_FEN)
    board.push_san("g3")

    state = king_safety_state(board, chess.WHITE, 20)

    assert state.king_square == "g1"
    assert state.missing_shield == 2
    assert state.opponent_has_queen
    assert state.effective_issues == frozenset({"pawn_shield"})


def test_endgame_position_abstains():
    assert not _detect(ENDGAME_FEN, "Ka5", "Kc7", 108, 33).detected


def test_cross_issue_swap_is_not_called_an_improvement():
    assert not _detect(ISSUE_SWAP_FEN, "Kf1", "Kg2", 118, 24).detected


@pytest.mark.parametrize(
    "best, context_cp",
    [
        ("Qc3", 99),
        ("Qc3", None),
        ("g3", 193),
        ("", 193),
    ],
)
def test_detector_abstains_without_causal_engine_evidence(best, context_cp):
    result = _detect(SHIELD_FEN, "g3", best, context_cp, 20)
    assert not result.detected


def test_registry_requires_best_move_and_shared_floor():
    detector = DetectorRegistry().get_detector("king_safety_detector")

    assert detector is not None
    assert detector.requires_best_move
    assert CAUSAL_MISTAKE_MIN_CP_LOSS == 100
    assert TRAPPED_PIECE_MIN_CP_LOSS == CAUSAL_MISTAKE_MIN_CP_LOSS


def test_detector_is_only_an_adapter_to_canonical_state():
    source = inspect.getsource(detect_king_safety)

    assert "king_safety_state" in source
    assert "shield_squares" not in source
    assert "king_file in [6, 2]" not in source

