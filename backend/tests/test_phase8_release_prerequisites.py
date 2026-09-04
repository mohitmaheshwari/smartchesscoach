import pytest
from datetime import datetime, timezone

from scripts.backfill_move_observations import (
    classify_destination_safety_observation,
    main_async as backfill_main_async,
)
from scripts.migrate_destination_safety_focus import (
    FOCUS_KIND,
    _candidate_for_user,
    run as migrate_focuses,
)
from scripts.lock_phase8_reach_target import build_target_lock
from scripts.report_phase8_release import (
    classify_journey_gap,
    release_status,
)
from scripts.reconcile_phase8_review_records import (
    _regenerate_one,
    classify_game_reconciliation,
)
from services.game_decryption_v5_service import V5_COACHING_VERSION
from services.move_observation_deriver import current_deriver_identity


FACT_VERSION = "piece_safety.destination_safety_exact.v1"
QUALITY_ID = "gap:piece_safety:destination_safety_exact"


def _derived(*, eligible=True, status="ok", fires=False):
    return {
        "schema_version": 18,
        "destination_safety_exact": {
            "version": FACT_VERSION,
            "quality_id": QUALITY_ID,
            "derivation_status": status,
            "eligible": eligible,
            "outcome": "miss" if fires else "handled",
            "fires": fires,
            "reason": "exact_destination_capture" if fires else "exchange_is_safe",
        },
    }


def test_observation_coverage_keeps_storage_and_decision_states_separate():
    missing = classify_destination_safety_observation(None, _derived(fires=True))
    assert missing == {
        "storage": "missing",
        "decision": "eligible",
        "write_required": True,
        "fires": True,
    }

    current = classify_destination_safety_observation(
        _derived(fires=False),
        _derived(fires=False),
    )
    assert current["storage"] == "already_current"
    assert current["write_required"] is False

    stale = classify_destination_safety_observation(
        {
            "schema_version": 17,
            "destination_safety_exact": {
                **_derived()["destination_safety_exact"],
                "version": "piece_safety.destination_safety_exact.v0",
            },
        },
        _derived(),
    )
    assert stale["storage"] == "stale_version"
    assert stale["write_required"] is True


def test_unavailable_position_is_invalid_and_never_written():
    outcome = classify_destination_safety_observation(
        None,
        _derived(eligible=False, status="unavailable"),
    )
    assert outcome["decision"] == "invalid"
    assert outcome["write_required"] is False


def test_sound_non_target_move_is_counted_as_evaluated_but_ineligible():
    outcome = classify_destination_safety_observation(
        None,
        _derived(eligible=False),
    )
    assert outcome["decision"] == "ineligible"
    assert outcome["write_required"] is True


@pytest.mark.asyncio
async def test_observation_apply_requires_named_confirmation_before_db_access():
    with pytest.raises(ValueError, match="phase8-observations"):
        await backfill_main_async(
            True,
            None,
            0,
            all_users=True,
            confirm=None,
        )


@pytest.mark.asyncio
async def test_focus_apply_requires_named_confirmation_before_db_access():
    with pytest.raises(ValueError, match="phase8-focus-bundles"):
        await migrate_focuses(
            apply=True,
            email=None,
            all_users=True,
            confirm=None,
        )


class _Rows:
    def __init__(self, rows):
        self.rows = list(rows)

    async def to_list(self, length=None):
        return list(self.rows)


class _Games:
    async def count_documents(self, _query):
        return 12


class _Observations:
    async def count_documents(self, _query):
        return 4

    def aggregate(self, _pipeline):
        return _Rows([{"decisions": 10, "misses": 4}])


class _Focuses:
    def __init__(self, active=None):
        self.active = active

    def find(self, _query):
        rows = self.active if isinstance(self.active, list) else [self.active]
        return _Rows(row for row in rows if row)


class _Db:
    def __init__(self, active=None):
        self.games = _Games()
        self.move_observations = _Observations()
        self.user_active_focus = _Focuses(active)


@pytest.mark.asyncio
async def test_missing_focus_becomes_an_insert_candidate_without_enrollment():
    candidate = await _candidate_for_user(
        _Db(),
        {"user_id": "user-1", "role": "user"},
    )
    assert candidate["eligible"] is True
    assert candidate["action"] == "insert"
    assert candidate["valid_bundle"] is True
    assert candidate["insert"]["focus_kind"] == FOCUS_KIND
    assert candidate["insert"]["instruction_id"]
    assert candidate["insert"]["status"] == "active"


@pytest.mark.asyncio
async def test_current_non_piece_focus_is_never_replaced_to_inflate_denominator():
    candidate = await _candidate_for_user(
        _Db({
            "_id": "focus-1",
            "user_id": "user-1",
            "type": "weakness",
            "status": "active",
            "topic_key": "calculation_depth",
        }),
        {"user_id": "user-1", "role": "user"},
    )
    assert candidate["eligible"] is False
    assert candidate["reason"] == "active_focus_conflict"
    assert candidate["valid_bundle"] is False
    assert "insert" not in candidate
    assert "update" not in candidate


@pytest.mark.asyncio
async def test_admin_and_duplicate_active_focuses_fail_closed():
    admin = await _candidate_for_user(
        _Db(),
        {"user_id": "admin-1", "role": "Admin"},
    )
    assert admin["reason"] == "excluded_admin_role"
    assert admin["valid_bundle"] is False

    duplicate = await _candidate_for_user(
        _Db(active=[
            {"user_id": "user-1", "status": "active", "topic_key": "piece_safety"},
            {"user_id": "user-1", "status": "active", "topic_key": "piece_safety"},
        ]),
        {"user_id": "user-1", "role": "user"},
    )
    assert duplicate["reason"] == "multiple_active_focuses"
    assert duplicate["valid_bundle"] is False


def _coverage_report(**overrides):
    report = {
        "mode": "dry_run",
        "full_corpus": True,
        "schema_version": 18,
        "fact_version": FACT_VERSION,
        "quality_id": QUALITY_ID,
        "observations_inspected": 446495,
        "writes_required": 0,
        "exact_fires": 4000,
        "users_covered": 67,
        "errors": 0,
        "storage": {"already_current": 446490, "missing": 5},
        "decisions": {"eligible": 40000, "ineligible": 406490, "invalid": 5},
    }
    report.update(overrides)
    return report


def _focus_report(**overrides):
    report = {
        "mode": "dry_run",
        "full_cohort": True,
        "non_admin_only": True,
        "users_scanned": 64,
        "eligible": 0,
        "qualifying_evidence": 31,
        "valid_bundles_after_run": 28,
    }
    report.update(overrides)
    return report


def test_target_lock_uses_post_apply_denominator_and_keeps_absolute_target():
    lock = build_target_lock(
        _coverage_report(),
        _focus_report(),
        coverage_sha256="a" * 64,
        focus_sha256="b" * 64,
        completion_target=10,
        created_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
        source_commit="abc123",
    )
    assert lock["eligible_denominator"] == 28
    assert lock["completion_target"] == 10
    assert lock["review_after_days"] == 42
    assert lock["coverage"]["invalid_observations"] == 5


def test_target_lock_refuses_unfinished_reconciliation_or_curve_grading():
    with pytest.raises(ValueError, match="not idempotent"):
        build_target_lock(
            _coverage_report(writes_required=1),
            _focus_report(),
            coverage_sha256="a" * 64,
            focus_sha256="b" * 64,
            completion_target=10,
            created_at=datetime.now(timezone.utc),
            source_commit="abc123",
        )


def test_target_lock_refuses_scoped_reports_as_a_population_denominator():
    with pytest.raises(ValueError, match="full-corpus"):
        build_target_lock(
            _coverage_report(full_corpus=False),
            _focus_report(),
            coverage_sha256="a" * 64,
            focus_sha256="b" * 64,
            completion_target=10,
            created_at=datetime.now(timezone.utc),
            source_commit="abc123",
        )
    with pytest.raises(ValueError, match="full non-admin"):
        build_target_lock(
            _coverage_report(),
            _focus_report(full_cohort=False),
            coverage_sha256="a" * 64,
            focus_sha256="b" * 64,
            completion_target=10,
            created_at=datetime.now(timezone.utc),
            source_commit="abc123",
        )
    with pytest.raises(ValueError, match="between 1"):
        build_target_lock(
            _coverage_report(),
            _focus_report(valid_bundles_after_run=8),
            coverage_sha256="a" * 64,
            focus_sha256="b" * 64,
            completion_target=10,
            created_at=datetime.now(timezone.utc),
            source_commit="abc123",
        )


def test_42_day_review_never_lowers_the_frozen_target():
    first = datetime(2026, 9, 4, tzinfo=timezone.utc)
    before_due = release_status(
        completion_target=10,
        completed_users=4,
        first_enrollment_at=first,
        now=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    after_due = release_status(
        completion_target=10,
        completed_users=4,
        first_enrollment_at=first,
        now=datetime(2026, 10, 17, tzinfo=timezone.utc),
    )
    completed = release_status(
        completion_target=10,
        completed_users=10,
        first_enrollment_at=first,
        now=datetime(2026, 9, 20, tzinfo=timezone.utc),
    )

    assert before_due["status"] == "in_progress"
    assert after_due["status"] == "pilot_incomplete"
    assert completed["status"] == "complete"
    assert after_due["completion_target"] == 10
    assert after_due["target_lowered"] is False


def test_journey_report_separates_inactivity_from_product_failure():
    ready_for_game = {
        "steps": {
            "home_focus_served": True,
            "lesson_opened": True,
            "server_graded_first_attempt": True,
            "lesson_completed": True,
            "review_served": True,
            "later_unassisted_opportunity": False,
            "verdict_served": False,
        },
        "complete": False,
    }
    assert classify_journey_gap(
        ready_for_game,
        later_analyzed_games=0,
    ) == "user_inactivity_no_later_game"
    assert classify_journey_gap(
        ready_for_game,
        later_analyzed_games=2,
    ) == "evidence_gap_no_comparable_opportunity"

    no_lesson = {
        "steps": {
            "home_focus_served": True,
            "lesson_opened": False,
        },
        "complete": False,
    }
    assert classify_journey_gap(
        no_lesson,
        later_analyzed_games=0,
    ) == "product_path_home_to_lesson"


def _reconciliation_fixture(*, plan=True, authorized=True):
    game = {
        "game_id": "game-1",
        "user_id": "user-1",
        "is_analyzed": True,
    }
    analysis = {
        "game_id": "game-1",
        "user_id": "user-1",
        "decryption_v5_version": V5_COACHING_VERSION,
        "decryption_v5_data": [{"move_number": 1, "caption": ""}],
        "stockfish_analysis": {
            "move_evaluations": [{
                "move_number": 1,
                "is_opponent_move": False,
            }]
        },
    }
    if plan:
        analysis["game_teaching_plan"] = {
            "schema_version": "personalized_game_review.shadow_plan.v1",
            "source_v5_version": V5_COACHING_VERSION,
            "observation_schema_version": 18,
            "deriver_identity": current_deriver_identity(),
            "planner_version": "personalized_game_review_planner.v1",
            "plan": (
                {
                    "chapters": [{
                        "event": {"display": {"authorized": True}}
                    }]
                }
                if authorized
                else None
            ),
        }
    observations = [{
        "schema_version": 18,
        "destination_safety_exact": {
            "version": FACT_VERSION,
            "quality_id": QUALITY_ID,
            "derivation_status": "ok",
        },
    }]
    return game, analysis, observations


def test_review_reconciliation_states_are_exclusive_and_fail_closed():
    game, analysis, observations = _reconciliation_fixture()
    current = classify_game_reconciliation(game, analysis, observations)
    assert current["state"] == "already_current"
    assert current["write_required"] is False

    game, analysis, observations = _reconciliation_fixture(authorized=False)
    no_event = classify_game_reconciliation(game, analysis, observations)
    assert no_event["state"] == "no_authorized_evidence"
    assert no_event["write_required"] is False

    game, analysis, observations = _reconciliation_fixture(plan=False)
    partial = classify_game_reconciliation(game, analysis, observations)
    assert partial["state"] == "partially_reconciled"
    assert partial["write_required"] is True

    game, analysis, observations = _reconciliation_fixture()
    analysis["decryption_v5_version"] = V5_COACHING_VERSION - 1
    analysis["game_teaching_plan"]["source_v5_version"] = (
        V5_COACHING_VERSION - 1
    )
    observations[0]["schema_version"] = 17
    stale = classify_game_reconciliation(game, analysis, observations)
    assert stale["state"] == "stale_version"
    assert stale["write_required"] is True

    game, analysis, _ = _reconciliation_fixture()
    analysis.pop("decryption_v5_data")
    analysis.pop("decryption_v5_version")
    analysis.pop("game_teaching_plan")
    never = classify_game_reconciliation(game, analysis, [])
    assert never["state"] == "never_had_required_records"

    invalid = classify_game_reconciliation(None, analysis, [])
    assert invalid["state"] == "invalid_or_unowned"
    assert invalid["write_required"] is False


@pytest.mark.asyncio
async def test_review_reconciliation_disables_model_and_learning_side_effects(
    monkeypatch,
):
    captured = {}

    async def generate(*_args, **kwargs):
        captured.update(kwargs)
        kwargs["game_teaching_plan_output"].update({
            "schema_version": "personalized_game_review.shadow_plan.v1",
            "plan": None,
        })
        return [{"move_number": 1, "caption": "Verified."}]

    class _Analyses:
        async def update_one(self, _query, _update):
            return None

    class _RegenDb:
        game_analyses = _Analyses()

    monkeypatch.setattr(
        "services.game_decryption_v5_service.generate_game_decryption_v5",
        generate,
    )
    outcome = await _regenerate_one(
        _RegenDb(),
        {
            "game_id": "game-1",
            "user_id": "user-1",
            "user_color": "white",
            "pgn": "1. e4 e5 *",
        },
        {
            "stockfish_analysis": {
                "move_evaluations": [{"move_number": 1}],
                "opponent_move_evaluations": [],
            },
        },
    )

    assert outcome == "updated"
    assert captured["persist_learning_side_effects"] is False
    assert captured["allow_llm_polish"] is False
