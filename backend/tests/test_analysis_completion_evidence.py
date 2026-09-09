from datetime import datetime, timezone

from services.analysis_completion_evidence import (
    _prepare,
    effective_pwc_evidence_mode,
    external_game_context,
    pwc_game_context,
)
from services.personal_curriculum import (
    AssistanceKind,
    EvidenceSourceType,
    LessonResult,
)


HANG_FEN = "4k3/8/4p2p/8/8/5N2/8/4K3 w - - 0 1"


def _analysis(cp_loss=200):
    return {
        "created_at": datetime(2026, 9, 9, tzinfo=timezone.utc),
        "stockfish_analysis": {
            "move_evaluations": [{
                "fen_before": HANG_FEN,
                "move_uci": "f3g5",
                "move_number": 1,
                "move": "Ng5",
                "cp_loss": cp_loss,
                "evaluation": "mistake" if cp_loss >= 150 else "good",
                "cognitive_gap": "piece_safety" if cp_loss >= 150 else None,
            }],
        },
    }


def _game():
    return {
        "game_id": "coach-session-1",
        "user_id": "user-1",
        "user_color": "white",
        "date_played": datetime(2026, 9, 9, tzinfo=timezone.utc),
    }


def _session(mode):
    return {
        "game_mode": "coach" if mode == "practice_assisted" else "play",
        "evidence_mode": mode,
        "coaching_context": {
            "primary_focus": {
                "focus_id": "focus-1",
                "instruction_id": "instruction-1",
                "detector_quality_id": (
                    "gap:piece_safety:destination_safety_exact"
                ),
            },
        },
    }


def _lesson_result(prepared):
    payload = prepared["events"][0]["lesson_result"]
    return LessonResult.from_event_dict(payload)


def test_pwc_modes_fail_closed_without_a_verified_focus():
    assert effective_pwc_evidence_mode(
        "checkpoint_unassisted",
        game_mode="play",
        has_verified_focus=False,
    ) == "just_play"
    assert effective_pwc_evidence_mode(
        "practice_assisted",
        game_mode="play",
        has_verified_focus=True,
    ) == "just_play"
    assert effective_pwc_evidence_mode(
        "practice_assisted",
        game_mode="coach",
        has_verified_focus=False,
    ) == "practice_assisted"
    assert effective_pwc_evidence_mode(
        "checkpoint_unassisted",
        game_mode="play",
        has_verified_focus=True,
    ) == "checkpoint_unassisted"


def test_assisted_pwc_application_preserves_help_and_cannot_claim_game_use(
    monkeypatch,
):
    monkeypatch.setattr(
        "services.analysis_completion_evidence.complete_coaching_system_enabled",
        lambda: True,
    )
    context = pwc_game_context(_session("practice_assisted"))
    prepared = _prepare(
        user_id="user-1",
        game=_game(),
        analysis=_analysis(),
        context=context,
    )
    result = _lesson_result(prepared)

    assert result.source_type == EvidenceSourceType.COACHED_APPLICATION
    assert result.assistance == (AssistanceKind.GUIDED_LINE,)
    assert result.assistance_measured is True
    assert result.earned_state() is None
    assert prepared["events"][0]["origin"] == (
        "pwc_practice_assisted_observation"
    )


def test_silent_checkpoint_is_recorded_separately_from_organic_transfer(
    monkeypatch,
):
    monkeypatch.setattr(
        "services.analysis_completion_evidence.complete_coaching_system_enabled",
        lambda: True,
    )
    context = pwc_game_context(_session("checkpoint_unassisted"))
    prepared = _prepare(
        user_id="user-1",
        game=_game(),
        analysis=_analysis(),
        context=context,
    )
    result = _lesson_result(prepared)

    assert context.evidence_mode == "checkpoint_unassisted"
    assert result.source_type == EvidenceSourceType.COACHED_APPLICATION
    assert result.assistance == ()
    assert result.earned_state() is None
    assert prepared["events"][0]["origin"] == (
        "pwc_checkpoint_unassisted_observation"
    )


def test_external_completion_keeps_existing_organic_event_identity(monkeypatch):
    monkeypatch.setattr(
        "services.analysis_completion_evidence.complete_coaching_system_enabled",
        lambda: True,
    )
    prepared = _prepare(
        user_id="user-1",
        game=_game(),
        analysis=_analysis(),
        context=external_game_context(),
    )
    result = _lesson_result(prepared)

    assert result.source_type == EvidenceSourceType.ORGANIC_GAME
    assert result.source_event_id == "move_observation:coach-session-1:2"
    assert prepared["events"][0]["origin"] == "external_game_observation"


def test_no_comparable_decision_creates_no_application_event(monkeypatch):
    monkeypatch.setattr(
        "services.analysis_completion_evidence.complete_coaching_system_enabled",
        lambda: True,
    )
    prepared = _prepare(
        user_id="user-1",
        game=_game(),
        analysis={
            "stockfish_analysis": {
                "move_evaluations": [{
                    "fen_before": (
                        "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"
                    ),
                    "move_uci": "e2e4",
                    "move_number": 1,
                    "move": "e4",
                    "cp_loss": 0,
                    "evaluation": "good",
                    "cognitive_gap": None,
                }],
            },
        },
        context=external_game_context(),
    )

    assert len(prepared["observations"]) == 1
    assert prepared["events"] == []
