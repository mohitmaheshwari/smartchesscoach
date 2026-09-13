from scripts.measure_deterministic_teaching_intelligence_opportunities import (
    build_report,
    main,
)


def test_report_is_fully_bound_offline_and_keeps_holdout_closed():
    report = build_report()

    assert report["status"] == "measured_not_authorized"
    assert report["execution_contract"] == {
        "database_reads": 0,
        "database_writes": 0,
        "engine_runs": 0,
        "model_calls": 0,
        "holdout_opened": False,
        "player_facing_authorization": False,
    }
    assert report["summary"]["reviewed_games"] == 100
    assert report["summary"]["games_with_candidate_teaching"] == 96
    assert report["summary"]["honest_no_strong_lesson_games"] == 4


def test_report_exposes_the_current_last_wire_gap():
    report = build_report()
    reach = report["current_product_reach"]

    assert reach["stored_move_captions"] == 6372
    assert reach["stored_caption_explanations"] == 0
    assert reach["stored_teachable_events"] == 3
    assert reach["games_with_stored_whole_game_plan"] == 3


def test_every_family_reports_reach_coverage_consequence_and_feasibility():
    report = build_report()
    families = report["families"]

    assert len(families) == 19
    assert sum(row["opportunities"] for row in families) == (
        report["summary"]["family_occurrences"]
    )
    assert sum(row["current_causal_coverage"] for row in families) == (
        report["summary"]["current_causally_covered_occurrences"]
    )
    for row in families:
        assert row["players"] > 0
        assert row["uncovered_players"] >= 0
        assert row["confirmed_high_consequence_uncovered"] >= 0
        assert (
            row["consequence_evidence_complete"]
            + row["consequence_evidence_partial"]
            + row["consequence_evidence_absent"]
        ) == row["opportunities"]
        assert row["proof_feasibility"] in {"high", "medium"}
        assert row["canonical_proof_assets"]

    summary = report["summary"]
    assert summary["candidate_plies"] == (
        summary["candidate_plies_with_stored_engine_evidence"]
        + summary["candidate_plies_without_stored_engine_evidence"]
    )
    assert summary["candidate_plies_without_stored_engine_evidence"] > 0


def test_balanced_policy_is_transparent_pareto_selection_not_hidden_score():
    report = build_report()
    policies = report["policy_comparison"]

    assert policies["frequency_first"][0] == "forced_mate_story"
    assert policies["player_reach_first"][0] == "forced_mate_story"
    assert "weighted" not in policies
    assert policies["balanced_pareto_front"]
    assert "No hidden weighted score" in policies["balanced_definition"]


def test_candidate_bundles_report_exact_combined_reach_without_hidden_weights():
    report = build_report()
    bundles = report["candidate_bundle_comparison"]

    assert bundles["pareto_first"] == {
        "families": ["forced_mate_story"],
        "family_count": 1,
        "uncovered_opportunities": 36,
        "unique_games": 36,
        "unique_players": 24,
        "confirmed_high_consequence_uncovered": 35,
        "maximum_visible_coverage_if_all_prove": 60,
        "maximum_visible_coverage_pct_if_all_prove": 31.25,
    }
    selected = bundles["high_feasibility_reach_floor"]
    assert selected["families"] == [
        "forced_mate_story",
        "multi_move_material_accounting",
        "queen_safety_or_greedy_capture",
        "unpunished_opponent_opportunity",
    ]
    assert selected["uncovered_opportunities"] == 73
    assert selected["unique_games"] == 61
    assert selected["unique_players"] == 30
    assert selected["maximum_visible_coverage_pct_if_all_prove"] == 50.52


def test_report_file_is_byte_stable_across_windows_and_linux(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", ["measure", "--output", str(output)])

    main()

    raw = output.read_bytes()
    assert raw.endswith(b"\n")
    assert b"\r\n" not in raw
