import pytest
from pathlib import Path

from services.complete_coaching_access import (
    BASELINE_COLLECTION,
    BASELINE_VERSION,
    PAUSED_MESSAGE,
    TARGET_COLLECTION,
    TARGET_LOCK_ID,
    get_complete_coaching_access,
    requested_complete_coaching_access,
)


ENV = {
    "COMPLETE_COACHING_SYSTEM_V1_ENABLED": "true",
    "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
    "PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT": "validation",
}
USER = {
    "user_id": "user-1",
    "role": "user",
    "feature_flags": {
        "personalized_game_review_coach": {
            "enabled": True,
            "cohort": "phase8_release_rescue_2026_09",
        }
    },
}


class _Collection:
    def __init__(self, rows=()):
        self.rows = list(rows)

    async def find_one(self, query, projection=None):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                if projection:
                    return {
                        key: value
                        for key, value in row.items()
                        if projection.get(key)
                    }
                return dict(row)
        return None


class _Db:
    def __init__(self, *, target=True, baseline=True):
        self.users = _Collection([USER])
        self.collections = {
            TARGET_COLLECTION: _Collection([
                {
                    "_id": TARGET_LOCK_ID,
                    "status": "locked",
                    "contract_version": "phase8_reach_target.v1",
                }
            ] if target else []),
            BASELINE_COLLECTION: _Collection([
                {
                    "_id": "baseline-1",
                    "user_id": "user-1",
                    "baseline_version": BASELINE_VERSION,
                    "target_lock_id": TARGET_LOCK_ID,
                }
            ] if baseline else []),
        }

    def __getitem__(self, name):
        return self.collections[name]


def test_pure_access_reuses_existing_review_enrollment_and_complete_flag():
    access = requested_complete_coaching_access(USER, ENV)
    assert access.requested is True
    assert access.enabled is False
    assert access.cohort == "phase8_release_rescue_2026_09"


@pytest.mark.asyncio
async def test_access_requires_both_target_lock_and_immutable_baseline():
    no_target = await get_complete_coaching_access(
        _Db(target=False), "user-1", user_doc=USER, env=ENV
    )
    assert no_target.enabled is False
    assert no_target.reason == "target_not_locked"

    no_baseline = await get_complete_coaching_access(
        _Db(baseline=False), "user-1", user_doc=USER, env=ENV
    )
    assert no_baseline.enabled is False
    assert no_baseline.reason == "baseline_missing"

    enabled = await get_complete_coaching_access(
        _Db(), "user-1", user_doc=USER, env=ENV
    )
    assert enabled.enabled is True
    assert enabled.reason == "enabled"
    assert enabled.baseline_id == "baseline-1"


@pytest.mark.asyncio
async def test_paused_user_keeps_an_explicit_saved_work_message():
    paused_user = {
        **USER,
        "feature_flags": {
            "personalized_game_review_coach": {
                "enabled": False,
                "cohort": "phase8_release_rescue_2026_09",
            }
        },
    }
    paused = await get_complete_coaching_access(
        _Db(), "user-1", user_doc=paused_user, env=ENV
    )
    assert paused.enabled is False
    assert paused.paused is True
    assert paused.public_dict()["message"] == PAUSED_MESSAGE


def test_role_alone_never_enrolls_a_real_user():
    admin = {"user_id": "admin-1", "role": "admin", "feature_flags": {}}
    access = requested_complete_coaching_access(admin, ENV)
    assert access.requested is False
    assert access.reason == "not_enrolled"


def test_complete_coaching_flag_is_forwarded_by_compose():
    compose = (
        Path(__file__).resolve().parents[2] / "docker-compose.yml"
    ).read_text(encoding="utf-8")
    assert (
        "COMPLETE_COACHING_SYSTEM_V1_ENABLED="
        "${COMPLETE_COACHING_SYSTEM_V1_ENABLED:-false}"
    ) in compose
