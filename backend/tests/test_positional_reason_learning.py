from __future__ import annotations

import pytest

from services.positional_reason_learning import (
    PositionalReasonValidationError,
    normalize_submission,
    position_fingerprint,
    structural_signature,
    voice_warnings,
)


ROW = {
    "fen": "8/8/8/8/3k4/8/4K2R/8 w - - 2 40",
    "game_id": "g1",
    "move_number": 40,
    "side_to_move": "white",
    "played_san": "Rh1",
    "best_san": "Kf3",
    "played_uci": "h2h1",
    "best_uci": "e2f3",
    "cp_loss": 180,
    "bucket": "bare endgame",
    "already_explained_by": [],
}


def eligible_payload():
    return {
        "fen": ROW["fen"],
        "disposition": "eligible_positional",
        "concept_label": "Bring the king toward the action",
        "better_move_fact": "Kf3 brings the king one square closer to the center.",
        "played_move_fact": "Rh1 leaves the king on e2 and moves the rook away.",
        "contrast": "The king can support both sides from f3, while the rook move adds no new job.",
        "transferable_lesson": "In a quiet endgame, improve your king before moving an active rook.",
    }


def test_fingerprint_ignores_move_clocks_but_keeps_move_pair():
    same_position = "8/8/8/8/3k4/8/4K2R/8 w - - 19 99"
    assert position_fingerprint(ROW["fen"], "h2h1", "e2f3") == position_fingerprint(
        same_position, "h2h1", "e2f3"
    )
    assert position_fingerprint(ROW["fen"], "h2h1", "e2f3") != position_fingerprint(
        same_position, "h2h1", "e2d3"
    )


def test_structural_signature_groups_by_coarse_move_geometry():
    signature = structural_signature(ROW["fen"], "h2h1", "e2f3")
    assert len(signature) == 64
    assert signature == structural_signature(ROW["fen"], "h2h1", "e2f3")


def test_eligible_reason_requires_all_four_teaching_parts():
    payload = eligible_payload()
    payload["contrast"] = ""
    with pytest.raises(PositionalReasonValidationError, match="contrast is required"):
        normalize_submission(payload, ROW, submitted_by="admin")


def test_eligible_reason_is_candidate_only_until_promoted():
    submission = normalize_submission(
        eligible_payload(), ROW, submitted_by="admin", now="2026-09-09T00:00:00+00:00"
    )
    assert submission["disposition"] == "eligible_positional"
    assert submission["proof_coverage"] == 1.0
    assert submission["caption_eligible"] is False
    assert submission["tracker_eligible"] is False
    assert submission["promotion"]["ready"] is False
    assert submission["proof"]["authority"] == "human_reviewed_candidate"


@pytest.mark.parametrize(
    "disposition",
    [
        "not_mistake",
        "already_decided",
        "tactical_or_forced",
        "duplicate",
        "unstable_engine_choice",
        "insufficient_evidence",
    ],
)
def test_ineligible_dispositions_never_reach_caption_or_tracker(disposition):
    submission = normalize_submission(
        {"fen": ROW["fen"], "disposition": disposition, "notes": "Reviewed."},
        ROW,
        submitted_by="admin",
    )
    assert submission["caption_eligible"] is False
    assert submission["tracker_eligible"] is False
    assert submission["proof_coverage"] == 0.0


def test_voice_warnings_flag_jargon_and_cp_material_framing():
    warnings = voice_warnings(
        ["The outpost loses about 2 pawns.", "Use the idea next time."]
    )
    assert any("outpost" in warning for warning in warnings)
    assert any("Centipawn loss" in warning for warning in warnings)


def test_eligible_reason_rejects_non_teaching_voice():
    payload = eligible_payload()
    payload["better_move_fact"] = "The outpost loses about 2 pawns."
    payload["played_move_fact"] = "The move does not improve the position."
    payload["contrast"] = "The alternative is better."
    payload["transferable_lesson"] = "Improve your position next time."
    with pytest.raises(PositionalReasonValidationError, match="outpost"):
        normalize_submission(payload, ROW, submitted_by="admin")


def test_eligible_reason_requires_plain_language_headline_even_when_mapped():
    payload = eligible_payload()
    payload["concept_label"] = ""
    payload["canonical_concept_id"] = "END_KING_ACTIVE"
    with pytest.raises(PositionalReasonValidationError, match="plain-language"):
        normalize_submission(payload, ROW, submitted_by="admin")
