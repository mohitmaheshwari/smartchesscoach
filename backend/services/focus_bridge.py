"""
Focus Bridge — the ONE reader for a user's active weakness focus.

Before this bridge existed, four rival "current focus" sources lived in the
codebase (users.focus, coach_memory.learning.current_focus,
player_identity_engine, and primary_weakness_picker.user_active_focus).
HomePage showed one thing, Play with Coach used another, and nothing
reconciled them.

This module is the single canonical read. Every surface that needs to
know "what is the user working on?" calls `get_active_focus_bundle()`.

The bundle shape is deliberately rich so consumers don't need to reach
back into MongoDB — session goal derivation, coach greetings, and mission
scoreboards all read the same struct.
"""
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


COLLECTION = "user_active_focus"

# Sprint 2 (docs/one_surviving_instruction_scope.md, Correction #7):
# instruction_id/instruction_text/instruction_version may ONLY reach
# admin/super_admin accounts while Experiment #1 (Universal Habit Coach,
# docs/experiment_01_habit_coach_scaleup_preregistration.md) is active --
# not any real-user cohort, including Cohort C. Gated HERE, the single
# reader every consumer goes through, so no call site can accidentally
# see these fields for an ineligible user -- there's nothing downstream
# to forget to check.
_INSTRUCTION_ROLLOUT_ROLES = ("admin", "super_admin")


def _instruction_flag_enabled() -> bool:
    return os.environ.get("PWC_SURVIVING_INSTRUCTION_ENABLED", "false").lower() == "true"


def _instruction_fields_eligible(user_role: Optional[str]) -> bool:
    return _instruction_flag_enabled() and user_role in _INSTRUCTION_ROLLOUT_ROLES


async def get_instruction_eligibility_state(db, user_id: str) -> Dict[str, Any]:
    """Explicit flag/role telemetry (2026-08-08, external review of
    b0105f21) -- the scope required 'telemetry for flag state and
    eligibility,' which pwc_insight_shown's instruction_id/
    is_carried_forward alone don't distinguish (null could mean flag
    off, wrong role, or simply no active focus -- three different
    things, one signal). Callers that want to log WHY a user did or
    didn't see Sprint 2 output call this directly."""
    flag_enabled = _instruction_flag_enabled()
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "role": 1})
    role = (user_doc or {}).get("role")
    role_eligible = role in _INSTRUCTION_ROLLOUT_ROLES
    return {
        "flag_enabled": flag_enabled,
        "role_eligible": role_eligible,
        "instruction_eligible": flag_enabled and role_eligible,
    }


async def get_active_focus_bundle(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Return the user's currently-active WEAKNESS focus in a stable shape,
    or None if they don't have one.

    Consumers:
      - services.session_goal_service (Play with Coach mission)
      - services.session_greeting_service (warm greeting on session start)
      - coach_play.coach_game_session (MissionScoreboard population)
      - routes.coach.get_active_focus (HomePage FocusCard)
      - routes.home.get_dashboard_v2 (focus_day_grid + banner)

    Shape (keys are stable — do NOT rename without updating all consumers):
        {
          "topic_key": str,                    # e.g. "time_management" | "king_safety"
          "topic_label": str,                  # human coaching label
          "coaching_narrative": str,           # evidence-driven narrative
          "subtype_histogram": {subtype: {count, dominant_severity}, ...},
          "dominant_subtype": str,             # top meaningful subtype
          "days_remaining": int,               # locked_until - now, in days
          "days_into_focus": int,              # started_at - now, in days
          "baseline_metric": {value, name, occurrence_count, n_games_at_baseline},
          "started_at": str,                   # ISO
          "locked_until": str,                 # ISO
          "moments_page_topic": str,           # → /coach/moments/<key>
          "runners_up": [...],
          # Sprint 2 (docs/one_surviving_instruction_scope.md) -- the
          # canonical instruction identity, set once at assign_focus() and
          # never regenerated. Consumers must read these fresh from here
          # every time, never from a prior session's own stored snapshot.
          "instruction_id": Optional[str],
          "instruction_text": Optional[str],
          "instruction_version": Optional[int],
        }
    """
    focus = await db[COLLECTION].find_one(
        {"user_id": user_id, "status": "active",
         "$or": [{"type": {"$exists": False}}, {"type": "weakness"}]},
        {"_id": 0},
    )
    if not focus:
        return None

    days_remaining = _days_between(focus.get("locked_until"), datetime.now(timezone.utc))
    days_into_focus = _days_between(datetime.now(timezone.utc), focus.get("started_at"))

    dominant_subtype = _pick_dominant_subtype(focus.get("subtype_histogram") or {})

    # Sprint 2 rollout gate (Correction #7) -- checked here, once, for
    # every consumer. A cheap, targeted lookup; role is small enough on
    # the users collection that this doesn't need caching.
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "role": 1})
    eligible = _instruction_fields_eligible((user_doc or {}).get("role"))
    instruction_id = focus.get("instruction_id") if eligible else None
    instruction_text = focus.get("instruction_text") if eligible else None
    instruction_version = focus.get("instruction_version") if eligible else None

    return {
        "topic_key": focus.get("topic_key"),
        "topic_label": focus.get("coaching_label") or (focus.get("topic_key") or "").replace("_", " ").title(),
        "coaching_narrative": focus.get("coaching_narrative"),
        "subtype_histogram": focus.get("subtype_histogram") or {},
        "dominant_subtype": dominant_subtype,
        "days_remaining": days_remaining,
        "days_into_focus": days_into_focus,
        "baseline_metric": focus.get("baseline_metric"),
        "started_at": focus.get("started_at"),
        "locked_until": focus.get("locked_until"),
        "moments_page_topic": focus.get("moments_page_topic") or "piece_safety",
        "runners_up": focus.get("runners_up") or [],
        "rating_band": focus.get("rating_band"),
        "instruction_id": instruction_id,
        "instruction_text": instruction_text,
        "instruction_version": instruction_version,
    }


def _days_between(a, b) -> Optional[int]:
    """Return floor((a - b) as days). a and b can be ISO strings or datetime.
    Returns None if either is unparseable."""
    a_dt = _to_dt(a)
    b_dt = _to_dt(b)
    if a_dt is None or b_dt is None:
        return None
    return max(0, (a_dt - b_dt).days)


def _to_dt(x):
    if x is None:
        return None
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    if isinstance(x, str):
        try:
            return datetime.fromisoformat(x.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _pick_dominant_subtype(hist: Dict[str, Any]) -> Optional[str]:
    """Pick the highest-count MEANINGFUL subtype (excluding 'small_slip'
    and unverified_hint noise buckets)."""
    if not hist:
        return None
    meaningful = {
        st: d for st, d in hist.items()
        if st not in ("small_slip", "unverified_hint") and isinstance(d, dict)
    }
    pool = meaningful or hist
    return max(pool.items(), key=lambda kv: kv[1].get("count", 0))[0] if pool else None


async def get_active_strength_bundle(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Companion reader for the user's active STRENGTH focus. Same collection,
    filtered by type='strength'. Returns None if unassigned."""
    s = await db[COLLECTION].find_one(
        {"user_id": user_id, "status": "active", "type": "strength"},
        {"_id": 0},
    )
    if not s:
        return None
    return {
        "label": s.get("label"),
        "narrative": s.get("narrative"),
        "kind": s.get("kind"),
        "metric_key": s.get("metric_key"),
        "user_value": s.get("user_value"),
        "cohort_mean": s.get("cohort_mean"),
        "z_score": s.get("z_score"),
    }
