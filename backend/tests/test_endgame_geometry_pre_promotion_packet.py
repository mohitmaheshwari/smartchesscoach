import json

from scripts.build_endgame_geometry_pre_promotion_packet import (
    DEFAULT_OUTPUT_PATH,
    build_packet,
)
from services.caption_facts import ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID
from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    get_authorization,
    is_authorized,
)


def _versioned_packet():
    return json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))


def test_versioned_endgame_packet_is_deterministic():
    assert build_packet() == _versioned_packet()


def test_endgame_packet_is_blinded_and_identity_free():
    packet = _versioned_packet()
    encoded_cases = json.dumps(packet["cases"]).lower()

    assert packet["review_packet"]["blinded"] is True
    assert packet["review_packet"]["cases"] == 31
    assert len(packet["cases"]) == 31
    assert len({case["case_id"] for case in packet["cases"]}) == 31
    assert "@" not in encoded_cases
    for forbidden in (
        "email",
        "user_id",
        "game_id",
        "cp_loss",
        "candidate_fired",
        "mechanism",
        "proof",
        "gold",
    ):
        assert forbidden not in encoded_cases


def test_endgame_packet_records_actual_shortfall_and_stays_shadow():
    packet = _versioned_packet()

    assert packet["quality_id"] == ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID
    assert packet["population"]["cases_scanned"] == 567
    assert packet["population"]["complete_branch_evidence"] == 563
    assert packet["population"]["architecture_overlap_excluded"] == 3
    assert packet["population"]["candidate_fires"] == 1
    assert packet["population"]["candidate_fire_source_units"] == 1
    assert packet["population"]["positive_edge_near_controls"] == 242
    assert packet["population"]["mechanisms"] == {
        "immediate_pawn_push_promotes": 1,
    }
    assert packet["review_packet"]["candidate_fires_hidden"] == 1
    assert packet["review_packet"]["controls_hidden"] == 30
    assert packet["promotion_gate"]["fire_shortfall"] == 49
    assert packet["promotion_gate"]["caption_promotion_gate_passed"] is False

    authorization = get_authorization(ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID)
    assert authorization.grade == QualityGrade.SHADOW
    assert is_authorized(
        ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID, QualitySurface.DIAGNOSTIC
    )
    assert not is_authorized(
        ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID, QualitySurface.CAPTION
    )


def test_endgame_packet_has_no_runtime_or_external_compute_side_effects():
    packet = _versioned_packet()

    assert packet["read_only"] is True
    assert packet["stockfish_runs"] == 0
    assert packet["llm_calls"] == 0
    assert packet["database_reads"] == 0
    assert packet["database_writes"] == 0
    assert all(len(source["sha256"]) == 64 for source in packet["sources"])
