from services.unified_pwc_coaching import (
    MAX_CRITICAL_PER_SESSION,
    UNIFIED_DECISION_SOURCE,
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
