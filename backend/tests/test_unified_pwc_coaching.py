import chess
import pytest

from services import fast_eval_service
from services import unified_pwc_coaching as unified
from services.unified_pwc_coaching import (
    MAX_CRITICAL_PER_SESSION,
    UNIFIED_DECISION_SOURCE,
    answer_unified_help,
    attach_unified_postgame_to_end_result,
    build_unified_postgame_summary,
    engine_evidence_for_player,
    evaluate_unified_pending,
    select_unified_decision,
)


BASE_EVAL = {
    "eval_before": 0.2,
    "eval_after": -4.0,
    "cp_loss": 420,
}
VERIFIED = {
    "verified": True,
    "caption": "Qh5 leaves your queen open to Nxh5. Check every reply before you commit.",
    "instruction": "Check every reply before you commit.",
    "category": "piece_safety",
    "concept_key": "TAC_HANGING_PIECE",
    "has_teaching_content": True,
    "rule_name": "R12_BLUNDER",
}


def _select(**overrides):
    values = {
        "game_mode": "coach",
        "eval_result": BASE_EVAL,
        "eval_valid": True,
        "caption": VERIFIED,
        "coaching_decisions": [],
        "user_color": "white",
        "user_rating": 1200,
        "coaching_context": {
            "primary_focus": {"topic_key": "piece_safety"},
        },
    }
    values.update(overrides)
    return select_unified_decision(**values)


def test_play_mode_is_silent_even_with_verified_blunder():
    assert _select(game_mode="play")["layer"] == "silent"


def test_unverified_caption_can_never_interrupt():
    assert _select(caption={**VERIFIED, "verified": False})["layer"] == "silent"


def test_engine_failure_can_never_interrupt():
    assert _select(eval_valid=False)["layer"] == "silent"


def test_verified_but_hollow_caption_stays_silent():
    hollow = {
        **VERIFIED,
        "caption": "You played Qh5; Qd2 was stronger.",
        "instruction": "",
        "has_teaching_content": False,
    }
    assert _select(caption=hollow)["layer"] == "silent"


def test_verified_rating_aware_blunder_gets_explicit_hold():
    result = _select()
    assert result["layer"] == "critical_interrupt"
    assert result["requires_hold"] is True
    assert result["focus_match"] is True
    assert result["proof"]["caption_verified"] is True


def test_critical_interventions_stop_after_inherited_session_cap():
    previous = [
        {"source": UNIFIED_DECISION_SOURCE, "layer": "critical_interrupt"}
        for _ in range(MAX_CRITICAL_PER_SESSION)
    ]
    result = _select(coaching_decisions=previous)
    assert result["layer"] == "advisory"
    assert result["requires_hold"] is False


def test_noncritical_cadence_is_at_most_two_in_recent_six():
    previous = [
        {"source": UNIFIED_DECISION_SOURCE, "layer": "advisory"},
        {"source": UNIFIED_DECISION_SOURCE, "layer": "silent"},
        {"source": UNIFIED_DECISION_SOURCE, "layer": "advisory"},
    ]
    mild_eval = {"eval_before": 0.2, "eval_after": -1.1, "cp_loss": 130}
    result = _select(eval_result=mild_eval, coaching_decisions=previous)
    assert result["layer"] == "silent"


@pytest.mark.asyncio
async def test_live_evaluation_carries_private_engine_evidence_for_persistence(
    monkeypatch,
):
    monkeypatch.setattr(
        fast_eval_service,
        "fast_eval",
        lambda *_args: {
            **BASE_EVAL,
            "best_move": "d2d4",
            "depth": 12,
        },
    )
    monkeypatch.setattr(unified, "build_verified_caption", lambda **_kwargs: VERIFIED)

    result = await evaluate_unified_pending(
        session_doc={
            "game_mode": "coach",
            "current_fen": chess.STARTING_FEN,
            "user_color": "white",
            "user_rating": 1200,
            "move_history": [],
            "coaching_decisions": [],
            "coaching_context": {
                "primary_focus": {"topic_key": "piece_safety"},
            },
        },
        fen_before=chess.STARTING_FEN,
        uci="e2e4",
        user_rating=1200,
    )

    assert result["_engineEvidence"] == {
        "eval_valid": True,
        "move_quality": "blunder",
        "cp_loss": 420,
        "best_move": "d2d4",
        "eval_before": 0.2,
        "eval_after": -4.0,
    }
    assert result["coachingDecision"]["layer"] == "critical_interrupt"


@pytest.mark.asyncio
async def test_focus_help_reuses_the_canonical_instruction():
    result = await answer_unified_help(
        session_doc={
            "coaching_context": {
                "primary_focus": {
                    "instruction_text": "Before moving, check what becomes loose.",
                },
            },
        },
        action="focus_check",
    )
    assert result["answer"] == "Before moving, check what becomes loose."
    assert result["source"] == "canonical_focus"
    assert result["proof"]["context_verified"] is True


@pytest.mark.asyncio
async def test_explain_last_move_abstains_when_there_is_no_verified_move():
    result = await answer_unified_help(
        session_doc={"move_history": [], "coaching_context": {}},
        action="explain_last_move",
    )
    assert result["proof"] == {
        "caption_verified": False,
        "abstained": True,
    }
    assert "won’t guess" in result["answer"]


@pytest.mark.asyncio
async def test_explain_last_move_uses_the_verified_caption_pipeline(monkeypatch):
    board = chess.Board()
    board.push_san("e4")
    before_e5 = board.fen()
    board.push_san("e5")
    captured = {}

    monkeypatch.setattr(
        fast_eval_service,
        "fast_eval",
        lambda *_args: {**BASE_EVAL, "best_move": "e7e5", "depth": 10},
    )

    def verified_caption(**kwargs):
        captured.update(kwargs)
        return VERIFIED

    monkeypatch.setattr(unified, "build_verified_caption", verified_caption)
    result = await answer_unified_help(
        session_doc={
            "user_color": "white",
            "user_rating": 1200,
            "coaching_context": {},
            "move_history": [
                {"by": "player", "move": "e4"},
                {
                    "by": "coach",
                    "move": "e5",
                    "uci": "e7e5",
                    "fen_before": before_e5,
                },
            ],
        },
        action="explain_last_move",
    )
    assert captured["mover_is_user"] is False
    assert result["answer"] == VERIFIED["caption"]
    assert result["proof"]["caption_verified"] is True


@pytest.mark.asyncio
async def test_unknown_help_action_is_rejected():
    with pytest.raises(ValueError, match="unknown coach help action"):
        await answer_unified_help(session_doc={}, action="tell_me_everything")


def test_black_engine_evidence_is_normalized_to_player_perspective():
    result = engine_evidence_for_player(
        {"eval_before": 1.5, "eval_after": 3.0, "cp_loss": 150},
        "black",
    )
    assert result == {
        "eval_before": -1.5,
        "eval_after": -3.0,
        "cp_loss": 150,
    }


def test_unified_postgame_uses_verified_focus_moment_and_canonical_action():
    result = build_unified_postgame_summary(
        session_doc={
            "game_mode": "coach",
            "coaching_context": {
                "primary_focus": {
                    "topic_key": "piece_safety",
                    "label": "Piece safety",
                    "instruction_text": "Before moving, check what becomes loose.",
                },
                "next_action": {
                    "label": "Practise this check",
                    "href": "/training/pattern/piece_safety",
                },
            },
            "coaching_decisions": [
                {
                    "source": UNIFIED_DECISION_SOURCE,
                    "layer": "critical_interrupt",
                    "category": "piece_safety",
                    "caption_verified": True,
                    "text": "Moving the bishop leaves your knight on e5 undefended.",
                    "cp_loss": 320,
                    "move_index": 12,
                },
                {
                    "source": "legacy",
                    "layer": "critical_interrupt",
                    "caption_verified": True,
                    "text": "This must not enter the story.",
                    "cp_loss": 900,
                },
            ],
            "guardian_overrides": [{"move": "Bg5"}],
        },
    )
    assert result["story"] == "We found 1 clear moment where today's focus mattered."
    assert result["detail"].startswith("Moving the bishop")
    assert result["next_action"]["href"] == "/training/pattern/piece_safety"
    assert result["evidence"] == {
        "verified_moments": 1,
        "focus_moments": 1,
        "warnings_overridden": 1,
    }


def test_unified_postgame_never_calls_no_observation_improvement():
    result = build_unified_postgame_summary(
        session_doc={
            "game_mode": "coach",
            "coaching_context": {
                "primary_focus": {
                    "topic_key": "piece_safety",
                    "label": "Piece safety",
                },
            },
            "coaching_decisions": [],
        },
    )
    assert result["story"] == (
        "I did not see a clear moment to measure this focus in this game, "
        "so I am not claiming you have fixed it yet."
    )
    assert result["turning_point"] is None


def test_unified_play_postgame_promises_review_without_claiming_progress():
    result = build_unified_postgame_summary(
        session_doc={"game_mode": "play"},
    )
    assert result["story"] == "The game is complete. Your review is ready."
    assert result["next_action"] == {"label": "Review the game", "href": "/lab"}


def test_unified_resign_response_carries_personal_focus_into_nested_summary():
    result = {"success": True, "summary": {"move_count": 1}}
    returned = attach_unified_postgame_to_end_result(
        result=result,
        session_doc={
            "experience_version": "unified_v1",
            "game_mode": "coach",
            "coaching_context": {
                "primary_focus": {
                    "topic_key": "piece_safety",
                    "label": "Keep the piece you move safe",
                    "instruction_text": (
                        "Before you move a piece, check whether it can be "
                        "captured on its new square."
                    ),
                },
                "next_action": {
                    "label": "Practise this check",
                    "href": "/training/pattern/piece_safety",
                },
            },
            "coaching_decisions": [],
        },
    )

    assert returned is result
    assert returned["summary"]["move_count"] == 1
    unified_summary = returned["summary"]["unified_summary"]
    assert unified_summary["focus_label"] == "Keep the piece you move safe"
    assert unified_summary["next_action"]["href"] == "/training/pattern/piece_safety"


def test_legacy_end_response_is_unchanged_by_unified_projection():
    result = {"success": True, "summary": {"move_count": 1}}
    original_summary = result["summary"]

    returned = attach_unified_postgame_to_end_result(
        result=result,
        session_doc={"experience_version": "legacy"},
    )

    assert returned is result
    assert returned["summary"] is original_summary
    assert "unified_summary" not in returned["summary"]
