import pytest
from datetime import datetime, timezone

from scripts.backfill_move_observations import (
    classify_destination_safety_observation,
    main_async as backfill_main_async,
)
from scripts.migrate_destination_safety_focus import (
    EXISTING_EXACT_REFRESH_CONFIRM,
    FOCUS_KIND,
    _candidate_in_requested_scope,
    _candidate_for_user,
    _run_existing_exact_refresh,
    _transition_plan_fingerprint,
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
from services.destination_safety_detector import FACT_VERSION, LEGACY_FACT_VERSION


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


@pytest.mark.asyncio
async def test_existing_exact_refresh_has_its_own_scope_and_confirmation():
    with pytest.raises(ValueError, match=EXISTING_EXACT_REFRESH_CONFIRM):
        await migrate_focuses(
            apply=True,
            email=None,
            all_users=True,
            confirm="phase8-focus-bundles",
            existing_exact_only=True,
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
async def test_stale_v1_exact_focus_becomes_a_v2_refresh_candidate():
    candidate = await _candidate_for_user(
        _Db({
            "_id": "focus-1",
            "user_id": "user-1",
            "type": "weakness",
            "status": "active",
            "topic_key": "piece_safety",
            "focus_kind": FOCUS_KIND,
            "detector_quality_id": QUALITY_ID,
            "detector_quality_grade": "plan",
            "proof_detector_id": LEGACY_FACT_VERSION,
            "instruction_id": "instruction-1",
            "instruction_text": "Check whether the piece can be taken.",
            "instruction_version": 2,
        }),
        {"user_id": "user-1", "role": "user"},
    )

    assert candidate["eligible"] is True
    assert candidate["action"] == "update"
    assert candidate["update"]["proof_detector_id"] == FACT_VERSION
    assert candidate["valid_bundle"] is True


@pytest.mark.asyncio
async def test_unpinned_quality_only_focus_becomes_a_v2_refresh_candidate():
    candidate = await _candidate_for_user(
        _Db({
            "_id": "focus-1",
            "user_id": "user-1",
            "type": "weakness",
            "status": "active",
            "topic_key": "piece_safety",
            "focus_kind": None,
            "detector_quality_id": QUALITY_ID,
            "detector_quality_grade": "plan",
            "proof_detector_id": None,
            "instruction_id": "instruction-1",
            "instruction_text": "Check whether the piece can be taken.",
            "instruction_version": 2,
        }),
        {"user_id": "user-1", "role": "user"},
    )

    assert candidate["eligible"] is True
    assert candidate["action"] == "update"
    assert candidate["existing_exact_focus"] is True
    assert candidate["update"]["focus_kind"] == FOCUS_KIND
    assert candidate["update"]["proof_detector_id"] == FACT_VERSION
    assert candidate["valid_bundle"] is True


def test_existing_exact_scope_never_creates_or_converts_another_focus():
    assert _candidate_in_requested_scope(
        {"action": "update", "existing_exact_focus": True},
        existing_exact_only=True,
    )
    assert not _candidate_in_requested_scope(
        {"action": "insert", "existing_exact_focus": False},
        existing_exact_only=True,
    )
    assert not _candidate_in_requested_scope(
        {"action": "update"},
        existing_exact_only=True,
    )


def _transition_focus(**overrides):
    return {
        "_id": "focus-1",
        "user_id": "user-1",
        "type": "weakness",
        "status": "active",
        "topic_key": "piece_safety",
        "focus_kind": FOCUS_KIND,
        "detector_quality_id": QUALITY_ID,
        "detector_quality_grade": "plan",
        "proof_detector_id": LEGACY_FACT_VERSION,
        "instruction_id": "instruction-1",
        "instruction_text": "Check whether the piece can be taken.",
        "instruction_version": 2,
        **overrides,
    }


def _observation_plan(**overrides):
    plan = {
        "games_inspected": 12,
        "observations_inspected": 120,
        "writes_required": 120,
        "exact_fires": 8,
        "eligible_decisions": 80,
        "misses": 8,
        "handled": 72,
        "errors": 0,
    }
    plan.update(overrides)
    return plan


class _TransitionResult:
    def __init__(self, modified_count):
        self.modified_count = modified_count


def _set_dotted(document, dotted, value):
    target = document
    parts = dotted.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


class _TransitionFocuses:
    def __init__(self, document):
        self.document = document
        self.updates = []

    def find(self, _query):
        return _Rows([self.document])

    async def update_one(self, query, update):
        transition = self.document.get("detector_version_transition")
        if "$or" in query:
            claimable = transition is None or transition.get("status") == "failed"
            if transition and transition.get("status") == "rewriting_observations":
                stale_before = query["$or"][2][
                    "detector_version_transition.started_at"
                ]["$lt"]
                started_at = transition.get("started_at")
                claimable = started_at is not None and started_at < stale_before
            if not claimable:
                return _TransitionResult(0)
        expected_run = query.get("detector_version_transition.run_id")
        if expected_run and (
            (self.document.get("detector_version_transition") or {}).get("run_id")
            != expected_run
        ):
            return _TransitionResult(0)
        self.updates.append((query, update))
        for dotted, value in (update.get("$set") or {}).items():
            _set_dotted(self.document, dotted, value)
        for dotted in (update.get("$unset") or {}):
            if dotted == "detector_version_transition":
                self.document.pop(dotted, None)
        return _TransitionResult(1)


class _TransitionGames:
    async def count_documents(self, _query):
        return 12


class _TransitionDb:
    def __init__(self, focus):
        self.user_active_focus = _TransitionFocuses(focus)
        self.games = _TransitionGames()


def test_transition_plan_fingerprint_is_order_stable_and_excludes_private_ids():
    first = {
        "_user_id": "private-user-a",
        "_focus": {"email": "private@example.com"},
        "user_fingerprint": "a" * 64,
        "focus_fingerprint": "b" * 64,
        "from_version": LEGACY_FACT_VERSION,
        "analyzed_games": 12,
        **_observation_plan(),
        "eligible": True,
    }
    second = {
        **first,
        "_user_id": "private-user-b",
        "user_fingerprint": "c" * 64,
    }
    forward = _transition_plan_fingerprint([first, second])
    reverse = _transition_plan_fingerprint([second, first])
    assert forward == reverse
    assert len(forward) == 64
    assert forward != _transition_plan_fingerprint([
        {**first, "writes_required": 119},
        second,
    ])


@pytest.mark.asyncio
async def test_existing_exact_refresh_rewrites_then_repins_one_user(
    monkeypatch,
):
    db = _TransitionDb(_transition_focus())

    async def derive(_db, _user_id, *, apply):
        return _observation_plan()

    async def eligible_update(_db, _focus):
        return {
            "eligible": True,
            "update": {
                "proof_detector_id": FACT_VERSION,
                "diagnosis_detector_id": FACT_VERSION,
            },
        }

    async def indexes(_db):
        return None

    monkeypatch.setattr(
        "scripts.migrate_destination_safety_focus._derive_user_observation_plan",
        derive,
    )
    monkeypatch.setattr(
        "scripts.migrate_destination_safety_focus._eligible_update",
        eligible_update,
    )
    monkeypatch.setattr(
        "scripts.migrate_destination_safety_focus.ensure_indexes",
        indexes,
    )
    users = [{"user_id": "user-1", "role": "user"}]
    dry_run = await _run_existing_exact_refresh(
        db,
        users,
        apply=False,
        confirm_plan=None,
    )
    applied = await _run_existing_exact_refresh(
        db,
        users,
        apply=True,
        confirm_plan=dry_run["plan_fingerprint"],
    )

    assert applied["updated"] == 1
    assert db.user_active_focus.document["proof_detector_id"] == FACT_VERSION
    assert "detector_version_transition" not in db.user_active_focus.document
    assert db.user_active_focus.updates[0][1]["$set"][
        "detector_version_transition"
    ]["status"] == "rewriting_observations"


@pytest.mark.asyncio
async def test_existing_exact_refresh_failure_keeps_old_pin_and_marks_resume(
    monkeypatch,
):
    db = _TransitionDb(_transition_focus())

    async def derive(_db, _user_id, *, apply):
        if apply:
            raise RuntimeError("simulated rewrite failure")
        return _observation_plan()

    async def indexes(_db):
        return None

    monkeypatch.setattr(
        "scripts.migrate_destination_safety_focus._derive_user_observation_plan",
        derive,
    )
    monkeypatch.setattr(
        "scripts.migrate_destination_safety_focus.ensure_indexes",
        indexes,
    )
    users = [{"user_id": "user-1", "role": "user"}]
    dry_run = await _run_existing_exact_refresh(
        db,
        users,
        apply=False,
        confirm_plan=None,
    )
    with pytest.raises(RuntimeError, match="simulated rewrite failure"):
        await _run_existing_exact_refresh(
            db,
            users,
            apply=True,
            confirm_plan=dry_run["plan_fingerprint"],
        )

    transition = db.user_active_focus.document["detector_version_transition"]
    assert transition["status"] == "failed"
    assert transition["failure_stage"] == "rewrite_observations"
    assert db.user_active_focus.document["proof_detector_id"] == LEGACY_FACT_VERSION

    async def successful_derive(_db, _user_id, *, apply):
        return _observation_plan()

    async def eligible_update(_db, _focus):
        return {
            "eligible": True,
            "update": {"proof_detector_id": FACT_VERSION},
        }

    monkeypatch.setattr(
        "scripts.migrate_destination_safety_focus._derive_user_observation_plan",
        successful_derive,
    )
    monkeypatch.setattr(
        "scripts.migrate_destination_safety_focus._eligible_update",
        eligible_update,
    )
    resumed_dry_run = await _run_existing_exact_refresh(
        db,
        users,
        apply=False,
        confirm_plan=None,
    )
    resumed = await _run_existing_exact_refresh(
        db,
        users,
        apply=True,
        confirm_plan=resumed_dry_run["plan_fingerprint"],
    )
    assert resumed["updated"] == 1
    assert db.user_active_focus.document["proof_detector_id"] == FACT_VERSION
    assert "detector_version_transition" not in db.user_active_focus.document


@pytest.mark.asyncio
async def test_existing_exact_refresh_aborts_all_writes_when_preflight_is_invalid(
    monkeypatch,
):
    db = _TransitionDb(_transition_focus())

    async def derive(_db, _user_id, *, apply):
        return _observation_plan(exact_fires=0, eligible_decisions=0)

    monkeypatch.setattr(
        "scripts.migrate_destination_safety_focus._derive_user_observation_plan",
        derive,
    )
    users = [{"user_id": "user-1", "role": "user"}]
    dry_run = await _run_existing_exact_refresh(
        db,
        users,
        apply=False,
        confirm_plan=None,
    )
    assert dry_run["ineligible"] == 1
    with pytest.raises(RuntimeError, match="aborted before writes"):
        await _run_existing_exact_refresh(
            db,
            users,
            apply=True,
            confirm_plan=dry_run["plan_fingerprint"],
        )
    assert db.user_active_focus.updates == []


@pytest.mark.asyncio
async def test_existing_exact_refresh_refuses_live_concurrent_claim(
    monkeypatch,
):
    db = _TransitionDb(_transition_focus(
        detector_version_transition={
            "status": "rewriting_observations",
            "to_version": FACT_VERSION,
            "run_id": "other-run",
            "started_at": datetime.now(timezone.utc),
        },
    ))

    async def derive(_db, _user_id, *, apply):
        return _observation_plan()

    async def indexes(_db):
        return None

    monkeypatch.setattr(
        "scripts.migrate_destination_safety_focus._derive_user_observation_plan",
        derive,
    )
    monkeypatch.setattr(
        "scripts.migrate_destination_safety_focus.ensure_indexes",
        indexes,
    )
    users = [{"user_id": "user-1", "role": "user"}]
    dry_run = await _run_existing_exact_refresh(
        db,
        users,
        apply=False,
        confirm_plan=None,
    )
    with pytest.raises(RuntimeError, match="could not claim"):
        await _run_existing_exact_refresh(
            db,
            users,
            apply=True,
            confirm_plan=dry_run["plan_fingerprint"],
        )
    assert db.user_active_focus.document[
        "detector_version_transition"
    ]["run_id"] == "other-run"


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
