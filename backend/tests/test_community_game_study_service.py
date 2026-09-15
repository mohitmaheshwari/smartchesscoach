from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from services.caption_facts import LegalMaterialLossCause, PieceOnSquare
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


def _personalized_typed_source_event(chapter=None):
    event = _source_event(chapter)
    cause = LegalMaterialLossCause(
        affected=PieceOnSquare(piece="rook", square="d2"),
        attacker=PieceOnSquare(piece="queen", square="c2"),
        punishment_san="Qxd2",
        material_loss_cp=500,
        best_move_san="Rd1",
        best_move_purpose="moves_affected_piece",
        best_move_from="d3",
        best_move_to="d1",
        avoidable_with_san="Rd1",
    )
    event["teaching"] = {
        "headline": "You left one piece behind",
        "caption": "You left your rook on d2 available to their queen.",
        "principle": "Before moving, check what their next capture wins.",
        "cause_fingerprint": cause.fingerprint,
    }
    event["cause"] = cause.contract_dict()
    return event


def _personalized_verified_line_event(chapter=None):
    event = _source_event(chapter)
    cause = {
        "schema_version": "verified_line_cause.v1",
        "kind": "verified_stored_line",
        "lesson_kind": "missed_material_opportunity",
        "phase": "middlegame",
        "position_kind": "general",
        "played_move_san": "Rab8",
        "best_move_san": "Rfb8",
        "best_move_from": "f8",
        "best_move_to": "b8",
        "played_line_san": ["Rab8", "Qg3"],
        "best_line_san": ["Rfb8", "Qg3", "Rxb2"],
        "played_captures": [],
        "best_captures": [
            {
                "ply": 3,
                "actor": "initiator",
                "move_san": "Rxb2",
                "origin": "b8",
                "destination": "b2",
                "capturing_piece": "rook",
                "captured_piece": "pawn",
                "captured_square": "b2",
                "captured_value_cp": 100,
            }
        ],
        "played_net_material_gain_cp": 0,
        "best_net_material_gain_cp": 100,
        "played_purposes": [],
        "mate_in": None,
        "reply_san": None,
        "reply_from": None,
        "reply_to": None,
        "relationships": [],
        "proof": {
            "authority": "stored_line_verifier.replay_stored_line",
            "version": "verified_line_cause.v1",
        },
    }
    fingerprint = hashlib.sha256(
        json.dumps(cause, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    cause["fingerprint"] = fingerprint
    event["move"]["san"] = "Rab8"
    event["teaching"] = {
        "headline": "You missed a material win",
        "caption": "You could have won material here.",
        "principle": "Look for forcing moves.",
        "cause_fingerprint": fingerprint,
    }
    event["cause"] = cause
    return event


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
    with pytest.raises(
        service.CommunityGameStudyError,
        match="personalized without a typed cause",
    ):
        service.project_neutral_chapter(personalized, chapter)

    mismatched = _source_event(chapter)
    mismatched["concept"]["id"] = "piece_safety.simple_hang"
    with pytest.raises(service.CommunityGameStudyError, match="concept does not match"):
        service.project_neutral_chapter(mismatched, chapter)


def test_neutral_projection_renders_real_personalized_event_from_typed_cause():
    chapter = _chapter("event-1")
    projected = service.project_neutral_chapter(
        _personalized_typed_source_event(chapter), chapter
    )
    assert projected["headline"] == "The rook on d2 is the key"
    assert projected["explanation"] == (
        "After Rd2, Qxd2 starts an exchange that costs the rook on d2. "
        "Rd1 was the stronger move."
    )
    assert "you" not in " ".join(str(value) for value in projected.values()).lower()


def test_neutral_projection_rejects_cause_or_teaching_fingerprint_drift():
    chapter = _chapter("event-1")
    stale_cause = _personalized_typed_source_event(chapter)
    stale_cause["cause"]["material_loss_cp"] = 300
    with pytest.raises(service.CommunityGameStudyError, match="fingerprint is stale"):
        service.project_neutral_chapter(stale_cause, chapter)

    stale_teaching = _personalized_typed_source_event(chapter)
    stale_teaching["teaching"]["cause_fingerprint"] = _sha("wrong")
    with pytest.raises(service.CommunityGameStudyError, match="not bound"):
        service.project_neutral_chapter(stale_teaching, chapter)


def test_neutral_projection_names_verified_material_target_in_plain_language():
    chapter = _chapter("event-1")
    projected = service.project_neutral_chapter(
        _personalized_verified_line_event(chapter), chapter
    )
    assert projected["headline"] == "The pawn on b2 could be won"
    assert projected["explanation"] == (
        "Rab8 missed the chance. Rfb8 starts the sequence that wins the pawn on b2."
    )
    assert projected["principle"] == (
        "Check captures and follow each reply until the gain is clear."
    )


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
