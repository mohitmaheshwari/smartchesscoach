from pathlib import Path


def test_personalized_routes_are_authenticated_flag_gated_and_owned():
    source = (
        Path(__file__).parents[1] / "routes" / "training.py"
    ).read_text(encoding="utf-8")

    for route in (
        '"/personalized/session/start"',
        '"/personalized/session"',
        '"/personalized/session/respond"',
        '"/personalized/session/help"',
        '"/personalized/session/pause"',
        '"/personalized/session/{session_id}/evidence"',
    ):
        assert route in source
    assert source.count("_require_personalized_teaching_user(user)") >= 6
    assert '{"session_id": request.session_id, "user_id": user.user_id}' in source
    assert '"user_id": user.user_id,' in source


def test_generic_routes_dispatch_through_existing_teaching_engine():
    source = (
        Path(__file__).parents[1] / "routes" / "training.py"
    ).read_text(encoding="utf-8")

    assert "PERSONALIZED_LESSON_TYPE, start_lesson" in source
    assert "process_personalized_move" in source
    assert "request_personalized_help" in source
    assert "from services.teaching_engine import exit_lesson" in source
    assert "reason_choice=request.reason_choice" in source
    assert "reasoning_consistent=request" not in source


def test_home_diagnostic_routes_are_flagged_enrolled_exact_and_owned():
    source = (
        Path(__file__).parents[1] / "routes" / "training.py"
    ).read_text(encoding="utf-8")

    for route in (
        '"/personalized/diagnostic/start"',
        '"/personalized/diagnostic"',
        '"/personalized/diagnostic/respond"',
        '"/personalized/diagnostic/help"',
        '"/personalized/diagnostic/pause"',
    ):
        assert route in source
    assert source.count("_require_home_diagnostic_user(user)") >= 5
    assert '"delivery_mode": "blind_diagnostic"' in source
    assert '"home_replay_diagnostic"' in source
    assert "QualitySurface.PLAN" in source
