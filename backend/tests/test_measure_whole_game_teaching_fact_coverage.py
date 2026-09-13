import ast
import inspect
import json

from scripts import measure_whole_game_teaching_fact_coverage as coverage


def test_frozen_coverage_accounts_for_every_gold_moment():
    report = coverage.build_report(
        coverage.DEFAULT_PACKET,
        coverage.DEFAULT_WORKSHEET,
    )

    assert report["source"]["games"] == 100
    assert report["source"]["holdout_opened"] is False
    assert report["summary"] == {
        "gold_moments": 219,
        "exact_fact": 158,
        "different_fact": 28,
        "no_typed_fact": 33,
        "exact_coverage_pct": 72.15,
    }
    assert len(report["moments"]) == 219


def test_versioned_coverage_snapshot_matches_current_pure_fact_output():
    report = coverage.build_report(
        coverage.DEFAULT_PACKET,
        coverage.DEFAULT_WORKSHEET,
    )
    snapshot = json.loads(
        (
            coverage.BACKEND
            / "data/corpus_snapshots/whole_game_teaching_review_fact_coverage_v1_2026-09-13.json"
        ).read_text(encoding="utf-8")
    )
    assert snapshot == report


def test_coverage_audit_has_no_database_engine_or_model_calls():
    tree = ast.parse(inspect.getsource(coverage))
    imported_modules = set()
    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called_names.add(func.id)
            elif isinstance(func, ast.Attribute):
                called_names.add(func.attr)

    assert not any("pymongo" in name or "motor" in name for name in imported_modules)
    assert "services.game_decryption_v5_service" not in imported_modules
    assert not {
        "generate_game_decryption_v5",
        "popen_uci",
        "SimpleEngine",
        "Popen",
        "analyse",
        "analyze",
    } & called_names


def test_family_matching_never_calls_a_different_fact_exact():
    assert coverage._match_status(
        "fork_geometry",
        {
            "legal_material_loss": None,
            "verified_line": {"lesson_kind": "missed_material_opportunity"},
            "hidden_opportunity": None,
        },
    ) == "different_fact"
    assert coverage._match_status(
        "missed_forced_mate",
        {
            "legal_material_loss": None,
            "verified_line": {"lesson_kind": "missed_forced_mate"},
            "hidden_opportunity": None,
        },
    ) == "exact_fact"
