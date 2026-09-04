import json
from pathlib import Path

from services.caption_facts import (
    HIDDEN_OPPORTUNITY_COMPOSER_VERSION,
    build_verified_hidden_opportunity,
)


BACKEND = Path(__file__).resolve().parents[1]
PACKET = BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_chess_gold_v1_2026-09-02.json"
)
ANNOTATIONS = BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_chess_gold_annotations_v1_2026-09-03.json"
)
TARGET_REPORT = BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_phase3a7_target_line_validation_v6_2026-09-04.json"
)
FORCING_REPORT = BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_phase3a7_forcing_tempo_validation_v3_2026-09-04.json"
)
ENDGAME_REPORT = BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_phase3a2_endgame_geometry_validation_v2_2026-09-03.json"
)
TRANSFORMATION_REPORT = BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_phase3a2_board_transformation_validation_v1_2026-09-03.json"
)


def _arguments(row):
    return {
        "fen_before": row["fen"],
        "played_san": row["played_move"]["san"],
        "best_move_san": row["best_move"]["san"],
        "pv_after_played": row["stored_four_ply"]["after_played"],
        "pv_after_best": row["stored_four_ply"]["after_best"],
        "cp_loss": row["cp_loss"],
    }


def _expected_owner_ids():
    target = json.loads(TARGET_REPORT.read_text(encoding="utf-8"))
    forcing = json.loads(FORCING_REPORT.read_text(encoding="utf-8"))
    endgame = json.loads(ENDGAME_REPORT.read_text(encoding="utf-8"))
    transformation = json.loads(
        TRANSFORMATION_REPORT.read_text(encoding="utf-8")
    )
    return (
        set(target["proof_position_ids"])
        | set(forcing["new_forcing_proof_position_ids"])
        | set(endgame["proof_position_ids"])
        | set(transformation["proof_position_ids"])
    )


def test_composer_version_is_explicit():
    assert HIDDEN_OPPORTUNITY_COMPOSER_VERSION == (
        "hidden_opportunity_composer.v1"
    )


def test_composer_matches_every_locked_proof_owner_exactly():
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    actual = {
        row["position_id"]
        for row in packet["positions"]
        if build_verified_hidden_opportunity(**_arguments(row)) is not None
    }

    assert actual == _expected_owner_ids()


def test_composer_never_claims_a_locked_non_opportunity():
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    annotations = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    surface_by_id = {
        row["position_id"]: row["surface_grade"]
        for row in annotations["annotations"]
    }

    for row in packet["positions"]:
        proof = build_verified_hidden_opportunity(**_arguments(row))
        if proof is not None:
            assert surface_by_id[row["position_id"]] == "hidden_opportunity"


def test_composer_is_deterministic_and_keeps_proof_fingerprint():
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    row = next(
        item
        for item in packet["positions"]
        if item["position_id"] in _expected_owner_ids()
    )

    first = build_verified_hidden_opportunity(**_arguments(row))
    second = build_verified_hidden_opportunity(**_arguments(row))

    assert first is not None
    assert second is not None
    assert first.contract_dict() == second.contract_dict()
    assert first.fingerprint == second.fingerprint


def test_composer_does_not_chase_two_overstated_gold_notes():
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    # Both notes describe a queen win, but their stored lines contain an
    # immediate queen recapture or equal queen exchange. They need a distinct
    # defensive-resource proof, not a relaxed material-payoff verifier.
    disputed_ids = {
        "00906363fd88603401ce",
        "001d12f6e8e923e5d08d",
    }
    rows = {
        row["position_id"]: row
        for row in packet["positions"]
        if row["position_id"] in disputed_ids
    }

    assert set(rows) == disputed_ids
    assert all(
        build_verified_hidden_opportunity(**_arguments(row)) is None
        for row in rows.values()
    )
