from datetime import datetime, timedelta, timezone

import pytest

from services.complete_coaching_access import (
    BASELINE_COLLECTION,
    BASELINE_VERSION,
    TARGET_COLLECTION,
    TARGET_LOCK_ID,
)
from services.destination_safety_detector import FACT_VERSION, QUALITY_ID
from services.game_decryption_v5_service import V5_COACHING_VERSION
from services.personal_curriculum import (
    ApplicationOutcome,
    AttemptKind,
    EvidenceSourceType,
    LessonResult,
    PIC_CANONICAL_SOURCE,
    PIC_CONTENT_ID,
    PIC_CONTENT_KIND,
    PIC_SKILL_ID,
)
from services.phase8_release_evidence import (
    FOCUS_KIND,
    JOURNEY_COLLECTION,
    build_phase8_journey_projection,
    build_pre_enrollment_baseline,
    record_phase8_reach_event,
    same_immutable_baseline,
)


def _nested(row, key):
    value = row
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _matches(row, query):
    for key, expected in query.items():
        actual = _nested(row, key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$gte" in expected and not (actual is not None and actual >= expected["$gte"]):
                return False
        elif actual != expected:
            return False
    return True


class _Cursor:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]

    def sort(self, key, direction):
        self.rows.sort(
            key=lambda row: _nested(row, key) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=direction < 0,
        )
        return self

    async def to_list(self, length=None):
        return self.rows[:length] if length else list(self.rows)

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self.rows):
            raise StopAsyncIteration
        row = self.rows[self._index]
        self._index += 1
        return row


class _Write:
    def __init__(self, upserted_id=None):
        self.upserted_id = upserted_id


class _Collection:
    def __init__(self, rows=()):
        self.rows = [dict(row) for row in rows]

    async def find_one(self, query, projection=None):
        for row in self.rows:
            if _matches(row, query):
                return dict(row)
        return None

    def find(self, query, projection=None):
        return _Cursor(row for row in self.rows if _matches(row, query))

    async def update_one(self, query, update, upsert=False):
        for row in self.rows:
            if _matches(row, query):
                return _Write()
        if upsert:
            inserted = dict(update.get("$setOnInsert") or {})
            self.rows.append(inserted)
            return _Write(inserted.get("_id"))
        return _Write()


class _Db:
    def __init__(self, collections):
        self.collections = {
            name: _Collection(rows)
            for name, rows in collections.items()
        }

    def __getattr__(self, name):
        return self.collections[name]

    def __getitem__(self, name):
        return self.collections[name]


def _lesson_result(*, at, application=False, missed=False):
    payload = LessonResult(
        content_kind=PIC_CONTENT_KIND,
        content_id=PIC_CONTENT_ID,
        canonical_source=PIC_CANONICAL_SOURCE,
        content_version="test.v1",
        skill_id=PIC_SKILL_ID,
        primary_skill_id=PIC_SKILL_ID,
        attempt_kind=(
            AttemptKind.APPLICATION if application else AttemptKind.INDEPENDENT
        ),
        occurred_at=at,
        correct=None if application else True,
        position_id=None if application else "position-1",
        board_verified=not application,
        distinct_position=not application,
        first_answer=None if application else True,
        attempt_id="application-1" if application else "attempt-1",
        source_type=(
            EvidenceSourceType.ORGANIC_GAME
            if application
            else EvidenceSourceType.LESSON
        ),
        application_outcome=(
            ApplicationOutcome.MISSED
            if missed
            else (
                ApplicationOutcome.APPLIED
                if application
                else ApplicationOutcome.NOT_MEASURED
            )
        ),
        detector_quality_id=QUALITY_ID if application else None,
        detector_version=FACT_VERSION if application else None,
        evidence_owner="analysis_worker" if application else "learning_sessions",
        evidence_ref="game-4" if application else "session-1",
    ).event_dict()
    return {
        "event_type": "lesson_result",
        "lesson_result": payload,
    }


def _db(*, now, events=(), journey=()):
    games = [
        {
            "game_id": f"game-{index}",
            "user_id": "user-1",
            "is_analyzed": True,
            "date_played": now - timedelta(days=4 - index),
        }
        for index in range(1, 4)
    ]
    analyses = [
        {
            "game_id": game["game_id"],
            "decryption_v5_version": V5_COACHING_VERSION,
            "decryption_v5_data": [{"move_number": 1, "caption": "Stored."}],
            "game_teaching_plan": {
                "schema_version": "personalized_game_review.shadow_plan.v1",
                "source_v5_version": V5_COACHING_VERSION,
                "planner_version": "personalized_game_review_planner.v1",
                "plan": None,
            },
        }
        for game in games
    ]
    observations = [
        {
            "_id": f"obs-{index}",
            "game_id": f"game-{index}",
            "user_id": "user-1",
            "schema_version": 18,
            "destination_safety_exact": {
                "version": FACT_VERSION,
                "derivation_status": "ok",
                "eligible": True,
                "outcome": "miss" if index == 3 else "handled",
            },
        }
        for index in range(1, 4)
    ]
    return _Db({
        "users": [{
            "user_id": "user-1",
            "role": "user",
            "feature_flags": {
                "personalized_game_review_coach": {
                    "enabled": True,
                    "cohort": "phase8_release_rescue_2026_09",
                    "phase8_enrolled_at": now.isoformat(),
                }
            },
        }],
        TARGET_COLLECTION: [{
            "_id": TARGET_LOCK_ID,
            "status": "locked",
            "contract_version": "phase8_reach_target.v1",
            "eligible_denominator": 12,
        }],
        BASELINE_COLLECTION: [{
            "_id": "baseline-1",
            "user_id": "user-1",
            "baseline_version": BASELINE_VERSION,
            "target_lock_id": TARGET_LOCK_ID,
            "status": "captured",
            "focus_id": "focus-1",
            "instruction_id": "instruction-1",
            "focus_kind": FOCUS_KIND,
        }],
        "user_active_focus": [{
            "_id": "focus-1",
            "user_id": "user-1",
            "status": "active",
            "focus_kind": FOCUS_KIND,
            "detector_quality_id": QUALITY_ID,
            "instruction_id": "instruction-1",
            "instruction_version": "v1",
        }],
        "games": games,
        "game_analyses": analyses,
        "move_observations": observations,
        "learning_sessions": [{
            "user_id": "user-1",
            "skill_id": PIC_SKILL_ID,
            "events": list(events),
        }],
        JOURNEY_COLLECTION: list(journey),
    })


@pytest.mark.asyncio
async def test_baseline_freezes_three_games_and_review_coverage(monkeypatch):
    now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    db = _db(now=now)
    db.users.rows[0]["feature_flags"]["personalized_game_review_coach"].pop(
        "phase8_enrolled_at"
    )

    async def mastery(*_args, **_kwargs):
        return {"state": "learning"}

    monkeypatch.setattr(
        "services.concept_mastery_service.get_pic_mastery_projection",
        mastery,
    )
    baseline = await build_pre_enrollment_baseline(
        db,
        "user-1",
        cutoff=now,
        source_commit="abc123",
    )

    assert baseline["status"] == "captured"
    assert baseline["pre_period"]["games"] == 3
    assert baseline["pre_period"]["opportunities"]["decisions"] == 3
    assert baseline["coverage_at_cutoff"]["analyzed_games"] == 3
    assert baseline["coverage_at_cutoff"]["current_v5_reviews"] == 3
    assert baseline["coverage_at_cutoff"]["current_teaching_plans"] == 3
    assert same_immutable_baseline(dict(baseline), baseline) is True
    changed = {**baseline, "coverage_at_cutoff": {"analyzed_games": 2}}
    assert same_immutable_baseline(changed, baseline) is False


@pytest.mark.asyncio
async def test_journey_records_idempotent_reach_and_practice_does_not_prove_transfer(
    monkeypatch,
):
    now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    db = _db(now=now, events=[_lesson_result(at=now + timedelta(minutes=1))])
    for key, value in {
        "COMPLETE_COACHING_SYSTEM_V1_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT": "validation",
    }.items():
        monkeypatch.setenv(key, value)

    async def mastery(*_args, **_kwargs):
        return {"state": "learning"}

    monkeypatch.setattr(
        "services.concept_mastery_service.get_pic_mastery_projection",
        mastery,
    )
    inserted = await record_phase8_reach_event(
        db,
        "user-1",
        step="home_focus_served",
        source_id="focus-1",
    )
    duplicate = await record_phase8_reach_event(
        db,
        "user-1",
        step="home_focus_served",
        source_id="focus-1",
    )
    projection = await build_phase8_journey_projection(db, "user-1")

    assert inserted is True
    assert duplicate is False
    assert projection["practice"]["lesson_evidence_events"] == 1
    assert projection["practice"]["changes_transfer_verdict"] is False
    assert projection["transfer"]["verdict"] == "insufficient_evidence"
    assert projection["steps"]["server_graded_first_attempt"] is True
    assert projection["steps"]["later_unassisted_opportunity"] is False


@pytest.mark.asyncio
async def test_later_verified_miss_keeps_focus_recurring(monkeypatch):
    now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    events = [
        _lesson_result(at=now + timedelta(minutes=1)),
        _lesson_result(
            at=now + timedelta(days=1),
            application=True,
            missed=True,
        ),
    ]
    db = _db(now=now, events=events)
    for key, value in {
        "COMPLETE_COACHING_SYSTEM_V1_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT": "validation",
    }.items():
        monkeypatch.setenv(key, value)

    async def mastery(*_args, **_kwargs):
        return {"state": "learning"}

    monkeypatch.setattr(
        "services.concept_mastery_service.get_pic_mastery_projection",
        mastery,
    )
    projection = await build_phase8_journey_projection(db, "user-1")

    assert projection["transfer"]["verdict"] == "still_recurring"
    assert projection["transfer"]["missed"] == 1
    assert projection["steps"]["later_unassisted_opportunity"] is True


@pytest.mark.asyncio
async def test_insufficient_pre_period_can_never_claim_improvement(monkeypatch):
    now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    events = [
        _lesson_result(at=now + timedelta(minutes=1)),
        _lesson_result(at=now + timedelta(days=1), application=True),
    ]
    db = _db(now=now, events=events)
    db[BASELINE_COLLECTION].rows[0]["status"] = "insufficient_pre_period"
    for key, value in {
        "COMPLETE_COACHING_SYSTEM_V1_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT": "validation",
    }.items():
        monkeypatch.setenv(key, value)

    async def mastery(*_args, **_kwargs):
        return {
            "state": "proven_in_games",
            "current_demonstrated_checkpoint": 5,
        }

    monkeypatch.setattr(
        "services.concept_mastery_service.get_pic_mastery_projection",
        mastery,
    )
    projection = await build_phase8_journey_projection(db, "user-1")

    assert projection["transfer"]["handled"] == 1
    assert projection["transfer"]["verdict"] == "insufficient_evidence"
    assert "cannot judge change" in projection["transfer"]["message"]


@pytest.mark.asyncio
async def test_old_progress_verdict_cannot_close_a_new_evidence_state(monkeypatch):
    now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    events = [
        _lesson_result(at=now + timedelta(minutes=1)),
        _lesson_result(
            at=now + timedelta(days=1),
            application=True,
            missed=True,
        ),
    ]
    db = _db(
        now=now,
        events=events,
        journey=[{
            "_id": "old-verdict",
            "schema_version": "complete_coaching_journey.v1",
            "user_id": "user-1",
            "baseline_id": "baseline-1",
            "step": "progress_verdict_served",
            "source_id": "focus-1:old-evidence",
            "occurred_at": now + timedelta(minutes=2),
            "metadata": {
                "verdict": "insufficient_evidence",
                "evidence_identity": "old-evidence",
            },
        }],
    )
    for key, value in {
        "COMPLETE_COACHING_SYSTEM_V1_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT": "validation",
    }.items():
        monkeypatch.setenv(key, value)

    async def mastery(*_args, **_kwargs):
        return {
            "state": "learning",
            "current_demonstrated_checkpoint": 5,
        }

    monkeypatch.setattr(
        "services.concept_mastery_service.get_pic_mastery_projection",
        mastery,
    )
    before = await build_phase8_journey_projection(db, "user-1")
    assert before["transfer"]["verdict"] == "still_recurring"
    assert before["steps"]["verdict_served"] is False

    identity = before["transfer"]["evidence_identity"]
    db[JOURNEY_COLLECTION].rows.append({
        "_id": "new-verdict",
        "schema_version": "complete_coaching_journey.v1",
        "user_id": "user-1",
        "baseline_id": "baseline-1",
        "step": "progress_verdict_served",
        "source_id": f"focus-1:{identity}",
        "occurred_at": now + timedelta(days=1, minutes=1),
        "metadata": {
            "verdict": "still_recurring",
            "evidence_identity": identity,
        },
    })
    after = await build_phase8_journey_projection(db, "user-1")
    assert after["steps"]["verdict_served"] is True


@pytest.mark.asyncio
async def test_all_journey_facts_out_of_order_do_not_count_as_complete(monkeypatch):
    now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    events = [
        _lesson_result(at=now + timedelta(minutes=1)),
        _lesson_result(
            at=now + timedelta(days=1),
            application=True,
            missed=True,
        ),
    ]
    journey = [
        {
            "_id": "home",
            "user_id": "user-1",
            "baseline_id": "baseline-1",
            "step": "home_focus_served",
            "source_id": "home",
            "occurred_at": now + timedelta(seconds=1),
            "metadata": {},
        },
        {
            "_id": "opened",
            "user_id": "user-1",
            "baseline_id": "baseline-1",
            "step": "lesson_opened",
            "source_id": "session-1",
            "occurred_at": now + timedelta(seconds=2),
            "metadata": {},
        },
        {
            "_id": "complete",
            "user_id": "user-1",
            "baseline_id": "baseline-1",
            "step": "lesson_completed",
            "source_id": "session-1",
            "occurred_at": now + timedelta(minutes=2),
            "metadata": {},
        },
        {
            "_id": "review-too-early",
            "user_id": "user-1",
            "baseline_id": "baseline-1",
            "step": "review_served",
            "source_id": "game-0",
            "occurred_at": now + timedelta(seconds=30),
            "metadata": {"outcome": "authorized_event"},
        },
    ]
    db = _db(now=now, events=events, journey=journey)
    for key, value in {
        "COMPLETE_COACHING_SYSTEM_V1_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT": "validation",
    }.items():
        monkeypatch.setenv(key, value)

    async def mastery(*_args, **_kwargs):
        return {
            "state": "learning",
            "current_demonstrated_checkpoint": 5,
        }

    monkeypatch.setattr(
        "services.concept_mastery_service.get_pic_mastery_projection",
        mastery,
    )
    before = await build_phase8_journey_projection(db, "user-1")
    identity = before["transfer"]["evidence_identity"]
    db[JOURNEY_COLLECTION].rows.append({
        "_id": "verdict",
        "user_id": "user-1",
        "baseline_id": "baseline-1",
        "step": "progress_verdict_served",
        "source_id": f"focus-1:{identity}",
        "occurred_at": now + timedelta(days=1, minutes=1),
        "metadata": {
            "verdict": "still_recurring",
            "evidence_identity": identity,
        },
    })

    projection = await build_phase8_journey_projection(db, "user-1")
    assert all(projection["steps"].values()) is True
    assert projection["sequence_valid"] is False
    assert projection["complete"] is False


@pytest.mark.asyncio
async def test_later_ordered_event_can_complete_after_an_early_page_visit(monkeypatch):
    now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    events = [
        _lesson_result(at=now + timedelta(minutes=1)),
        _lesson_result(
            at=now + timedelta(days=1),
            application=True,
            missed=True,
        ),
    ]
    journey = [
        {
            "_id": "early-review",
            "user_id": "user-1",
            "baseline_id": "baseline-1",
            "step": "review_served",
            "source_id": "old-game",
            "occurred_at": now,
            "metadata": {"outcome": "authorized_event"},
        },
        {
            "_id": "home",
            "user_id": "user-1",
            "baseline_id": "baseline-1",
            "step": "home_focus_served",
            "source_id": "home",
            "occurred_at": now + timedelta(seconds=1),
            "metadata": {},
        },
        {
            "_id": "opened",
            "user_id": "user-1",
            "baseline_id": "baseline-1",
            "step": "lesson_opened",
            "source_id": "session-1",
            "occurred_at": now + timedelta(seconds=2),
            "metadata": {},
        },
        {
            "_id": "lesson-complete",
            "user_id": "user-1",
            "baseline_id": "baseline-1",
            "step": "lesson_completed",
            "source_id": "session-1",
            "occurred_at": now + timedelta(minutes=2),
            "metadata": {},
        },
        {
            "_id": "later-review",
            "user_id": "user-1",
            "baseline_id": "baseline-1",
            "step": "review_served",
            "source_id": "new-game",
            "occurred_at": now + timedelta(minutes=3),
            "metadata": {"outcome": "authorized_event"},
        },
    ]
    db = _db(now=now, events=events, journey=journey)
    for key, value in {
        "COMPLETE_COACHING_SYSTEM_V1_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT": "validation",
    }.items():
        monkeypatch.setenv(key, value)

    async def mastery(*_args, **_kwargs):
        return {"state": "learning", "current_demonstrated_checkpoint": 5}

    monkeypatch.setattr(
        "services.concept_mastery_service.get_pic_mastery_projection",
        mastery,
    )
    before = await build_phase8_journey_projection(db, "user-1")
    identity = before["transfer"]["evidence_identity"]
    db[JOURNEY_COLLECTION].rows.append({
        "_id": "verdict",
        "user_id": "user-1",
        "baseline_id": "baseline-1",
        "step": "progress_verdict_served",
        "source_id": f"focus-1:{identity}",
        "occurred_at": now + timedelta(days=1, minutes=1),
        "metadata": {
            "verdict": "still_recurring",
            "evidence_identity": identity,
        },
    })

    projection = await build_phase8_journey_projection(db, "user-1")
    assert projection["sequence_valid"] is True
    assert projection["complete"] is True
