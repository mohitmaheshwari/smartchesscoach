from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from services import community_game_study_service as service


QUALITY_ID = "gap:piece_safety:destination_safety_exact"
OTHER_CONCEPT_ID = "piece_safety.simple_hang"
OTHER_QUALITY_ID = "gap:piece_safety:simple_hang"


def _sha(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _chapter(
    event_id: str,
    *,
    concept_id: str = "piece_safety.destination_safety_exact",
    quality_id: str = QUALITY_ID,
    phase: str = "middlegame",
):
    return {
        "event_id": event_id,
        "concept_id": concept_id,
        "quality_id": quality_id,
        "phase": phase,
        "move_number": 14,
    }


def _source_event(chapter=None):
    chapter = chapter or _chapter("event-1")
    return {
        "schema_version": "personalized_game_review.v1",
        "event_id": chapter["event_id"],
        "move": {"number": chapter["move_number"], "san": "Rd2"},
        "concept": {"id": chapter["concept_id"]},
        "evidence": {
            "quality_id": chapter["quality_id"],
            "source_version": "stored-proof.v1",
            "provenance": ["stored:analysis"],
            "final_verified": True,
        },
        "display": {
            "requested_surface": "caption",
            "authorized": True,
        },
        "teaching": {
            "headline": "The loose rook decides the position.",
            "caption": "White moves the defender, so Black can take the rook on d2.",
            "principle": "Before moving a defender, check what it leaves behind.",
        },
    }


def _study(
    study_id: str = "study-1",
    *,
    band: str = "beginner_low",
    chapters=None,
    status: str = "shadow",
):
    moves = ["e2e4", "e7e5", "g1f3", "b8c6"]
    initial = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    return {
        "schema_version": service.SCHEMA_VERSION,
        "admission_policy_version": service.ADMISSION_POLICY_VERSION,
        "study_id": study_id,
        "game_id": f"game-{study_id}",
        "status": status,
        "source": {
            "provider": service.APPROVED_PROVIDER,
            "license": service.APPROVED_LICENSE,
            "release_id": "lichess-2026-08",
            "source_checksum": _sha("release"),
            "record_key_hash": _sha(study_id),
            "terms_reviewed_at": "2026-09-15",
        },
        "game": {
            "initial_fen": initial,
            "moves_uci": moves,
            "rating_band": band,
            "time_control_category": "rapid",
        },
        "replay": {
            "legal": True,
            "fingerprint": service.replay_fingerprint(initial, moves),
        },
        "plan": {
            "plan_id": f"plan-{study_id}",
            "input_fingerprint": _sha(f"plan-{study_id}"),
            "safe_projection_version": service.SAFE_PROJECTION_VERSION,
            "chapters": chapters
            or [_chapter(f"{study_id}-1"), _chapter(f"{study_id}-2")],
        },
        "privacy": {
            "identity_state": "anonymous",
            "contains_identity_fields": False,
        },
    }


def test_valid_study_preserves_input_and_requires_canonical_authority():
    study = _study()
    original = deepcopy(study)
    normalized = service.validate_study(study)
    assert normalized["study_id"] == "study-1"
    assert study == original
    assert len(normalized["plan"]["chapters"]) == 2


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda row: row["source"].update(provider="chess_com"),
            "provider is not approved",
        ),
        (
            lambda row: row["source"].update(license="unknown"),
            "license is not approved",
        ),
        (
            lambda row: row["privacy"].update(identity_state="named"),
            "identity_state must be anonymous",
        ),
        (
            lambda row: row["game"].update(rating_band="900-1199"),
            "rating_band is not canonical",
        ),
        (
            lambda row: row["plan"].update(safe_projection_version="stale.v0"),
            "safe_projection_version is not current",
        ),
        (
            lambda row: row.update(username="source-player"),
            "private field is not allowed",
        ),
        (
            lambda row: row["source"].update(note="source@example.com"),
            "private field is not allowed",
        ),
        (
            lambda row: row["source"].update(note="https://example.com/game/123"),
            "private field is not allowed",
        ),
        (
            lambda row: row["plan"]["chapters"][0].update(
                explanation="Copied source-player caption."
            ),
            "unsupported fields",
        ),
        (
            lambda row: row["plan"].update(chapters=[_chapter("only")]),
            "needs two chapters",
        ),
        (
            lambda row: row["plan"]["chapters"][0].update(
                quality_id="review:target_line_causal_proof"
            ),
            "not currently Caption-authorized",
        ),
        (
            lambda row: row["plan"]["chapters"][0].update(
                concept_id="king_safety.escape_square"
            ),
            "concept does not match its evidence",
        ),
    ],
)
def test_admission_fails_closed(mutate, message):
    row = _study()
    mutate(row)
    with pytest.raises(service.CommunityGameStudyError, match=message):
        service.validate_study(row)


def test_replay_is_recomputed_instead_of_trusting_the_stored_boolean():
    row = _study()
    row["game"]["moves_uci"][2] = "a1a8"
    row["replay"]["fingerprint"] = service.replay_fingerprint(
        row["game"]["initial_fen"], row["game"]["moves_uci"]
    )
    with pytest.raises(service.CommunityGameStudyError, match="illegal move"):
        service.validate_study(row)


def test_neutral_projection_resolves_current_event_without_storing_caption_copy():
    chapter = _chapter("event-1")
    projected = service.project_neutral_chapter(_source_event(chapter), chapter)
    assert projected["event_id"] == "event-1"
    assert projected["headline"] == "The loose rook decides the position."
    assert projected["explanation"].startswith("White moves")
    assert "caption" not in chapter


def test_neutral_projection_rejects_personalization_and_reference_drift():
    chapter = _chapter("event-1")
    personalized = _source_event(chapter)
    personalized["teaching"]["caption"] = "You left your rook loose."
    with pytest.raises(service.CommunityGameStudyError, match="personalized"):
        service.project_neutral_chapter(personalized, chapter)

    mismatched = _source_event(chapter)
    mismatched["concept"]["id"] = "piece_safety.simple_hang"
    with pytest.raises(service.CommunityGameStudyError, match="concept does not match"):
        service.project_neutral_chapter(mismatched, chapter)


def test_focus_match_requires_both_canonical_identities():
    row = _study(
        "concept-only",
        chapters=[
            _chapter("x1", quality_id=OTHER_QUALITY_ID),
            _chapter("x2", quality_id=OTHER_QUALITY_ID),
        ],
    )
    candidate = service.candidate_from_study(
        row,
        focus_concept_id="piece_safety.destination_safety_exact",
        focus_quality_id=QUALITY_ID,
        rating_band="beginner_low",
    )
    assert candidate is not None
    assert candidate["focus_match"] is False


def test_balanced_formula_prefers_focus_then_breadth_then_richness():
    other = OTHER_CONCEPT_ID
    studies = [
        _study(
            "rich-no-focus",
            chapters=[
                _chapter("a1", concept_id=other, quality_id=OTHER_QUALITY_ID, phase="opening"),
                _chapter("a2", concept_id=other, quality_id=OTHER_QUALITY_ID, phase="middlegame"),
                _chapter("a3", concept_id=other, quality_id=OTHER_QUALITY_ID, phase="endgame"),
                _chapter("a4", concept_id=other, quality_id=OTHER_QUALITY_ID, phase="endgame"),
            ],
        ),
        _study(
            "focus-narrow",
            chapters=[_chapter("b1"), _chapter("b2")],
        ),
        _study(
            "focus-broad",
            chapters=[
                _chapter("c1", phase="opening"),
                _chapter("c2", phase="middlegame"),
                _chapter("c3", concept_id=other, quality_id=OTHER_QUALITY_ID, phase="endgame"),
            ],
        ),
    ]
    ranked = service.rank_studies(
        studies,
        focus_concept_id="piece_safety.destination_safety_exact",
        focus_quality_id=QUALITY_ID,
        rating_band="beginner_low",
    )
    assert [item["study_id"] for item in ranked] == [
        "focus-broad",
        "focus-narrow",
        "rich-no-focus",
    ]


def test_rating_band_and_terminal_history_fail_closed():
    ranked = service.rank_studies(
        [_study("same"), _study("other-band", band="beginner_high")],
        focus_concept_id="piece_safety.destination_safety_exact",
        focus_quality_id=QUALITY_ID,
        rating_band="beginner_low",
        terminal_study_ids=["same"],
    )
    assert ranked == []


def test_shadow_result_cannot_claim_to_change_visible_selection():
    result = service.shadow_selection(
        [_study()],
        focus_concept_id="piece_safety.destination_safety_exact",
        focus_quality_id=QUALITY_ID,
        rating_band="beginner_low",
    )
    assert result["status"] == "candidate"
    assert result["candidate"]["study_id"] == "study-1"
    assert result["visible_prescription_changed"] is False
    serialized = repr(result)
    for secret in ("game-study-1", "record_key_hash", "source_checksum"):
        assert secret not in serialized


@pytest.mark.asyncio
async def test_database_loader_is_read_only_and_returns_shadow_contract():
    calls = []

    class Cursor:
        async def to_list(self, *, length):
            assert length is None
            return [_study()]

    class Collection:
        def find(self, query, projection):
            calls.append((query, projection))
            return Cursor()

    class Database:
        def __getitem__(self, name):
            assert name == service.COLLECTION
            return Collection()

    db = Database()
    result = await service.load_shadow_selection(
        db,
        focus_concept_id="piece_safety.destination_safety_exact",
        focus_quality_id=QUALITY_ID,
        rating_band="beginner_low",
    )
    assert result["candidate"]["study_id"] == "study-1"
    assert calls == [
        (
            {
                "status": {"$in": ["admitted", "shadow"]},
                "game.rating_band": "beginner_low",
            },
            {"_id": 0},
        )
    ]
