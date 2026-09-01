"""Structural route-boundary checks for default-off Game Review reflection.

The local Windows unit runtime does not install ``bcrypt``, so importing the
full auth route (a transitive dependency of ``routes.reflect``) fails before
the endpoint can be collected. Pure submission behavior is exercised in
``test_review_reflection_service.py``; this file verifies the live route's
guard, ownership boundary, server-contract lookup, and narrow request shape.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROUTE_PATH = Path(__file__).parents[1] / "routes" / "reflect.py"
SOURCE = ROUTE_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _class_fields(class_name: str):
    node = next(
        item
        for item in TREE.body
        if isinstance(item, ast.ClassDef) and item.name == class_name
    )
    return {
        item.target.id
        for item in node.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    }


def _function_source(function_name: str) -> str:
    node = next(
        item
        for item in TREE.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == function_name
    )
    return ast.get_source_segment(SOURCE, node) or ""


def test_v2_request_contract_is_options_only_and_has_no_raw_position_fields():
    fields = _class_fields("GameReviewEventReflectionRequest")
    assert fields == {
        "game_id",
        "event_id",
        "prompt_id",
        "shown_option_ids",
        "selected_option_id",
        "elapsed_ms",
        "answered_before_reveal",
    }
    assert not {"free_text", "fen", "pgn", "user_move", "best_move"}.intersection(fields)


def test_v2_route_is_default_off_and_undiscoverable():
    function = _function_source("submit_game_review_event_reflection")
    assert "personalized_game_review_access(review_user_doc).enabled" in function
    assert '"feature_flags.personalized_game_review_coach": 1' in function
    assert 'HTTPException(status_code=404, detail="Not found")' in function


def test_v2_route_checks_game_ownership_before_loading_server_contracts():
    function = _function_source("submit_game_review_event_reflection")
    ownership = function.index("user_scope_filter(user)")
    analysis_lookup = function.index("db.game_analyses.find_one")
    assert ownership < analysis_lookup
    assert 'candidate_event = move.get("teachable_event")' in function
    assert 'candidate_prompt = move.get("reflection_prompt")' in function


def test_v2_route_persists_only_through_event_reflection_service():
    function = _function_source("submit_game_review_event_reflection")
    assert "build_document_from_stored_contracts(" in function
    assert "store_event_reflection(db.reflection_sessions, document)" in function
    assert "insert_one" not in function
