"""One fail-closed access decision for the Phase 8 coaching journey.

The service composes existing switches. It does not own a new cohort list:
the existing personalized-review enrollment remains the per-user authority,
while the complete-system flag, frozen reach target and immutable baseline
prove that Phase 8 is safe to expose.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, Mapping, Optional

from services.concept_contract_registry import complete_coaching_system_enabled
from services.game_review_contracts import (
    USER_FEATURE_FLAG,
    personalized_game_review_access,
)


SCHEMA_VERSION = "complete_coaching_access.v1"
TARGET_LOCK_ID = "phase8_reach_target.v1"
BASELINE_VERSION = "phase8_pre_enrollment.v1"
TARGET_COLLECTION = "complete_coaching_release_state"
BASELINE_COLLECTION = "complete_coaching_baselines"
PAUSED_MESSAGE = (
    "Your lesson and progress are saved. "
    "Your coach is preparing the next step."
)


@dataclass(frozen=True)
class CompleteCoachingAccess:
    enabled: bool
    paused: bool
    requested: bool
    reason: str
    cohort: Optional[str]
    rollout_mode: str
    comparison_allowed: bool
    target_lock_id: Optional[str] = None
    baseline_id: Optional[str] = None

    def public_dict(self) -> Dict[str, Any]:
        result = {
            "schema_version": SCHEMA_VERSION,
            "enabled": self.enabled,
            "eligible": self.enabled,
            "paused": self.paused,
            "reason": self.reason,
            "cohort": self.cohort,
            "rollout_mode": self.rollout_mode,
            "comparison_allowed": self.comparison_allowed,
        }
        if self.paused:
            result["message"] = PAUSED_MESSAGE
        return result


def _user_enrollment(user_doc: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    flags = ((user_doc or {}).get("feature_flags") or {}).get(
        USER_FEATURE_FLAG
    ) or {}
    return flags if isinstance(flags, Mapping) else {}


def requested_complete_coaching_access(
    user_doc: Optional[Mapping[str, Any]],
    env: Optional[Mapping[str, str]] = None,
) -> CompleteCoachingAccess:
    """Resolve switches only; database prerequisites are checked asynchronously."""
    source = os.environ if env is None else env
    enrollment = _user_enrollment(user_doc)
    review = personalized_game_review_access(user_doc, source)
    explicitly_enrolled = enrollment.get("enabled") is True
    selected = bool(
        review.enabled
        and (review.rollout_mode == "all" or explicitly_enrolled)
    )
    composition_enabled = complete_coaching_system_enabled(source)
    requested = bool(composition_enabled and selected)
    cohort = str(
        enrollment.get("cohort")
        or ("all" if review.rollout_mode == "all" and selected else "")
    ) or None
    if requested:
        reason = "prerequisites_pending"
    elif not composition_enabled:
        reason = "composition_disabled"
    elif review.rollout_mode == "invalid":
        reason = "invalid_review_rollout"
    elif not review.enabled:
        reason = "not_enrolled"
    else:
        reason = "not_selected"
    return CompleteCoachingAccess(
        enabled=False,
        paused=False,
        requested=requested,
        reason=reason,
        cohort=cohort,
        rollout_mode=review.rollout_mode,
        comparison_allowed=review.comparison_allowed,
    )


async def get_complete_coaching_access(
    db,
    user_id: str,
    *,
    user_doc: Optional[Mapping[str, Any]] = None,
    env: Optional[Mapping[str, str]] = None,
) -> CompleteCoachingAccess:
    """Require the frozen target and immutable user baseline before access."""
    if user_doc is None:
        user_doc = await db.users.find_one(
            {"user_id": user_id},
            {"_id": 0, "role": 1, "feature_flags": 1},
        )
    request = requested_complete_coaching_access(user_doc, env)
    enrollment = _user_enrollment(user_doc)
    if not request.requested and not request.cohort:
        return request

    target = await db[TARGET_COLLECTION].find_one(
        {"_id": TARGET_LOCK_ID, "status": "locked"},
        {"_id": 1, "contract_version": 1},
    )
    baseline = None
    if target:
        baseline = await db[BASELINE_COLLECTION].find_one(
            {
                "user_id": user_id,
                "baseline_version": BASELINE_VERSION,
                "target_lock_id": TARGET_LOCK_ID,
            },
            {"_id": 1},
        )

    if request.requested and not target:
        return CompleteCoachingAccess(
            **{
                **request.__dict__,
                "reason": "target_not_locked",
            }
        )
    if request.requested and not baseline:
        return CompleteCoachingAccess(
            **{
                **request.__dict__,
                "reason": "baseline_missing",
                "target_lock_id": TARGET_LOCK_ID,
            }
        )
    if request.requested:
        return CompleteCoachingAccess(
            enabled=True,
            paused=False,
            requested=True,
            reason="enabled",
            cohort=request.cohort,
            rollout_mode=request.rollout_mode,
            comparison_allowed=request.comparison_allowed,
            target_lock_id=TARGET_LOCK_ID,
            baseline_id=str(baseline.get("_id")),
        )

    had_phase8_state = bool(
        target
        and baseline
        and enrollment.get("cohort")
    )
    return CompleteCoachingAccess(
        enabled=False,
        paused=had_phase8_state,
        requested=False,
        reason="paused" if had_phase8_state else request.reason,
        cohort=request.cohort,
        rollout_mode=request.rollout_mode,
        comparison_allowed=False,
        target_lock_id=TARGET_LOCK_ID if target else None,
        baseline_id=str(baseline.get("_id")) if baseline else None,
    )


__all__ = [
    "BASELINE_COLLECTION",
    "BASELINE_VERSION",
    "CompleteCoachingAccess",
    "PAUSED_MESSAGE",
    "SCHEMA_VERSION",
    "TARGET_COLLECTION",
    "TARGET_LOCK_ID",
    "get_complete_coaching_access",
    "requested_complete_coaching_access",
]
