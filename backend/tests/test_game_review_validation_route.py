"""Structural Phase 6 validation-route security and ownership checks."""
from __future__ import annotations

import ast
from pathlib import Path


ROUTE_PATH = Path(__file__).parents[1] / "routes" / "coach.py"
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


def test_scorecard_request_contains_no_board_caption_or_account_override():
    fields = _class_fields("GameReviewValidationRequest")
    assert fields == {"presentation_variant", "ratings", "notes"}
    assert not {
        "fen",
        "pgn",
        "caption",
        "plan_id",
        "user_id",
        "email",
        "critical_truth_failure",
    }.intersection(fields)


def test_review_get_resolves_account_access_before_honoring_query_mode():
    function = _function_source("get_game_decryption_v5")
    flag_lookup = function.index('"feature_flags.personalized_game_review_coach": 1')
    ownership = function.index("user_scope_filter(user)")
    mode_resolution = function.index("resolve_blind_variant(")
    analysis_lookup = function.index("db.game_analyses.find_one")
    assert flag_lookup < ownership < mode_resolution < analysis_lookup
    assert "review_access.comparison_allowed" in function
    assert "public_validation_packet(" in function
    assert "except HTTPException:" in function


def test_scorecard_route_rechecks_access_and_server_plan_before_storage():
    function = _function_source("submit_game_review_validation")
    access = function.index("personalized_game_review_access(user_doc)")
    ownership = function.index("user_scope_filter(user)")
    analysis = function.index("db.game_analyses.find_one")
    projection = function.index("maybe_attach_phase5_review_fields(")
    document = function.index("build_validation_review_document(")
    storage = function.index("store_validation_review(")
    assert access < ownership < analysis < projection < document < storage
    assert "request.presentation_variant" in function
    assert "request.ratings" in function
    assert "request.notes" in function
    assert "request.plan_id" not in function
    assert "request.presentation_mode" not in function
    assert "request.critical_truth_failure" not in function


def test_validation_route_uses_one_canonical_collection_and_service():
    function = _function_source("submit_game_review_validation")
    assert "VALIDATION_COLLECTION" in function
    assert "insert_one" not in function
    assert "update_one" not in function
