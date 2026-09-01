import chess

from services.destination_safety_detector import (
    FACT_VERSION,
    QUALITY_ID,
    derive_destination_safety_exact,
    grade_destination_safety_candidate,
)
from services.detector_quality import QualityGrade, QualitySurface, grade_for, is_authorized


def _row(fen, move, reply, *, cp_loss=300):
    board = chess.Board(fen)
    played = chess.Move.from_uci(move)
    assert played in board.legal_moves
    board.push(played)
    return {
        "fen_before": fen,
        "fen_after": board.fen(),
        "move_uci": move,
        "cp_loss": cp_loss,
        "pv_after_played": [reply] if reply else [],
    }


def test_exact_destination_loss_fires():
    row = _row("3rk3/8/8/8/8/8/8/3QK3 w - - 0 1", "d1d5", "Rxd5")
    fact = derive_destination_safety_exact(row)
    assert fact["version"] == FACT_VERSION
    assert fact["quality_id"] == QUALITY_ID
    assert fact["eligible"] is True
    assert fact["outcome"] == "miss"
    assert fact["fires"] is True
    assert fact["opponent_reply_uci"] == "d8d5"
    assert fact["exact_exchange_gain_cp"] >= 150


def test_full_recapture_tree_rejects_safe_exchange():
    row = _row("4k3/8/2b5/8/P7/8/8/4KB2 w - - 0 1", "f1b5", "Bxb5")
    fact = derive_destination_safety_exact(row)
    assert fact["eligible"] is True
    assert fact["outcome"] == "handled"
    assert fact["exact_exchange_gain_cp"] == 0
    assert fact["fires"] is False
    assert fact["reason"] == "exchange_is_safe"


def test_low_stockfish_consequence_is_handled():
    row = _row(
        "3rk3/8/8/8/8/8/8/3QK3 w - - 0 1",
        "d1d5",
        "Rxd5",
        cp_loss=149,
    )
    fact = derive_destination_safety_exact(row)
    assert fact["outcome"] == "handled"
    assert fact["fires"] is False
    assert fact["reason"] == "move_not_costly"


def test_promotion_exchange_is_measured_but_not_promoted_without_packet():
    # 1.Na1 bxa1=Q 2.Rxa1: Black wins a knight and promotes, then loses the
    # promoted queen. Net gain is 200cp; omitting the promotion delta would
    # incorrectly call the destination safe.
    row = _row(
        "4k3/8/8/8/8/8/1pN1K3/7R w - - 0 1",
        "c2a1",
        "bxa1=Q",
        cp_loss=300,
    )
    fact = derive_destination_safety_exact(row)
    assert fact["exact_exchange_gain_cp"] == 200
    assert fact["outcome"] == "miss"
    assert fact["fires"] is False
    assert fact["reason"] == "promotion_exchange_not_promoted"


def test_missing_stored_reply_keeps_miss_measurable_but_does_not_diagnose():
    row = _row("3rk3/8/8/8/8/8/8/3QK3 w - - 0 1", "d1d5", None)
    fact = derive_destination_safety_exact(row)
    assert fact["outcome"] == "miss"
    assert fact["fires"] is False
    assert fact["reason"] == "missing_stored_reply"


def test_pawn_and_king_moves_are_not_eligible():
    pawn = _row("4k3/8/8/8/8/8/3P4/4K3 w - - 0 1", "d2d4", None)
    king = _row("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "e1e2", None)
    assert derive_destination_safety_exact(pawn)["eligible"] is False
    assert derive_destination_safety_exact(king)["eligible"] is False


def test_quality_authorization_is_plan_grade_and_evidence_locked():
    assert grade_for(QUALITY_ID) == QualityGrade.PLAN
    assert is_authorized(QUALITY_ID, QualitySurface.PLAN)
    assert is_authorized(QUALITY_ID, QualitySurface.MASTERY)
    assert is_authorized(QUALITY_ID, QualitySurface.CAPTION)


def test_counterfactual_safe_non_best_piece_move_passes_narrow_concept():
    result = grade_destination_safety_candidate(
        "3rk3/8/8/8/8/8/8/3QK3 w - - 0 1",
        "d1a1",
    )
    assert result["status"] == "pass"
    assert result["proofs_agree"] is True
    assert result["exact_exchange_gain_cp"] == 0


def test_counterfactual_move_to_losing_destination_fails_narrow_concept():
    result = grade_destination_safety_candidate(
        "3rk3/8/8/8/8/8/8/3QK3 w - - 0 1",
        "d1d5",
    )
    assert result["status"] == "fail"
    assert result["exact_exchange_gain_cp"] >= 150
    assert result["proofs_agree"] is True


def test_counterfactual_pawn_move_is_not_claimed_as_concept_understanding():
    result = grade_destination_safety_candidate(
        "4k3/8/8/8/8/8/3P4/3QK3 w - - 0 1",
        "d2d4",
    )
    assert result["status"] == "unmeasured"
    assert result["reason"] == "piece_not_eligible"


def test_counterfactual_illegal_move_fails_closed():
    result = grade_destination_safety_candidate(
        "4k3/8/8/8/8/8/8/3QK3 w - - 0 1",
        "d1d9",
    )
    assert result["status"] == "unmeasured"
