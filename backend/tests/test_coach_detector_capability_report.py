from backend.scripts.report_coach_detector_capabilities import build_report


def _rows(report):
    return {row["detector_id"]: row for row in report["detectors"]}


def test_report_is_derived_from_every_registered_detector_and_curriculum():
    report = build_report()

    assert report["summary"]["registered_detectors"] == 48
    assert sum(report["summary"]["by_family"].values()) == 48
    assert report["content_coverage"] == {
        "openings": {
            "publishable": 41,
            "detector_covered": 41,
            "curriculum_selectable": 41,
        },
        "traps": {
            "publishable": 36,
            "detector_covered": 36,
            "curriculum_selectable": 31,
        },
        "opening_ideas": {
            "publishable": 19,
            "detector_covered": 19,
            "curriculum_selectable": 0,
        },
        "endgames": {
            "publishable": 20,
            "detector_covered": 20,
            "curriculum_selectable": 16,
        },
    }


def test_opening_and_trap_adapters_map_to_real_personalized_curriculum():
    rows = _rows(build_report())

    opening = rows["opening_play"]
    assert opening["content_count"] == 41
    assert opening["target_skill_count"] == 41
    assert opening["workspace"]["supported_content_count"] == 41

    traps = rows["trap_detection"]
    assert traps["content_count"] == 36
    assert traps["target_skill_count"] == 14
    assert traps["workspace"]["supported_content_count"] == 14


def test_five_verified_traps_remain_explore_only_without_rating_envelopes():
    coverage = build_report()["content_coverage"]["traps"]

    assert coverage["publishable"] - coverage["curriculum_selectable"] == 5


def test_every_endgame_has_an_exact_detector_but_four_are_explore_only():
    report = build_report()
    exact_rows = [
        row for row in report["detectors"]
        if row["detector_id"].startswith("endgame_curriculum__")
    ]

    assert len(exact_rows) == 20
    assert sum(row["curriculum_mapped"] for row in exact_rows) == 16
    assert all(row["workspace"]["available"] for row in exact_rows)
    assert {
        row["content_ids"][0]
        for row in exact_rows
        if not row["curriculum_mapped"]
    } == {
        "bishop_endgames/good_vs_bad_bishop",
        "bishop_endgames/opposite_color_bishops",
        "knight_endgames/knight_blockade",
        "knight_endgames/knight_vs_bishop",
    }


def test_shadow_detectors_never_claim_a_live_player_effect():
    report = build_report()

    assert report["summary"]["by_player_effect"].get("mastery_enabled", 0) == 0
    assert all(
        row["player_effect"] != "mastery_enabled"
        for row in report["detectors"]
        if row["quality_grade"] == "shadow"
    )


def test_report_covers_opening_plans_and_keeps_positional_mapping_gaps_explicit():
    report = build_report()
    gaps = set(report["mapping_gaps"])

    assert "opening_sound_deviation" in gaps
    assert "opening_castling" in gaps
    assert "concept_knight_outpost" in gaps
    assert "opening_plan_play" not in gaps
    assert report["content_coverage"]["opening_ideas"]["detector_covered"] == 19
    plan = _rows(report)["opening_plan_play"]
    assert plan["content_count"] == 19
    assert plan["quality_grade"] == "shadow"
