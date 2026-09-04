import json

from scripts.build_hidden_opportunity_moment_ranking_review import (
    DEFAULT_OUTPUT_PATH,
    SCHEMA_VERSION,
    build_packet,
)


def test_versioned_ranking_packet_matches_builder_exactly():
    expected = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))

    assert build_packet() == expected


def test_ranking_packet_is_blinded_private_and_comparable():
    packet = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))
    encoded_groups = json.dumps(packet["groups"]).lower()

    assert packet["schema_version"] == SCHEMA_VERSION
    assert packet["blinding"] == {
        "formula_ids_hidden": True,
        "formula_scores_hidden": True,
        "cp_loss_hidden": True,
        "critical_flags_hidden": True,
        "proof_family_hidden": True,
        "mechanism_name_hidden": True,
    }
    assert packet["coverage"]["comparable_games"] == len(packet["groups"])
    assert all(len(group["candidates"]) >= 2 for group in packet["groups"])
    assert "cp_loss" not in encoded_groups
    assert "quality_id" not in encoded_groups
    assert "proof_version" not in encoded_groups
    assert "mechanism" not in encoded_groups
    assert "email" not in encoded_groups
    assert "user_id" not in encoded_groups
    assert "game_id" not in encoded_groups
    assert "username" not in encoded_groups


def test_ranking_packet_has_no_runtime_or_external_compute_side_effects():
    packet = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))

    assert packet["read_only"] is True
    assert packet["stockfish_runs"] == 0
    assert packet["llm_calls"] == 0
    assert packet["database_reads"] == 0
    assert packet["database_writes"] == 0
    assert len(packet["source"]["sha256"]) == 64


def test_candidate_ids_are_unique_and_review_responses_start_empty():
    packet = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))
    candidate_ids = [
        candidate["candidate_id"]
        for group in packet["groups"]
        for candidate in group["candidates"]
    ]

    assert len(candidate_ids) == len(set(candidate_ids))
    for group in packet["groups"]:
        assert group["reviewer_response"] == {
            "show_any": None,
            "ranked_candidate_ids": [],
            "rejected_candidate_ids": [],
            "top_choice_reason": None,
            "notes": "",
        }
