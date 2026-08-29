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
PIC_FACT_VERSION = "piece_safety.d_live.v1"
COACHING_CONTEXT_SCHEMA_VERSION = "coaching_context.v1"
COACHING_CONTEXT_SURFACES = frozenset({"home", "review", "training", "coach_play"})
COACHING_CONTEXT_STATES = frozenset({
    "no_focus",
    "primary_only",
    "primary_with_support",
    "evidence_pending",
    "pic_outcome",
})


def _instruction_flag_enabled() -> bool:
    return os.environ.get("PWC_SURVIVING_INSTRUCTION_ENABLED", "false").lower() == "true"


def _pic_flag_enabled() -> bool:
    return os.environ.get(
        "PERSONAL_IMPROVEMENT_CYCLE_ENABLED", "false"
    ).lower() == "true"


def _coaching_context_flag_enabled() -> bool:
    return os.environ.get(
        "COACHING_CONTEXT_V1_ENABLED", "false"
    ).lower() == "true"


def _coaching_context_rollout_roles() -> set[str]:
    raw = os.environ.get(
        "COACHING_CONTEXT_V1_ROLES", "admin,super_admin"
    )
    return {role.strip() for role in raw.split(",") if role.strip()}


def _pic_rollout_roles() -> set[str]:
    raw = os.environ.get(
        "PERSONAL_IMPROVEMENT_CYCLE_ROLES", "admin,super_admin"
    )
    return {role.strip() for role in raw.split(",") if role.strip()}


def _pic_fields_eligible(user_role: Optional[str]) -> bool:
    return _pic_flag_enabled() and user_role in _pic_rollout_roles()


def _instruction_fields_eligible(user_role: Optional[str]) -> bool:
    pwc_eligible = (
        _instruction_flag_enabled()
        and user_role in _INSTRUCTION_ROLLOUT_ROLES
    )
    context_eligible = (
        _coaching_context_flag_enabled()
        and user_role in _coaching_context_rollout_roles()
    )
    return pwc_eligible or _pic_fields_eligible(user_role) or context_eligible


async def get_instruction_eligibility_state(db, user_id: str) -> Dict[str, Any]:
    """Explicit flag/role telemetry (2026-08-08, external review of
    b0105f21) -- the scope required 'telemetry for flag state and
    eligibility,' which pwc_insight_shown's instruction_id/
    is_carried_forward alone don't distinguish (null could mean flag
    off, wrong role, or simply no active focus -- three different
    things, one signal). Callers that want to log WHY a user did or
    didn't see Sprint 2 output call this directly."""
    pwc_flag_enabled = _instruction_flag_enabled()
    pic_flag_enabled = _pic_flag_enabled()
    flag_enabled = pwc_flag_enabled or pic_flag_enabled
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "role": 1})
    role = (user_doc or {}).get("role")
    role_eligible = role in _INSTRUCTION_ROLLOUT_ROLES
    return {
        "flag_enabled": flag_enabled,
        "pwc_flag_enabled": pwc_flag_enabled,
        "pic_flag_enabled": pic_flag_enabled,
        "role_eligible": role_eligible,
        "instruction_eligible": _instruction_fields_eligible(role),
    }


async def get_d_live_evidence_summary(
    db, user_id: str, game_ids: Optional[list[str]] = None
) -> Dict[str, int]:
    """Aggregate exact-version D_live facts without reading pre-SEE residue."""
    if game_ids is not None and not game_ids:
        return {"decisions": 0, "misses": 0, "handled": 0}
    match: Dict[str, Any] = {
        "user_id": user_id,
        "schema_version": {"$gte": 16},
        "piece_safety_decision.version": PIC_FACT_VERSION,
        "piece_safety_decision.derivation_status": "ok",
        "piece_safety_decision.eligible": True,
    }
    if game_ids is not None:
        match["game_id"] = {"$in": game_ids}
    rows = await db.move_observations.aggregate([
        {"$match": match},
        {"$group": {
            "_id": None,
            "decisions": {"$sum": 1},
            "misses": {"$sum": {
                "$cond": [
                    {"$eq": ["$piece_safety_decision.outcome", "miss"]},
                    1,
                    0,
                ]
            }},
        }},
    ]).to_list(length=1)
    if not rows:
        return {"decisions": 0, "misses": 0, "handled": 0}
    decisions = int(rows[0].get("decisions") or 0)
    misses = int(rows[0].get("misses") or 0)
    return {
        "decisions": decisions,
        "misses": misses,
        "handled": max(0, decisions - misses),
    }


async def get_pic_focus_projection(
    db,
    user_id: str,
    focus: Optional[Dict[str, Any]] = None,
    user_role: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the default-off PIC presentation model from canonical sources."""
    if not _pic_flag_enabled():
        return None
    if user_role is None:
        user_doc = await db.users.find_one(
            {"user_id": user_id}, {"_id": 0, "role": 1}
        )
        user_role = (user_doc or {}).get("role")
    if not _pic_fields_eligible(user_role):
        return None
    if focus is None:
        focus = await db[COLLECTION].find_one(
            {
                "user_id": user_id,
                "status": "active",
                "$or": [
                    {"type": {"$exists": False}},
                    {"type": "weakness"},
                ],
            },
            {"_id": 0},
        )
    if not focus or focus.get("topic_key") != "piece_safety":
        return {
            "enabled": True,
            "eligible": False,
            "state": "not_eligible",
            "reason": "piece_safety_focus_required",
        }

    diagnosis_query = {
        "user_id": user_id,
        "schema_version": {"$gte": 16},
        "missed_pattern": "piece_safety",
        "subtype": "simple_hang",
    }
    diagnosis_count = await db.move_observations.count_documents(diagnosis_query)
    example_cursor = db.move_observations.find(
        diagnosis_query,
        {
            "_id": 0,
            "game_id": 1,
            "move_number": 1,
            "move_san": 1,
            "fen_before": 1,
        },
    ).sort("derived_at", -1).limit(2)
    examples = await example_cursor.to_list(length=2)

    all_available = await get_d_live_evidence_summary(db, user_id)
    started_dt = _to_dt(focus.get("started_at"))
    recent_game_ids: list[str] = []
    if started_dt is not None:
        recent_game_ids = await db.games.distinct(
            "game_id",
            {
                "user_id": user_id,
                "is_analyzed": True,
                "date_played": {"$gte": started_dt.isoformat()},
            },
        )
    recent = await get_d_live_evidence_summary(db, user_id, recent_game_ids)
    stored_baseline = ((focus.get("evidence_summary") or {}).get("baseline"))
    from services.concept_mastery_service import get_pic_mastery_projection
    learner_state = await get_pic_mastery_projection(
        db,
        user_id,
        diagnosed=diagnosis_count > 0,
    )

    if diagnosis_count <= 0:
        state = "not_eligible"
        next_action = {"type": "review", "label": "Review your latest game", "href": "/lab"}
    elif recent["decisions"] <= 0:
        state = "diagnosed"
        next_action = {"type": "practice", "label": "Practise this", "href": "/training/pattern/piece_safety"}
    else:
        state = "evidence_collected"
        next_action = {"type": "focus_game", "label": "Use this in a real game", "href": "/home"}

    return {
        "enabled": True,
        "eligible": diagnosis_count > 0,
        "cycle_version": 1,
        "focus_kind": "piece_safety/simple_hang",
        "state": state,
        "focus_label": "Keeping your pieces safe",
        "instruction_id": focus.get("instruction_id"),
        "instruction_text": focus.get("instruction_text"),
        "proof_eligibility": focus.get("proof_eligibility") or "verified",
        "focus_game": focus.get("pending_focus_game"),
        "learner_state": learner_state,
        "diagnosis": {
            "detector_id": "move_observation.simple_hang.v16_plus",
            "count": diagnosis_count,
            "examples": examples,
        },
        "evidence": {
            "proof_detector_id": PIC_FACT_VERSION,
            "available": all_available,
            "baseline": stored_baseline,
            "since_focus": recent,
            "verdict": "measurement_pending",
            "message": (
                "We have comparable decisions, but the improvement rule is "
                "not locked yet. No progress claim has been made."
                if recent["decisions"] > 0
                else "No comparable decision evidence since this focus started."
            ),
        },
        "next_action": next_action,
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
    )
    if not focus:
        return None
    from services.detector_quality import focus_document_is_authorized
    if not focus_document_is_authorized(focus):
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
        "focus_id": str(focus.get("_id")) if focus.get("_id") is not None else None,
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
        "detector_quality_id": focus.get("detector_quality_id"),
        "proof_eligibility": focus.get("proof_eligibility"),
        "focus_kind": focus.get("focus_kind"),
        "diagnosis_detector_id": focus.get("diagnosis_detector_id"),
        "evidence_summary": focus.get("evidence_summary"),
        "instruction_id": instruction_id,
        "instruction_text": instruction_text,
        "instruction_version": instruction_version,
    }


def validate_coaching_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Fail closed when a V1 context violates its public contract."""
    required = {
        "schema_version",
        "context_id",
        "surface",
        "state",
        "primary_focus",
        "supporting_focuses",
        "elective",
        "evidence",
        "learner_projection",
        "next_action",
        "rollout",
        "surface_context",
    }
    missing = sorted(required.difference(context))
    if missing:
        raise ValueError(f"coaching context missing fields: {', '.join(missing)}")
    if context["schema_version"] != COACHING_CONTEXT_SCHEMA_VERSION:
        raise ValueError("unknown coaching context schema")
    if context["surface"] not in COACHING_CONTEXT_SURFACES:
        raise ValueError("unknown coaching context surface")
    if context["state"] not in COACHING_CONTEXT_STATES:
        raise ValueError("unknown coaching context state")
    supports = context["supporting_focuses"]
    if not isinstance(supports, list):
        raise ValueError("supporting_focuses must be a list")
    if len(supports) > 1:
        raise ValueError("coaching_context.v1 permits at most one supporting focus")
    if context["state"] == "no_focus" and context["primary_focus"] is not None:
        raise ValueError("no_focus cannot include a primary focus")
    if context["state"] != "no_focus" and context["primary_focus"] is None:
        raise ValueError("focused states require a primary focus")
    return context


def coaching_context_visible_in_mode(
    context: Optional[Dict[str, Any]], game_mode: str
) -> Optional[Dict[str, Any]]:
    """Coach Mode may teach live; Play Mode retains no visible context."""
    return context if game_mode == "coach" else None


def coaching_session_payload_for_mode(
    session_payload: Dict[str, Any], game_mode: str
) -> Dict[str, Any]:
    """Remove live teaching snapshots from the Play Mode browser payload."""
    visible = dict(session_payload)
    if game_mode == "play":
        for field in (
            "coaching_context",
            "mission_scoreboard",
            "session_focus",
            "session_goal",
            "session_greeting",
        ):
            visible[field] = None
    return visible


def _no_focus_surface_context(
    surface: str, game_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    if surface == "review":
        return {
            "game_id": game_id,
            "focus_evidence_state": "unavailable",
            "primary_matches": [],
            "supporting_matches": [],
            "message": "I need a verified focus before comparing this game against it.",
        }
    if surface == "training":
        return {
            "assignment": None,
            "reason": "no_verified_focus",
        }
    return None


def _no_focus_context(
    surface: str,
    reason: str,
    *,
    game_id: Optional[str] = None,
) -> Dict[str, Any]:
    return validate_coaching_context({
        "schema_version": COACHING_CONTEXT_SCHEMA_VERSION,
        "context_id": f"ccv1:no-focus:{reason}",
        "surface": surface,
        "state": "no_focus",
        "primary_focus": None,
        "supporting_focuses": [],
        "elective": None,
        "evidence": {
            "eligibility": "insufficient",
            "verdict": "insufficient_evidence",
            "message": (
                "I need enough verified games before choosing your main focus."
            ),
        },
        "learner_projection": None,
        "next_action": {
            "type": "review",
            "href": "/import",
            "label": "Build my coaching evidence",
        },
        "rollout": {"eligible": True, "reason": reason},
        "surface_context": _no_focus_surface_context(surface, game_id),
    })


def _authorized_supporting_focuses(
    runners_up: list[Dict[str, Any]], primary_topic: Optional[str]
) -> list[Dict[str, Any]]:
    """Project the first strictly Plan-authorized, distinct runner.

    Runners are ranking residue, not authorization. Missing quality identity
    therefore fails closed instead of inheriting the primary detector's grade.
    """
    from services.detector_quality import QualitySurface, is_authorized

    for runner in runners_up:
        if not isinstance(runner, dict):
            continue
        topic = runner.get("topic_key") or runner.get("topic")
        quality_id = runner.get("detector_quality_id")
        if not topic or topic == primary_topic or not quality_id:
            continue
        if not is_authorized(str(quality_id), QualitySurface.PLAN):
            continue
        return [{
            "topic_key": str(topic),
            "label": (
                runner.get("coaching_label")
                or runner.get("label")
                or str(topic).replace("_", " ").title()
            ),
            "detector_quality_id": str(quality_id),
            "evidence_count": runner.get("evidence_count"),
        }]
    return []


def _review_match_payload(
    observation: Dict[str, Any], quality_id: str
) -> Dict[str, Any]:
    return {
        "move_number": observation.get("move_number"),
        "move_san": observation.get("move_san"),
        "severity": observation.get("severity"),
        "topic_key": observation.get("missed_pattern"),
        "subtype": observation.get("subtype"),
        "detector_quality_id": quality_id,
    }


async def _build_review_surface_context(
    db,
    user_id: str,
    game_id: Optional[str],
    primary: Dict[str, Any],
    supports: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """Attach only existing, strictly Plan-authorized move observations."""
    if not game_id:
        return {
            "game_id": None,
            "focus_evidence_state": "not_requested",
            "primary_matches": [],
            "supporting_matches": [],
            "message": "Open a game to compare it with your current focus.",
        }

    rows = await db.move_observations.find(
        {"user_id": user_id, "game_id": game_id},
        {
            "_id": 0,
            "move_number": 1,
            "move_san": 1,
            "missed_pattern": 1,
            "subtype": 1,
            "severity": 1,
        },
    ).to_list(length=None)

    from services.detector_quality import (
        QualitySurface,
        gap_quality_id,
        is_authorized,
    )

    primary_quality_id = primary.get("detector_quality_id")
    support_ids = {
        support.get("detector_quality_id") for support in supports
        if support.get("detector_quality_id")
    }
    primary_matches: list[Dict[str, Any]] = []
    supporting_matches: list[Dict[str, Any]] = []
    seen: set[tuple[Any, str]] = set()
    for observation in rows:
        pattern = observation.get("missed_pattern")
        subtype = observation.get("subtype")
        if not pattern:
            continue
        quality_id = gap_quality_id(
            str(pattern), str(subtype) if subtype else None
        )
        if not is_authorized(quality_id, QualitySurface.PLAN):
            continue
        dedupe_key = (observation.get("move_number"), quality_id)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        payload = _review_match_payload(observation, quality_id)
        if quality_id == primary_quality_id:
            primary_matches.append(payload)
        elif quality_id in support_ids:
            supporting_matches.append(payload)

    sort_key = lambda item: (
        item.get("move_number") is None,
        item.get("move_number") or 0,
    )
    primary_matches.sort(key=sort_key)
    supporting_matches.sort(key=sort_key)

    if primary_matches:
        state = "observed"
        message = (
            "Your current check showed up in this game. Review these moves, "
            "then repeat the same check in later games until it becomes part "
            "of your thinking."
        )
    else:
        state = "not_observed"
        message = (
            "This game did not give us a verified chance to test your focus. "
            "That does not mean the problem is fixed. Keep using the same "
            "check until later games give us real chances to measure it."
        )
    return {
        "game_id": game_id,
        "focus_evidence_state": state,
        "primary_matches": primary_matches,
        "supporting_matches": supporting_matches,
        "message": message,
    }


async def _build_surface_context(
    db,
    user_id: str,
    surface: str,
    game_id: Optional[str],
    primary: Dict[str, Any],
    supports: list[Dict[str, Any]],
    next_action: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if surface == "review":
        return await _build_review_surface_context(
            db, user_id, game_id, primary, supports
        )
    if surface == "training":
        return {
            "assignment": {
                "type": "focus_practice",
                "focus_id": primary.get("focus_id"),
                "instruction_id": primary.get("instruction_id"),
                "instruction_text": primary.get("instruction_text"),
                "href": next_action.get("href"),
                "label": next_action.get("label"),
            }
        }
    return None


async def build_coaching_context(
    db,
    user_id: str,
    *,
    surface: str,
    game_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Build the one default-off cross-surface coaching presentation.

    Focus choice remains owned by ``user_active_focus`` through
    ``get_active_focus_bundle``. This function only validates and presents the
    chosen focus; it never selects a rival priority or creates a verdict.
    """
    if not _coaching_context_flag_enabled():
        return None
    if surface not in COACHING_CONTEXT_SURFACES:
        raise ValueError("unknown coaching context surface")

    user_doc = await db.users.find_one(
        {"user_id": user_id}, {"_id": 0, "role": 1}
    )
    if (user_doc or {}).get("role") not in _coaching_context_rollout_roles():
        return None

    focus = await get_active_focus_bundle(db, user_id)
    if not focus:
        return _no_focus_context(surface, "enabled", game_id=game_id)

    from services.detector_quality import QualitySurface, is_authorized
    quality_id = focus.get("detector_quality_id")
    if not quality_id or not is_authorized(str(quality_id), QualitySurface.PLAN):
        return _no_focus_context(
            surface, "focus_not_plan_authorized", game_id=game_id
        )

    primary = {
        "focus_id": focus.get("focus_id"),
        "topic_key": focus.get("topic_key"),
        "label": focus.get("topic_label"),
        "instruction_id": focus.get("instruction_id"),
        "instruction_text": focus.get("instruction_text"),
        "instruction_version": focus.get("instruction_version"),
        "detector_quality_id": str(quality_id),
    }
    supports = _authorized_supporting_focuses(
        focus.get("runners_up") or [], focus.get("topic_key")
    )
    pic = await get_pic_focus_projection(
        db,
        user_id,
        focus=focus,
    )

    if not primary["instruction_id"] or not primary["instruction_text"]:
        state = "evidence_pending"
        evidence = {
            "eligibility": "verified_focus_missing_instruction",
            "verdict": "measurement_pending",
            "message": (
                "This focus is verified, but it does not yet have a verified "
                "instruction. No teaching claim has been invented."
            ),
        }
        next_action = {
            "type": "review",
            "href": "/lab",
            "label": "Review the evidence",
        }
    else:
        pic_evidence = (pic or {}).get("evidence") or {}
        evidence = {
            "eligibility": (pic or {}).get("proof_eligibility") or "verified",
            "verdict": pic_evidence.get("verdict") or "measurement_pending",
            "message": pic_evidence.get("message") or (
                "Your instruction is ready. Improvement is not claimed until "
                "comparable later-game evidence exists."
            ),
        }
        if pic and evidence["verdict"] not in (None, "measurement_pending"):
            state = "pic_outcome"
        else:
            state = "primary_with_support" if supports else "primary_only"
        next_action = (pic or {}).get("next_action") or {
            "type": "practice",
            "href": f"/training/pattern/{focus.get('topic_key')}",
            "label": "Practise this check",
        }

    focus_id = primary.get("focus_id") or "legacy"
    instruction_id = primary.get("instruction_id") or "pending"
    instruction_version = primary.get("instruction_version") or 0
    context = {
        "schema_version": COACHING_CONTEXT_SCHEMA_VERSION,
        "context_id": (
            f"ccv1:{focus_id}:{instruction_id}:{instruction_version}"
        ),
        "surface": surface,
        "state": state,
        "primary_focus": primary,
        "supporting_focuses": supports,
        "elective": None,
        "evidence": evidence,
        "learner_projection": (pic or {}).get("learner_state"),
        "next_action": next_action,
        "rollout": {"eligible": True, "reason": "enabled"},
        "surface_context": await _build_surface_context(
            db,
            user_id,
            surface,
            game_id,
            primary,
            supports,
            next_action,
        ),
    }
    return validate_coaching_context(context)


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
    if s.get("kind") == "pattern":
        metric_key = str(s.get("metric_key") or "")
        pattern_id = metric_key
        if metric_key.startswith("pattern_") and metric_key.endswith("_rate"):
            pattern_id = metric_key[len("pattern_"):-len("_rate")]
        from services.detector_quality import (
            QualitySurface,
            can_influence,
            shape_quality_id,
        )
        if not can_influence(
            shape_quality_id(pattern_id), QualitySurface.PLAN
        ):
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
