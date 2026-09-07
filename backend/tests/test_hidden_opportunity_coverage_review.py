import json

from scripts.build_hidden_opportunity_coverage_review import (
    DEFAULT_OUTPUT_PATH,
    SCHEMA_VERSION,
    build_packet,
)


def test_versioned_coverage_packet_matches_builder_exactly():
    expected = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))

    assert build_packet() == expected


def test_coverage_packet_preserves_the_complete_no_candidate_population():
    packet = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))
    coverage = packet["coverage"]

    assert packet["schema_version"] == SCHEMA_VERSION
    assert coverage["games_scanned"] == 80
    assert coverage["meaningful_decisions_scanned"] == 467
    assert coverage["complete_branch_evidence"] == 467
    assert coverage["candidate_fires"] == 14
    assert coverage["games_with_candidate"] == 13
    assert coverage["games_without_candidate"] == 67
    assert coverage["games_without_candidate"] == len(packet["groups"])
    assert coverage["games_with_existing_verified_line_cause"] == 64
    assert (
        coverage["no_candidate_games_with_existing_verified_line_cause"]
        == 52
    )
    assert coverage["games_without_opportunity_or_verified_line_cause"] == 15
    assert (
        coverage["decisions_without_opportunity_or_verified_line_cause"]
        == 38
    )
    assert coverage["decisions_in_no_candidate_games"] == sum(
        len(group["decisions"]) for group in packet["groups"]
    )
    assert sum(
        packet["evidence_topology"]["all_meaningful_decisions"].values()
    ) == 467
    assert sum(
        packet["evidence_topology"]["no_candidate_games"].values()
    ) == coverage["decisions_in_no_candidate_games"]
    assert sum(
        packet["evidence_topology"][
            "games_without_either_exact_cause"
        ].values()
    ) == coverage[
        "decisions_without_opportunity_or_verified_line_cause"
    ]


def test_coverage_review_is_blinded_private_and_answerless():
    packet = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))
    encoded_groups = json.dumps(packet["groups"]).lower()

    assert packet["blinding"] == {
        "cp_loss_hidden": True,
        "critical_flags_hidden": True,
        "stored_labels_hidden": True,
        "existing_captions_hidden": True,
        "proof_family_hidden": True,
        "mechanism_name_hidden": True,
        "composer_rejection_reason_hidden": True,
    }
    assert packet["answer_key_status"] == (
        "not_created_until_review_is_frozen"
    )
    for forbidden in (
        "email",
        "user_id",
        "game_id",
        "username",
        "cp_loss",
        "quality_id",
        "proof_version",
        "mechanism",
        "cognitive_gap",
        "current_review",
    ):
        assert forbidden not in encoded_groups


def test_coverage_review_responses_start_empty_and_ids_are_unique():
    packet = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))
    ids = []
    for group in packet["groups"]:
        assert group["reviewer_response"] == {
            "game_has_hidden_opportunity": None,
            "best_decision_ids": [],
            "rejected_decision_ids": [],
            "notes": "",
        }
        for decision in group["decisions"]:
            ids.append(decision["decision_id"])
            assert decision["reviewer_response"] == {
                "surface_grade": None,
                "idea_family": None,
                "evidence_horizon_sufficient": None,
                "reason": "",
            }

    assert len(ids) == len(set(ids))


def test_coverage_review_has_no_external_or_runtime_side_effects():
    packet = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))

    assert packet["read_only"] is True
    assert packet["stockfish_runs"] == 0
    assert packet["llm_calls"] == 0
    assert packet["database_reads"] == 0
    assert packet["database_writes"] == 0
    assert len(packet["source"]["sha256"]) == 64
