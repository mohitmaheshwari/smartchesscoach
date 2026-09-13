import inspect

from services.whole_game_review_composer import (
    PHASE_SOURCE,
    WHOLE_GAME_COMPOSER_VERSION,
    WHOLE_GAME_REVIEW_SCHEMA_VERSION,
    compose_empty_whole_game_review,
    compose_whole_game_review,
)


def _event(
    event_id,
    *,
    ply,
    outcome="missed",
    actor="user",
    headline="One decision is worth replaying",
    caption="The recapture allowed a pawn fork.",
    principle="Before recapturing, check the next pawn push.",
):
    return {
        "event_id": event_id,
        "move": {
            "ply": ply,
            "number": (ply + 1) // 2,
            "san": "Rxe4",
            "actor": actor,
        },
        "outcome": outcome,
        "display": {"authorized": True},
        "teaching": {
            "headline": headline,
            "caption": caption,
            "principle": principle,
        },
    }


def _plan(events, *, takeaway=None):
    first = events[0]
    return {
        "plan_id": "plan-v1",
        "chapters": [
            {"event_id": event["event_id"], "role": "turning_point"}
            for event in events
        ],
        "takeaway": takeaway or first["teaching"]["principle"],
    }


def _envelope(plan, *, source_v5_version=154):
    return {
        "formula_id": "E_transition_then_teaching",
        "source_v5_version": source_v5_version,
        "plan": {
            **plan,
            "input_fingerprint": "a" * 64,
        },
    }


def _moves():
    return (
        {
            "phase": "opening",
            "opening_name": "Italian Game",
            "move_san": "e4",
        },
        {
            "phase": "opening",
            "opening_name": "Italian Game",
            "move_san": "e5",
        },
        {"phase": "middlegame", "move_san": "Nf3"},
        {"phase": "middlegame", "move_san": "Nc6"},
    )


def test_composes_one_connected_story_from_safe_events_and_stored_phases():
    event = _event("game:3:verified", ply=3)
    plan = _plan([event])

    result = compose_whole_game_review(
        stored_moves=_moves(),
        safe_plan=plan,
        safe_events=(event,),
        stored_plan_envelope=_envelope(plan),
    )

    assert result["schema_version"] == WHOLE_GAME_REVIEW_SCHEMA_VERSION
    assert result["composer_version"] == WHOLE_GAME_COMPOSER_VERSION
    assert result["source"]["phase_source"] == PHASE_SOURCE
    assert result["opening"] == {
        "name": "Italian Game",
        "claim_strength": "identity_only",
    }
    assert result["central_story"] == {
        "headline": "One decision is worth replaying",
        "lead": (
            "You reached the Italian Game. "
            "The clearest verified lesson came in the middlegame."
        ),
        "phase": "middlegame",
        "source_event_id": event["event_id"],
    }
    phases = {item["phase"]: item for item in result["phases"]}
    assert phases["opening"]["state"] == "no_authorized_lesson"
    assert "do not yet have an opening lesson I can prove" in phases["opening"]["summary"]
    assert phases["middlegame"]["state"] == "verified_lesson"
    assert phases["middlegame"]["event_ids"] == [event["event_id"]]
    assert phases["endgame"]["state"] == "not_reached"
    assert phases["endgame"]["summary"] == (
        "This game ended before a real endgame began."
    )
    assert result["surviving_instruction"]["source_event_id"] == event["event_id"]
    assert len(result["presentation_fingerprint"]) == 64


def test_positive_authorized_event_is_good_play_not_a_manufactured_problem():
    event = _event(
        "game:2:good",
        ply=2,
        outcome="demonstrated",
        headline="You kept every piece protected",
    )
    plan = _plan([event])

    result = compose_whole_game_review(
        stored_moves=_moves(),
        safe_plan=plan,
        safe_events=(event,),
        stored_plan_envelope=_envelope(plan),
    )

    opening = next(item for item in result["phases"] if item["phase"] == "opening")
    assert opening["state"] == "verified_good_play"
    assert opening["lead_event_headline"] == "You kept every piece protected"


def test_zero_authorized_events_is_an_honest_complete_story():
    result = compose_empty_whole_game_review(stored_moves=_moves())

    assert result["central_story"] == {
        "headline": "I don't have a verified lesson for this game yet.",
        "lead": (
            "You can still walk through every move. I won't invent a lesson "
            "that the stored evidence cannot prove."
        ),
        "phase": None,
        "source_event_id": None,
    }
    assert result["featured_event_ids"] == []
    assert result["surviving_instruction"] is None
    assert result["source"]["kind"] == "stored_phase_overview"
    assert len(result["source"]["input_fingerprint"]) == 64
    assert [phase["state"] for phase in result["phases"]] == [
        "no_authorized_lesson",
        "no_authorized_lesson",
        "not_reached",
    ]
    assert result == compose_empty_whole_game_review(stored_moves=_moves())


def test_empty_story_fails_closed_when_stored_phase_is_missing_or_invalid():
    assert compose_empty_whole_game_review(stored_moves=()) is None
    assert compose_empty_whole_game_review(
        stored_moves=({"phase": "late-ish"},)
    ) is None


def test_opponent_event_gets_actor_safe_fallback_headline():
    event = _event(
        "game:4:opponent",
        ply=4,
        actor="opponent",
        headline="",
    )
    plan = _plan([event])

    result = compose_whole_game_review(
        stored_moves=_moves(),
        safe_plan=plan,
        safe_events=(event,),
        stored_plan_envelope=_envelope(plan),
    )

    assert result["central_story"]["headline"] == "Your opponent left a chance"


def test_deterministic_fingerprint_changes_when_the_safe_plan_changes():
    event = _event("game:3:verified", ply=3)
    plan = _plan([event])
    first = compose_whole_game_review(
        stored_moves=_moves(),
        safe_plan=plan,
        safe_events=(event,),
        stored_plan_envelope=_envelope(plan),
    )
    second = compose_whole_game_review(
        stored_moves=_moves(),
        safe_plan=plan,
        safe_events=(event,),
        stored_plan_envelope=_envelope(plan),
    )
    changed_plan = _plan([event], takeaway=event["teaching"]["caption"])
    changed = compose_whole_game_review(
        stored_moves=_moves(),
        safe_plan=changed_plan,
        safe_events=(event,),
        stored_plan_envelope=_envelope(changed_plan),
    )

    assert first == second
    assert first["presentation_fingerprint"] != changed["presentation_fingerprint"]


def test_fails_closed_on_phase_provenance_event_and_takeaway_mismatches():
    event = _event("game:3:verified", ply=3)
    plan = _plan([event])

    bad_phase = list(_moves())
    bad_phase[2] = {"phase": "late-ish", "move_san": "Nf3"}
    assert compose_whole_game_review(
        stored_moves=bad_phase,
        safe_plan=plan,
        safe_events=(event,),
        stored_plan_envelope=_envelope(plan),
    ) is None

    unauthorized = {**event, "display": {"authorized": False}}
    assert compose_whole_game_review(
        stored_moves=_moves(),
        safe_plan=plan,
        safe_events=(unauthorized,),
        stored_plan_envelope=_envelope(plan),
    ) is None

    assert compose_whole_game_review(
        stored_moves=_moves(),
        safe_plan=plan,
        safe_events=(event,),
        stored_plan_envelope=_envelope(plan, source_v5_version=None),
    ) is None

    bad_takeaway = {**plan, "takeaway": "A sentence with no event source."}
    assert compose_whole_game_review(
        stored_moves=_moves(),
        safe_plan=bad_takeaway,
        safe_events=(event,),
        stored_plan_envelope=_envelope(bad_takeaway),
    ) is None


def test_composer_has_no_board_engine_database_network_or_model_dependency():
    import services.whole_game_review_composer as module

    source = inspect.getsource(module).lower()
    forbidden = (
        "import chess",
        "stockfish",
        "pymongo",
        "motor",
        "requests",
        "httpx",
        "openai",
        "anthropic",
        "maia",
        "otter",
    )
    assert all(token not in source for token in forbidden)
