"""The candidate experience must reach exactly one account, not one role.

A role gate was considered and rejected on evidence: production carries TWO
super_admins and ONE admin, so gating on role would have exposed the unfinished
experience to three privileged accounts. Measured 2026-09-11:

    validation_compare: true  -> 1  (the validation account)
    super_admin accounts      -> 2
    admin accounts            -> 1
    enabled-but-not-compare   -> 40 (the Phase 8 pilot cohort)

So the three environment variables are GLOBAL KILL SWITCHES only, and audience
is the existing personalized-review validation enrollment. Both must be true.

Every gate consumes one shared resolver; no service re-implements the rule.
"""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.candidate_caption_evidence import (  # noqa: E402
    ENRICHMENT_FLAG,
    LESSON_FLAG,
    VISIBLE_FLAG,
    candidate_experience_allowed,
    candidate_experience_allowed_sync,
    user_document_is_enrolled,
)

ALL_FLAGS = (ENRICHMENT_FLAG, VISIBLE_FLAG, LESSON_FLAG)

VALIDATOR = {
    "user_id": "user_8b599930d7ef",
    "role": "super_admin",
    "feature_flags": {
        "personalized_game_review_coach": {"enabled": True, "validation_compare": True}
    },
}
OTHER_SUPER_ADMIN = {
    "user_id": "user_other_super",
    "role": "super_admin",
    "feature_flags": {"personalized_game_review_coach": {"enabled": True}},
}
ADMIN = {
    "user_id": "user_admin",
    "role": "admin",
    "feature_flags": {},
}
PHASE8_PILOT = {
    "user_id": "user_pilot",
    "role": "user",
    "feature_flags": {
        "personalized_game_review_coach": {"enabled": True, "validation_compare": False}
    },
}
POPULATION = {u["user_id"]: u for u in (VALIDATOR, OTHER_SUPER_ADMIN, ADMIN, PHASE8_PILOT)}


class _Users:
    def __init__(self, population):
        self.population = population

    def find_one(self, query, projection=None):
        return self.population.get(query.get("user_id"))


class _AsyncUsers(_Users):
    async def find_one(self, query, projection=None):
        return self.population.get(query.get("user_id"))


class _DB:
    def __init__(self, async_mode=True, population=None):
        pop = POPULATION if population is None else population
        self.users = (_AsyncUsers if async_mode else _Users)(pop)


@pytest.fixture
def flags_on(monkeypatch):
    for name in ALL_FLAGS:
        monkeypatch.setenv(name, "true")


@pytest.fixture
def flags_off(monkeypatch):
    for name in ALL_FLAGS:
        monkeypatch.setenv(name, "false")


# 1 -- the enrolled validation account receives the feature -------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ALL_FLAGS)
async def test_the_enrolled_validation_account_receives_the_feature(flags_on, flag):
    assert await candidate_experience_allowed(_DB(), VALIDATOR["user_id"], flag) is True


# 2 -- another super_admin does not -------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ALL_FLAGS)
async def test_another_super_admin_does_not(flags_on, flag):
    allowed = await candidate_experience_allowed(
        _DB(), OTHER_SUPER_ADMIN["user_id"], flag
    )
    assert allowed is False, (
        "a second super_admin must not inherit the candidate experience, which "
        "is exactly what a role gate would have got wrong"
    )


# 3 -- an admin does not -------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ALL_FLAGS)
async def test_an_admin_does_not(flags_on, flag):
    assert await candidate_experience_allowed(_DB(), ADMIN["user_id"], flag) is False


# 4 -- an ordinary enrolled Phase 8 user does not ------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ALL_FLAGS)
async def test_an_ordinary_enrolled_phase8_user_does_not(flags_on, flag):
    allowed = await candidate_experience_allowed(_DB(), PHASE8_PILOT["user_id"], flag)
    assert allowed is False, (
        "40 pilot users carry enabled:true without validation_compare, and they "
        "must keep legacy behaviour"
    )


# 5 -- missing or invalid identity fails closed --------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, "", "   ", "user_does_not_exist", 0])
async def test_missing_or_invalid_identity_fails_closed(flags_on, bad):
    assert await candidate_experience_allowed(_DB(), bad, VISIBLE_FLAG) is False


@pytest.mark.asyncio
async def test_absent_database_fails_closed(flags_on):
    allowed = await candidate_experience_allowed(None, VALIDATOR["user_id"], VISIBLE_FLAG)
    assert allowed is False


@pytest.mark.asyncio
async def test_a_database_error_fails_closed(flags_on):
    class _Boom:
        class users:
            @staticmethod
            async def find_one(*args, **kwargs):
                raise RuntimeError("mongo down")

    allowed = await candidate_experience_allowed(
        _Boom(), VALIDATOR["user_id"], VISIBLE_FLAG
    )
    assert allowed is False


@pytest.mark.parametrize(
    "doc",
    [
        None,
        {},
        {"feature_flags": None},
        {"feature_flags": {}},
        {"feature_flags": {"personalized_game_review_coach": None}},
        {"feature_flags": {"personalized_game_review_coach": "yes"}},
        {"feature_flags": {"personalized_game_review_coach": {"validation_compare": True}}},
        {"feature_flags": {"personalized_game_review_coach": {"enabled": True}}},
        {
            "feature_flags": {
                "personalized_game_review_coach": {
                    "enabled": True,
                    "validation_compare": "true",
                }
            }
        },
    ],
)
def test_the_enrollment_predicate_never_guesses_yes(doc):
    assert user_document_is_enrolled(doc) is False


# 6 -- all behaviour is legacy when the global flag is off ---------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ALL_FLAGS)
async def test_everything_is_legacy_when_the_kill_switch_is_off(flags_off, flag):
    for uid in POPULATION:
        allowed = await candidate_experience_allowed(_DB(), uid, flag)
        assert allowed is False, (
            f"{uid} got the feature with {flag} off, so the env var is no longer "
            "an absolute kill switch"
        )


@pytest.mark.asyncio
async def test_an_unset_flag_is_off(monkeypatch):
    for name in ALL_FLAGS:
        monkeypatch.delenv(name, raising=False)
    allowed = await candidate_experience_allowed(
        _DB(), VALIDATOR["user_id"], VISIBLE_FLAG
    )
    assert allowed is False


# 7 -- background analysis agrees with request time ----------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("uid", sorted(POPULATION))
async def test_background_worker_agrees_with_request_time(flags_on, uid):
    """The sync worker path and the async route path must never disagree.

    If they did, the worker would write candidate evidence for accounts the
    routes will never show it to, or withhold it from the one that can.
    """
    request_time = await candidate_experience_allowed(_DB(True), uid, ENRICHMENT_FLAG)
    background = candidate_experience_allowed_sync(_DB(False), uid, ENRICHMENT_FLAG)
    assert request_time == background, (
        f"{uid}: route says {request_time}, worker says {background}"
    )
    assert background is (uid == VALIDATOR["user_id"])


def test_exactly_one_account_in_a_realistic_population(flags_on):
    eligible = [
        uid
        for uid in POPULATION
        if candidate_experience_allowed_sync(_DB(False), uid, VISIBLE_FLAG)
    ]
    assert eligible == [VALIDATOR["user_id"]], f"expected one validator, got {eligible}"
