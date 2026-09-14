import ast
from pathlib import Path


ROUTE_FILE = Path(__file__).parents[1] / "routes" / "coach_play.py"
SESSION_FILE = Path(__file__).parents[1] / "coach_play" / "coach_game_session.py"


def _function_source(name: str) -> str:
    source = ROUTE_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )
    return ast.get_source_segment(source, function) or ""


def test_shared_coach_move_writer_is_quiet_before_any_legacy_narration():
    source = _function_source("_apply_coach_move")
    quiet_return = source.index("if quiet_surface:")
    assert "surface_session.get(\"game_mode\") == \"play\"" in source
    assert "surface_session.get(\"experience_version\") == \"unified_v1\"" in source
    assert '"explanation": (' in source
    assert quiet_return < source.index("_PRE_MOVE_NAG_BY_TOPIC")
    assert quiet_return < source.index("evaluate_coach_move_teaching")


def test_unified_background_exits_before_legacy_analysis_and_message_paths():
    source = _function_source("_process_move_and_respond")
    unified_branch = source.index(
        'session_doc_check.get("experience_version") == "unified_v1"'
    )
    assert unified_branch < source.index("await get_quick_analysis(")
    assert unified_branch < source.index("should_coach_speak(")
    assert "await _unified_coach_turn(" in source


def test_pending_route_consumes_private_engine_evidence_before_responding():
    source = _function_source("evaluate_pending_move")
    assert 'unified_response.pop("_engineEvidence", {})' in source
    assert '"eval_before": engine_evidence.get("eval_before")' in source
    assert '"eval_after": engine_evidence.get("eval_after")' in source


def test_unified_turn_reuses_persisted_eval_and_pedagogical_opponent():
    source = _function_source("_unified_coach_turn")
    assert 'item.get("source") == "pwc_unified_v1"' in source
    assert "PedagogicalOpponent" in source
    assert "get_quick_analysis" not in source
    assert "coach_messages" not in source
    assert source.index('session_doc.get("opening_teaching_moves")') < source.index(
        "await opponent.get_move(fen_after_user)"
    )


def test_resume_endpoint_reenters_unified_controller_before_legacy_messages():
    source = _function_source("trigger_coach_move_endpoint")
    unified_branch = source.index(
        'session_doc.get("experience_version") == "unified_v1"'
    )
    assert unified_branch < source.index("CoachOpponent")
    assert unified_branch < source.index("coach_messages.insert_one")
    assert "await _unified_coach_turn(" in source
    assert '"message": None' in source


def test_unified_move_bypasses_legacy_curriculum_and_play_dispatch():
    source = _function_source("make_coach_play_move")
    assert 'is_unified = session_doc.get("experience_version") == "unified_v1"' in source
    assert "and not is_unified" in source
    unified_dispatch = source.index("if is_unified:", source.index("# Fire background task"))
    legacy_dispatch = source.index("elif not is_play_mode:", unified_dispatch)
    assert unified_dispatch < legacy_dispatch


def test_unified_start_does_not_auto_select_a_legacy_opening_or_guidance():
    source = _function_source("start_play_with_coach")
    auto_suggestion = source.index("await suggest_opening_for_session(")
    condition = source.rfind(
        "experience_version != UNIFIED_V1_EXPERIENCE",
        0,
        auto_suggestion,
    )
    assert condition >= 0
    guidance_response = source.index('"openingGuidance": (')
    assert (
        "experience_version != UNIFIED_V1_EXPERIENCE"
        in source[guidance_response:guidance_response + 500]
    )


def test_unified_evidence_survives_full_session_replace_writes():
    source = SESSION_FILE.read_text(encoding="utf-8")
    for field in (
        "coaching_decisions: List[Dict]",
        "coaching_help_events: List[Dict]",
        "unified_journey: Dict",
    ):
        assert field in source


def test_unified_journey_records_warning_outcomes_and_player_actions():
    confirm = _function_source("confirm_risky_move")
    revise = _function_source("record_unified_intervention_revision")
    journey = _function_source("record_unified_journey_event")
    assert '"coaching_decisions.$.outcome": "overridden"' in confirm
    assert '"interruption_duration_ms"' in confirm
    assert '"coaching_decisions.$.outcome": "revised"' in revise
    assert '"postgame_action": "postgame_action_events"' in journey
    assert '"resumed": "resume_events"' in journey
