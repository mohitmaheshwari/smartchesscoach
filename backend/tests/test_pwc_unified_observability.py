from services.pwc_unified_observability import summarize_unified_rollout


def test_rollout_report_measures_funnel_outcomes_and_play_isolation():
    sessions = [
        {
            "session_id": "coach-1",
            "game_mode": "coach",
            "status": "completed",
            "created_at": "2026-09-14T10:00:00+00:00",
            "unified_journey": {
                "started_at": "2026-09-14T10:00:00+00:00",
                "first_move_at": "2026-09-14T10:00:06+00:00",
                "resume_events": [{"created_at": "2026-09-14T10:02:00+00:00"}],
                "postgame_action_events": [{"action_kind": "recommended_next_action"}],
            },
            "coaching_decisions": [{
                "source": "pwc_unified_v1",
                "layer": "critical_interrupt",
                "delivered_at": "2026-09-14T10:01:00+00:00",
                "outcome": "revised",
                "interruption_duration_ms": 2500,
            }],
            "coaching_help_events": [{"action": "focus_check"}],
            "move_history": [{"by": "player"}, {"by": "coach"}],
        },
        {
            "session_id": "play-1",
            "game_mode": "play",
            "status": "resigned",
            "created_at": "2026-09-14T11:00:00+00:00",
            "unified_journey": {},
            "move_history": [{"by": "player"}],
        },
    ]

    report = summarize_unified_rollout(sessions, {"play-1": 1})

    assert report["sessions_by_mode"] == {"coach": 1, "play": 1}
    assert report["first_move"]["median_seconds"] == 6.0
    assert report["completion"]["completion_rate"] == 0.5
    assert report["completion"]["abandoned_before_two_player_moves"] == 1
    assert report["interventions"]["outcomes"] == {"revised": 1}
    assert report["help_requests"] == 1
    assert report["resume_events"] == 1
    assert report["postgame_actions"] == 1
    assert report["play_mode_isolation"] == {
        "live_coach_messages": 1,
        "passes_zero_message_gate": False,
    }


def test_rollout_report_handles_an_empty_cohort():
    report = summarize_unified_rollout([])
    assert report["sessions"] == 0
    assert report["first_move"]["median_seconds"] is None
    assert report["completion"]["completion_rate"] is None
    assert report["play_mode_isolation"]["passes_zero_message_gate"] is True
