"""Canonical rollout and version contract for Play with Coach.

This module does not decide chess, choose a focus, or render coaching text.
It answers one product question: which Play with Coach experience may this
user start?  Active sessions store the resolved version so a flag change
cannot swap interaction controllers in the middle of a game.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping


LEGACY_EXPERIENCE = "legacy"
UNIFIED_V1_EXPERIENCE = "unified_v1"
UNIFIED_V1_FEATURE_KEY = "pwc_unified_experience_v1"
PWC_V2_SHADOW_FEATURE_KEY = "pwc_v2_shadow"


def _flag_enabled() -> bool:
    return (
        os.environ.get("PWC_UNIFIED_EXPERIENCE_V1_ENABLED", "false").lower()
        == "true"
    )


def _rollout_roles() -> set[str]:
    raw = os.environ.get(
        "PWC_UNIFIED_EXPERIENCE_V1_ROLES",
        "admin,super_admin",
    )
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _v2_shadow_flag_enabled() -> bool:
    return os.environ.get("PWC_V2_SHADOW_ENABLED", "false").lower() == "true"


def _v2_shadow_rollout_roles() -> set[str]:
    raw = os.environ.get("PWC_V2_SHADOW_ROLES", "admin,super_admin")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def pwc_v2_shadow_eligible(user_doc: Mapping[str, Any] | None) -> bool:
    """Admit read-only V2 comparison without changing the live experience.

    This is intentionally separate from ``preferred_experience_version``.
    Shadow eligibility may record policy comparisons on an existing Unified V1
    turn, but it can never make the browser request or render a V2 runtime.
    """
    if not _v2_shadow_flag_enabled():
        return False

    user_doc = user_doc or {}
    feature_flags = user_doc.get("feature_flags") or {}
    explicit = feature_flags.get(PWC_V2_SHADOW_FEATURE_KEY)
    if explicit is False:
        return False
    if explicit is True:
        return True

    role = str(user_doc.get("role") or "user").strip().lower()
    return role in _v2_shadow_rollout_roles()


def unified_v1_eligible(user_doc: Mapping[str, Any] | None) -> bool:
    """Return eligibility under the global kill switch and user rollout.

    An explicit per-user False always opts out.  An explicit True admits a
    user only while the global kill switch is on.  Otherwise the role cohort
    controls admission.
    """
    if not _flag_enabled():
        return False

    user_doc = user_doc or {}
    feature_flags = user_doc.get("feature_flags") or {}
    explicit = feature_flags.get(UNIFIED_V1_FEATURE_KEY)
    if explicit is False:
        return False
    if explicit is True:
        return True

    role = str(user_doc.get("role") or "user").strip().lower()
    return role in _rollout_roles()


def preferred_experience_version(
    user_doc: Mapping[str, Any] | None,
) -> str:
    return (
        UNIFIED_V1_EXPERIENCE
        if unified_v1_eligible(user_doc)
        else LEGACY_EXPERIENCE
    )


def resolve_requested_experience_version(
    requested: Any,
    user_doc: Mapping[str, Any] | None,
) -> str:
    """Resolve a start request without changing legacy clients implicitly."""
    requested_value = str(requested or LEGACY_EXPERIENCE).strip().lower()
    if requested_value == LEGACY_EXPERIENCE:
        return LEGACY_EXPERIENCE
    if requested_value != UNIFIED_V1_EXPERIENCE:
        raise ValueError("unknown Play with Coach experience version")
    if not unified_v1_eligible(user_doc):
        raise PermissionError("unified Play with Coach is not enabled")
    return UNIFIED_V1_EXPERIENCE


async def build_experience_config(
    db: Any,
    user_id: str,
) -> Dict[str, Any]:
    """Build the pre-setup capability response from canonical services."""
    user_doc = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "role": 1, "feature_flags": 1},
    )
    version = preferred_experience_version(user_doc)

    from subscription_service import can_start_pwc_session

    coach_access = await can_start_pwc_session(db, user_id)
    coaching_context = None
    if version == UNIFIED_V1_EXPERIENCE:
        from services.focus_bridge import build_coaching_context

        coaching_context = await build_coaching_context(
            db,
            user_id,
            surface="coach_play",
        )

    return {
        "experience_version": version,
        "unified_enabled": version == UNIFIED_V1_EXPERIENCE,
        "defaults": {
            "user_color": "white",
            "time_control": "15+10",
        },
        "access": {
            "coach": coach_access,
            "play": {
                "allowed": True,
                "reason": None,
            },
        },
        "coaching_context": coaching_context,
    }


__all__ = [
    "LEGACY_EXPERIENCE",
    "UNIFIED_V1_EXPERIENCE",
    "UNIFIED_V1_FEATURE_KEY",
    "PWC_V2_SHADOW_FEATURE_KEY",
    "build_experience_config",
    "preferred_experience_version",
    "resolve_requested_experience_version",
    "pwc_v2_shadow_eligible",
    "unified_v1_eligible",
]
