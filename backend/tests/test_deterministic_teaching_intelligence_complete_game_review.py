import hashlib
import json
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
PACKET = (
    BACKEND
    / "data/detector_gold/deterministic_teaching_intelligence_development_packet_v1.json"
)
REVIEW = (
    BACKEND
    / "data/detector_gold/deterministic_teaching_intelligence_codex_complete_game_review_v1.json"
)
BASELINE = (
    BACKEND
    / "data/detector_gold/deterministic_teaching_intelligence_system_baseline_v1.json"
)
COVERAGE = (
    BACKEND
    / "data/detector_gold/deterministic_teaching_intelligence_current_coverage_adjudication_v1.json"
)
WORKSHEET = (
    BACKEND
    / "data/detector_gold/deterministic_teaching_intelligence_codex_worksheet_v1.json"
)
CENSUS = (
    BACKEND
    / "data/corpus_snapshots/deterministic_teaching_intelligence_census_v1_2026-09-13.json"
)
OPPORTUNITY_REPORT = (
    BACKEND
    / "data/corpus_snapshots/deterministic_teaching_intelligence_opportunity_report_v1_2026-09-14.json"
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_review_is_frozen_against_the_exact_blind_packet():
    packet = _load(PACKET)
    review = _load(REVIEW)

    assert review["status"] == "frozen_development_review"
    assert review["source_packet_sha256"] == _sha256(PACKET)
    assert review["source_membership_sha256"] == packet["membership_sha256"]
    assert review["review_protocol"] == {
        "reviewed_games": 100,
        "blind_to_current_chessguru_output": True,
        "complete_game_context_reviewed": True,
        "stockfish_runs": 0,
        "model_calls": 0,
        "holdout_opened": False,
        "player_facing_authorization": False,
        "meaning": (
            "A Codex chess-reasoning inventory of the teaching stories that a "
            "strong deterministic reviewer should be able to prove. Candidate "
            "families are research targets, not publishable chess claims."
        ),
    }


def test_review_accounts_for_every_game_once_in_packet_order():
    packet = _load(PACKET)
    review = _load(REVIEW)
    rows = review["game_reviews"]

    assert [row["review_index"] for row in rows] == list(range(1, 101))
    assert [row["anonymous_game_key"] for row in rows] == [
        game["anonymous_game_key"] for game in packet["games"]
    ]
    assert len({row["anonymous_game_key"] for row in rows}) == 100


def test_every_candidate_ply_and_family_is_bound_to_available_evidence():
    packet = _load(PACKET)
    review = _load(REVIEW)
    families = set(review["proposed_family_definitions"])
    allowed_statuses = set(review["evidence_statuses"])
    games = {
        game["anonymous_game_key"]: game
        for game in packet["games"]
    }

    for row in review["game_reviews"]:
        game = games[row["anonymous_game_key"]]
        available_plies = {move["ply"] for move in game["moves"]}
        assert set(row["candidate_plies"]) <= available_plies
        assert set(row["required_families"]) <= families
        if row["disposition"] == "honest_no_strong_lesson":
            assert row["candidate_plies"] == []
            assert row["required_families"] == []
            assert "evidence_status" not in row
        else:
            assert row["candidate_plies"] or row["required_families"]
            assert row["evidence_status"] in allowed_statuses


def test_review_contains_no_identity_or_player_facing_authorization():
    review_text = REVIEW.read_text(encoding="utf-8-sig").lower()
    review = _load(REVIEW)

    for forbidden in (
        '"email"',
        '"user_id"',
        '"game_id"',
        '"username"',
        '"player_key"',
        '"pgn"',
        '"date_played"',
    ):
        assert forbidden not in review_text
    assert review["review_protocol"]["holdout_opened"] is False
    assert review["review_protocol"]["player_facing_authorization"] is False


def test_every_frozen_evidence_artifact_excludes_identity_and_credentials():
    artifacts = (
        PACKET,
        REVIEW,
        BASELINE,
        COVERAGE,
        WORKSHEET,
        CENSUS,
        OPPORTUNITY_REPORT,
    )
    forbidden_keys = (
        "\"email\"",
        "\"user_id\"",
        "\"game_id\"",
        "\"username\"",
        "\"player_key\"",
        "\"pgn\"",
        "\"date_played\"",
        "\"url\"",
        "\"credential\"",
        "\"password\"",
        "\"token\"",
    )

    for artifact in artifacts:
        text = artifact.read_text(encoding="utf-8-sig").lower()
        for forbidden in forbidden_keys:
            assert forbidden not in text, f"{forbidden} leaked into {artifact.name}"


def test_review_demands_more_than_error_only_material_captions():
    review = _load(REVIEW)
    rows = review["game_reviews"]
    required = {
        family
        for row in rows
        for family in row["required_families"]
    }

    assert "clean_or_positive_play" in required
    assert "unpunished_opponent_opportunity" in required
    assert "opening_purpose" in required
    assert "exact_endgame" in required
    assert "forced_mate_story" in required
    assert "multi_move_material_accounting" in required
    assert len(required) >= 15


def test_post_review_coverage_is_bound_and_partitions_only_reviewed_families():
    review = _load(REVIEW)
    coverage = _load(COVERAGE)
    rows = {row["review_index"]: row for row in review["game_reviews"]}

    assert coverage["status"] == "frozen_after_blind_review"
    assert coverage["source_review_sha256"] == _sha256(REVIEW)
    assert coverage["source_system_baseline_sha256"] == _sha256(BASELINE)
    assert coverage["comparison_contract"][
        "same_move_different_reason_counts"
    ] is False
    assert coverage["comparison_contract"][
        "default_for_unlisted_family_occurrence"
    ] == "uncovered"
    assert coverage["comparison_contract"]["holdout_opened"] is False

    seen = set()
    for item in coverage["covered_family_occurrences"]:
        identity = (item["review_index"], item["family"])
        assert identity not in seen
        seen.add(identity)
        source = rows[item["review_index"]]
        assert item["family"] in source["required_families"]
        assert set(item["supporting_plies"]) <= set(source["candidate_plies"])
        assert item["reason"].strip()


def test_system_baseline_is_stored_read_only_output_not_recomposition():
    baseline = _load(BASELINE)

    assert len(baseline["games"]) == 100
    assert baseline["blinded"] is False
    assert baseline["database_writes"] == 0
    assert baseline["stockfish_runs"] == 0
    assert baseline["model_calls"] == 0
    assert baseline["system_recomposition"] == {
        "performed": False,
        "source": "stored production output",
        "persist_learning_side_effects": False,
        "allow_llm_polish": False,
        "stockfish_runs": 0,
        "model_calls": 0,
        "database_writes": 0,
    }
