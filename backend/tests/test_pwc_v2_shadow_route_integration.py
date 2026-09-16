from copy import deepcopy
from types import SimpleNamespace

import pytest

import routes.coach_play as coach_play_route
import services.unified_pwc_coaching as unified_coaching

FEN = "4k3/8/8/4N3/8/8/8/4K3 w - - 0 1"


class _CoachSessions:
    def __init__(self, session):
        self.session = session
        self.updates = []

    async def find_one(self, _query, _projection=None):
        return deepcopy(self.session)

    async def update_one(self, query, update):
        self.updates.append((deepcopy(query), deepcopy(update)))
        return SimpleNamespace(modified_count=1)


class _DB:
    def __init__(self, session):
        self.coach_sessions = _CoachSessions(session)


def _session(*, shadow_enabled):
    return {
        "session_id": "session-1",
        "user_id": "user-1",
        "experience_version": "unified_v1",
        "game_mode": "coach",
        "user_color": "white",
        "user_rating": 1200,
        "current_fen": FEN,
        "move_history": [],
        "coaching_decisions": [],
        "pwc_v2_shadow_enabled": shadow_enabled,
    }


def _live_response():
    return {
        "shouldAutoCommit": False,
        "coachingDecision": {
            "source": "pwc_unified_v1",
            "layer": "critical_interrupt",
            "category": "piece_safety",
            "conceptKey": "loose_piece",
            "text": "Your knight on e5 has no defender.",
            "instruction": "Check what the move leaves loose.",
            "focusMatch": True,
            "proof": {
                "caption_verified": True,
                "rule_name": "loose-piece",
            },
        },
        "visual": {"arrows": [], "highlightSquares": ["e5"]},
        "_engineEvidence": {
            "eval_valid": True,
            "move_quality": "blunder",
            "cp_loss": 300,
            "best_move": "e5c4",
            "eval_before": 0.0,
            "eval_after": -3.0,
        },
    }


async def _run_route(monkeypatch, *, shadow_enabled):
    database = _DB(_session(shadow_enabled=shadow_enabled))
    monkeypatch.setattr(coach_play_route, "db", database)

    async def fake_evaluate_unified_pending(**_kwargs):
        return deepcopy(_live_response())

    monkeypatch.setattr(
        unified_coaching,
        "evaluate_unified_pending",
        fake_evaluate_unified_pending,
    )
    response = await coach_play_route.evaluate_pending_move(
        {
            "sessionId": "session-1",
            "fenBefore": FEN,
            "uci": "e5c4",
            "moveIndexPreview": 12,
            "userRating": 1200,
        },
        SimpleNamespace(user_id="user-1"),
    )
    return response, database


@pytest.mark.asyncio
async def test_shadow_on_and_off_return_the_same_player_payload(monkeypatch):
    shadow_response, shadow_db = await _run_route(
        monkeypatch,
        shadow_enabled=True,
    )
    live_response, live_db = await _run_route(
        monkeypatch,
        shadow_enabled=False,
    )

    assert shadow_response == live_response
    assert "_engineEvidence" not in shadow_response
    assert "pwc_v2_shadow" not in shadow_response

    shadow_decision = shadow_db.coach_sessions.updates[0][1]["$push"][
        "coaching_decisions"
    ]
    live_decision = live_db.coach_sessions.updates[0][1]["$push"]["coaching_decisions"]
    assert shadow_decision["pwc_v2_shadow"]["player_visible"] is False
    assert shadow_decision["pwc_v2_shadow"]["candidate_count"] == 1
    assert "pwc_v2_shadow" not in live_decision


@pytest.mark.asyncio
async def test_shadow_exception_fails_open_for_live_coaching(monkeypatch):
    from coach_play.v2 import shadow_conductor

    def fail_shadow(**_kwargs):
        raise RuntimeError("test-only shadow failure")

    monkeypatch.setattr(
        shadow_conductor,
        "build_shadow_packet_from_unified_response",
        fail_shadow,
    )
    response, database = await _run_route(
        monkeypatch,
        shadow_enabled=True,
    )

    expected = _live_response()
    expected.pop("_engineEvidence")
    assert response == expected
    stored = database.coach_sessions.updates[0][1]["$push"]["coaching_decisions"]
    assert "pwc_v2_shadow" not in stored
