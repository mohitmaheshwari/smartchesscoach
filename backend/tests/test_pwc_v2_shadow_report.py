from scripts.report_pwc_v2_shadow import summarize_shadow_sessions


def _candidate(candidate_id: str, *, source: str = "caption_pipeline"):
    return {
        "candidate_id": candidate_id,
        "source": source,
        "category": "piece_safety",
    }


def _packet(*, candidates, winners, disagreement=False, rejected=None):
    policies = {
        name: {
            "winner_candidate_id": winners.get(name),
            "tied_candidate_ids": (
                [winners[name]] if winners.get(name) is not None else []
            ),
            "tie": False,
        }
        for name in (
            "safety_focus_lexicographic",
            "expected_learning_value",
            "phase_guarded",
        )
    }
    rejected = rejected or []
    return {
        "schema_version": "pwc_v2_shadow.v1",
        "policy_version": "pwc_v2_policy_bakeoff.v1",
        "player_visible": False,
        "candidate_count": len(candidates),
        "rejected_count": len(rejected),
        "candidates": candidates,
        "rejected": rejected,
        "policies": policies,
        "disagreement": disagreement,
        "created_at": "2026-09-16T00:00:00+00:00",
    }


def test_report_measures_policy_disagreement_without_authorizing_a_winner():
    packet = _packet(
        candidates=[_candidate("danger"), _candidate("focus", source="focus_bridge")],
        winners={
            "safety_focus_lexicographic": "danger",
            "expected_learning_value": "focus",
            "phase_guarded": "danger",
        },
        disagreement=True,
    )
    report = summarize_shadow_sessions(
        [
            {
                "session_id": "session-1",
                "user_rating": 1100,
                "coaching_decisions": [
                    {"move_key": "12:e2e4", "pwc_v2_shadow": packet}
                ],
            }
        ]
    )
    assert report["sessions"] == 1
    assert report["packets"] == 1
    assert report["multi_candidate_packets"] == 1
    assert report["comparison_possible"] is True
    assert report["disagreements"] == 1
    assert report["conductor_choice_authorized"] is False
    assert report["invariant_violation_count"] == 0
    assert report["candidate_sources"] == {
        "caption_pipeline": 1,
        "focus_bridge": 1,
    }


def test_report_fails_structural_invariants_and_never_claims_comparison():
    packet = _packet(
        candidates=[_candidate("only"), _candidate("other")],
        winners={
            "safety_focus_lexicographic": "missing",
            "expected_learning_value": "only",
            "phase_guarded": "only",
        },
    )
    packet["player_visible"] = True
    packet["candidate_count"] = 3
    report = summarize_shadow_sessions(
        [
            {
                "session_id": "session-bad",
                "coaching_decisions": [{"move_key": "2:a2a3", "pwc_v2_shadow": packet}],
            }
        ]
    )
    assert report["comparison_possible"] is False
    assert report["invariant_violation_count"] == 1
    violations = report["invariant_violations"][0]["violations"]
    assert "player_visible_not_false" in violations
    assert "candidate_count_mismatch" in violations
    assert "unknown_winner:safety_focus_lexicographic" in violations


def test_report_counts_rejections_and_zero_candidate_packets():
    packet = _packet(
        candidates=[],
        winners={},
        rejected=[
            {
                "candidate_id": "bad",
                "reasons": ["proof_not_verified", "candidate_abstained"],
            }
        ],
    )
    report = summarize_shadow_sessions(
        [{"coaching_decisions": [{"pwc_v2_shadow": packet}]}]
    )
    assert report["zero_candidate_packets"] == 1
    assert report["rejected_candidates"] == 1
    assert report["rejection_reasons"] == {
        "proof_not_verified": 1,
        "candidate_abstained": 1,
    }


def test_report_counts_adapter_timeouts_separately_from_candidate_rejections():
    packet = _packet(candidates=[], winners={})
    packet["adapter_observations"] = [
        {
            "adapter": "canonical_curriculum",
            "status": "timed_out",
            "elapsed_ms": 25.4,
            "budget_ms": 25,
            "candidate_count": 0,
        }
    ]

    report = summarize_shadow_sessions(
        [{"coaching_decisions": [{"pwc_v2_shadow": packet}]}]
    )

    assert report["adapter_statuses"] == {
        "canonical_curriculum:timed_out": 1,
    }
    assert report["rejected_candidates"] == 0
