"""Lock the simple_hang Caption promotion to its evidence.

The grade must not drift without the packet that justifies it, and the packet
must not be silently emptied or corrupted while the grade stays Caption.
"""
import json
import sys
from pathlib import Path

import chess
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.detector_quality import (  # noqa: E402
    QualityGrade,
    QualitySurface,
    explicit_authorizations,
    grade_for,
    is_authorized,
)

QUALITY_ID = "gap:piece_safety:simple_hang"
PACKET = BACKEND_ROOT / "data" / "corpus_snapshots" / "simple_hang_caption_packet.json"

SEE_FLOOR_CP = 150
CP_LOSS_FLOOR = 150
MIN_NON_OPPORTUNITIES = 20      # the locked Caption bar


@pytest.fixture(scope="module")
def packet():
    assert PACKET.exists(), f"promotion evidence missing: {PACKET}"
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_simple_hang_is_caption_grade():
    assert grade_for(QUALITY_ID) == QualityGrade.CAPTION


def test_caption_surface_is_authorized():
    assert is_authorized(QUALITY_ID, QualitySurface.CAPTION)


def test_plan_and_mastery_stay_unauthorized():
    # Plan needs a >=60% recall floor that 16.09% D_live miss recall fails.
    assert not is_authorized(QUALITY_ID, QualitySurface.PLAN)
    assert not is_authorized(QUALITY_ID, QualitySurface.MASTERY)


def test_caption_surface_admits_only_evidence_backed_ids():
    """Nothing reaches captions without its own reviewed promotion packet.

    Updated 2026-09-01: Quality V2 added review:verified_single_game_cause,
    promoted against the same locked bar (70/70 reviewed positives, Wilson
    lower bound ~94.8%, 30/30 abstentions, zero critical false claims). The
    guard's purpose is that every caption-authorised id is listed here
    deliberately -- not that the list has exactly one entry.
    """
    allowed = {
        QUALITY_ID,
        "review:verified_single_game_cause",
        "review:exact_endgame_result_change",
    }
    caption = {
        qid for qid in explicit_authorizations()
        if is_authorized(qid, QualitySurface.CAPTION)
    }
    unexpected = caption - allowed
    assert not unexpected, (
        "a detector reached the caption surface without being listed here; "
        f"add it only with its evidence packet: {sorted(unexpected)}"
    )


def test_evidence_ref_points_at_the_promotion_document():
    auth = explicit_authorizations()[QUALITY_ID]
    assert auth.evidence_ref == "docs/simple_hang_caption_promotion_2026_08_31.md"
    assert (BACKEND_ROOT.parent / auth.evidence_ref).exists()

    exact = explicit_authorizations()["review:exact_endgame_result_change"]
    assert exact.evidence_ref == "docs/exact_endgame_result_caption_evidence_2026_09_01.md"
    assert (BACKEND_ROOT.parent / exact.evidence_ref).exists()
    assert is_authorized("review:exact_endgame_result_change", QualitySurface.CAPTION)
    assert not is_authorized("review:exact_endgame_result_change", QualitySurface.PLAN)
    assert not is_authorized("review:exact_endgame_result_change", QualitySurface.MASTERY)


def test_packet_meets_the_locked_non_opportunity_bar(packet):
    assert len(packet["non_opportunities"]) >= MIN_NON_OPPORTUNITIES


def test_packet_thresholds_match_the_detector_floors(packet):
    thresholds = packet["thresholds"]
    assert thresholds["see_floor_cp"] == SEE_FLOOR_CP
    assert thresholds["cp_loss_floor"] == CP_LOSS_FLOOR


def test_every_non_opportunity_is_a_legal_position_and_move(packet):
    for case in packet["non_opportunities"]:
        board = chess.Board(case["fen_before"])
        assert board.is_valid(), case["fen_before"]
        move = chess.Move.from_uci(case["move_uci"])
        assert move in board.legal_moves, case


def test_no_non_opportunity_is_actually_a_hang(packet):
    """The critical property: silence must be correct in every case."""
    for case in packet["non_opportunities"]:
        both_gates = (
            case["see_cp"] >= SEE_FLOOR_CP
            and (case["cp_loss"] or 0) >= CP_LOSS_FLOOR
        )
        assert not both_gates, f"non-opportunity actually meets both gates: {case}"
        assert case["detector_says_hang"] is False


def test_non_opportunities_offer_the_opponent_a_real_capture(packet):
    """A quiet move proves nothing about restraint."""
    for case in packet["non_opportunities"]:
        assert case.get("best_capture_uci"), (
            "case has no opponent capture, so silence is uninformative: "
            f"{case['fen_before']}"
        )


def test_king_moves_never_appear(packet):
    for case in packet["non_opportunities"] + packet["adversarial"]:
        board = chess.Board(case["fen_before"])
        move = chess.Move.from_uci(case["move_uci"])
        assert board.piece_type_at(move.from_square) != chess.KING


def test_defended_cases_are_genuinely_defended(packet):
    defended = [c for c in packet["non_opportunities"] if c["reason"] == "defended"]
    assert defended, "the most meaningful true-negative class must be represented"
    for case in defended:
        assert case["see_cp"] <= 0, case
