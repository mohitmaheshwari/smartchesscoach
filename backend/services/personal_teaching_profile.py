"""Read-only, evidence-gated teaching profile for one lesson request.

This module adapts delivery, never chess truth. It joins existing owners and
returns provenance for every personal anchor. It performs no database writes
and stores no permanent learner type.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from services.personal_curriculum import HelpAction


TEACHING_PROFILE_SCHEMA_VERSION = "personal_teaching_profile.v1"
ALLOWED_HELP_ACTIONS = tuple(action.value for action in HelpAction)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _skill_records(coach_memory: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    learning = _mapping(coach_memory.get("learning"))
    raw = learning.get("skills") or []
    if isinstance(raw, Mapping):
        return [
            {"skill_id": skill_id, **dict(_mapping(value))}
            for skill_id, value in raw.items()
        ]
    return [item for item in raw if isinstance(item, Mapping)]


def _exact_skill(
    coach_memory: Mapping[str, Any],
    skill_id: str,
) -> Optional[Mapping[str, Any]]:
    for item in _skill_records(coach_memory):
        if str(item.get("skill_id") or "") == skill_id:
            return item
    return None


def _plain_label(value: Any) -> str:
    return str(value or "").strip().replace("_", " ")


_MISCONCEPTION_COPY = {
    "activity_before_safety": (
        "you chose activity before checking whether every piece stayed safe"
    ),
    "piece_safety_relationship_unclear": (
        "you were not yet sure which piece could be taken after your move"
    ),
    "piece_left_unsafe": "one of your pieces was left where it could be taken",
    "expects_immediate_opening_win": (
        "you expected the opening move to win something immediately"
    ),
    "opening_plan_unclear": (
        "the next piece or pawn in your opening plan was not clear yet"
    ),
    "opening_plan_not_recognized": (
        "the next piece or pawn in your opening plan was missed"
    ),
    "attacks_before_answering_threat": (
        "you started your own attack before answering the opponent's threat"
    ),
    "immediate_threat_unclear": (
        "the opponent's immediate check, capture, or threat was not clear yet"
    ),
    "threat_not_identified": "the opponent's immediate threat was missed",
    "check_without_endgame_rule": (
        "you chose a check before applying the rule for this ending"
    ),
    "endgame_rule_unclear": (
        "the needed king, pawn, or rook setup was not clear yet"
    ),
    "endgame_rule_not_applied": "the rule for this ending was not applied",
    "reason_not_given": "you moved without naming what you checked",
    "reason_does_not_match_move": (
        "your move worked, but the reason you chose did not explain why"
    ),
    "board_relationship_missed": (
        "the important piece or square in the position was missed"
    ),
}


def _misconception_copy(value: Any) -> str:
    key = str(value or "").strip()
    return _MISCONCEPTION_COPY.get(key, _plain_label(key))


def _anchor(
    *,
    anchor_type: str,
    message: str,
    owner: str,
    ref: Optional[str],
    strength: str,
    skill_specific: bool,
) -> Dict[str, Any]:
    return {
        "type": anchor_type,
        "message": message,
        "provenance": {
            "owner": owner,
            "ref": ref,
            "strength": strength,
        },
        "skill_specific": skill_specific,
    }


def _help_from_evidence(
    current_interaction: Mapping[str, Any],
    skill_record: Mapping[str, Any],
) -> Optional[str]:
    requested = str(current_interaction.get("requested_help") or "")
    if requested in ALLOWED_HELP_ACTIONS:
        return requested
    for evidence in reversed(list(skill_record.get("evidence") or [])):
        if not isinstance(evidence, Mapping):
            continue
        candidate = str(evidence.get("requested_help") or "")
        if candidate in ALLOWED_HELP_ACTIONS and evidence.get("correct") is True:
            return candidate
    return None


def derive_personal_teaching_profile(
    *,
    skill_id: str,
    canonical_lesson: Mapping[str, Any],
    current_interaction: Optional[Mapping[str, Any]] = None,
    coach_memory: Optional[Mapping[str, Any]] = None,
    active_focus: Optional[Mapping[str, Any]] = None,
    player_profile: Optional[Mapping[str, Any]] = None,
    chess_understanding: Optional[Mapping[str, Any]] = None,
    repertoire: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Derive one delivery view without changing the canonical lesson."""
    if not skill_id or not str(skill_id).strip():
        raise ValueError("skill_id is required")
    lesson = dict(_mapping(canonical_lesson))
    required = ("kind", "id", "canonical_source", "content_version")
    if any(not str(lesson.get(field) or "").strip() for field in required):
        raise ValueError("canonical_lesson identity and version are required")

    interaction = _mapping(current_interaction)
    memory = _mapping(coach_memory)
    focus = _mapping(active_focus)
    profile = _mapping(player_profile)
    understanding = _mapping(chess_understanding)
    opening = _mapping(repertoire)
    skill = _mapping(_exact_skill(memory, skill_id))
    anchors = []

    misconception_key = str(interaction.get("misconception") or "").strip()
    misconception = _misconception_copy(misconception_key)
    if misconception_key:
        anchors.append(_anchor(
            anchor_type="current_misconception",
            message=(
                f"Your last answer shows that {misconception}. "
                "We will clear that up before the next position."
            ),
            owner="current_learning_interaction",
            ref=str(interaction.get("event_id") or "") or None,
            strength="direct",
            skill_specific=True,
        ))
    elif (
        interaction.get("prediction_correct") is False
        or interaction.get("reasoning_consistent") is False
    ):
        anchors.append(_anchor(
            anchor_type="current_reasoning",
            message=(
                "Your move and your explanation did not agree. "
                "Before adding difficulty, we will name the piece or square your move helps."
            ),
            owner="current_learning_interaction",
            ref=str(interaction.get("event_id") or "") or None,
            strength="direct",
            skill_specific=True,
        ))

    if skill:
        seen = max(0, int(skill.get("seen") or 0))
        wrong = max(0, int(skill.get("wrong") or 0))
        applied = max(0, int(skill.get("applied") or 0))
        if applied:
            message = (
                "You have used this idea in a game before. "
                "This lesson checks whether you can find it again without help."
            )
        elif wrong:
            message = (
                "You have met this idea before, and it has still caused trouble. "
                "We will start with the part that broke down."
            )
        elif seen:
            message = (
                "You have met this idea before. "
                "We will begin with a fresh position instead of repeating the answer."
            )
        else:
            message = ""
        if message:
            anchors.append(_anchor(
                anchor_type="exact_skill_history",
                message=message,
                owner="coach_memory.learning.skills",
                ref=skill_id,
                strength="measured",
                skill_specific=True,
            ))

    focus_key = str(focus.get("topic_key") or focus.get("skill_id") or "")
    if focus_key and (
        focus_key == skill_id
        or focus_key in skill_id
        or skill_id in focus_key
    ):
        anchors.append(_anchor(
            anchor_type="active_focus",
            message="This is the one idea in your current coaching plan.",
            owner="user_active_focus via services/focus_bridge.py",
            ref=str(focus.get("focus_id") or "") or None,
            strength="measured",
            skill_specific=True,
        ))

    lesson_kind = str(lesson["kind"])
    opening_name = str(
        opening.get("opening_name")
        or opening.get("opening_key")
        or ""
    ).strip()
    if lesson_kind == "opening" and opening_name:
        anchors.append(_anchor(
            anchor_type="repertoire",
            message=(
                f"This connects to {opening_name}, which you already play."
            ),
            owner="user_opening_progress",
            ref=str(opening.get("opening_key") or opening_name),
            strength="measured",
            skill_specific=True,
        ))

    specific = [item for item in anchors if item["skill_specific"]]
    preferred_help = _help_from_evidence(interaction, skill)
    if specific:
        mode = "personalized"
        why_now = specific[0]["message"]
        first_stage = "explain" if interaction else "diagnose"
    else:
        mode = "diagnostic_required"
        why_now = (
            "I do not know yet which part of this idea is difficult for you. "
            "Show me what you notice on the board, and I will start there."
        )
        first_stage = "diagnose"

    rating = profile.get("rating") or profile.get("current_rating")
    dimensions = _mapping(understanding.get("dimensions"))
    complexity = {
        "rating_fallback": int(rating) if isinstance(rating, (int, float)) else None,
        "dimension_count": len(dimensions),
        "owner": (
            "services/chess_understanding.py"
            if dimensions
            else ("backend/player_profile_service.py" if rating else None)
        ),
    }

    return {
        "schema_version": TEACHING_PROFILE_SCHEMA_VERSION,
        "skill_id": skill_id,
        "canonical_lesson": lesson,
        "mode": mode,
        "why_now": why_now,
        "first_stage": first_stage,
        "anchors": anchors,
        "misconception": misconception_key or None,
        "delivery": {
            "allowed_help": list(ALLOWED_HELP_ACTIONS),
            "preferred_help": preferred_help,
            "known_vocabulary": list(interaction.get("known_vocabulary") or []),
            "complexity_fallback": complexity,
        },
        "honesty": {
            "personal_claims_require_provenance": True,
            "chess_truth_adapted": False,
            "permanent_learner_type": None,
        },
    }


async def build_personal_teaching_profile(
    db,
    user_id: str,
    *,
    skill_id: str,
    canonical_lesson: Mapping[str, Any],
    current_interaction: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Read existing evidence owners and return a non-persisted projection."""
    if current_interaction is None:
        sessions = getattr(db, "learning_sessions", None)
        if sessions is not None:
            previous = await sessions.find_one(
                {
                    "user_id": user_id,
                    "lesson_type": "personalized_curriculum",
                    "skill_id": skill_id,
                },
                {"_id": 0, "events": 1, "updated_at": 1},
                sort=[("updated_at", -1)],
            ) or {}
            for event in reversed(list(previous.get("events") or [])):
                if event.get("event_type") != "answer_submitted":
                    continue
                attempt = _mapping(event.get("attempt"))
                requested = list(attempt.get("requested_help") or [])
                current_interaction = {
                    "event_id": event.get("event_id"),
                    "misconception": attempt.get("misconception"),
                    "prediction_correct": attempt.get("prediction_correct"),
                    "reasoning_consistent": attempt.get("reasoning_consistent"),
                    "requested_help": requested[-1] if requested else None,
                    "correct": attempt.get("correct"),
                }
                break
    memory = await db.coach_memory.find_one(
        {"user_id": user_id},
        {
            "_id": 0,
            "learning.skills": 1,
            "learning.active_curriculum": 1,
        },
    ) or {}
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "rating": 1, "current_rating": 1},
    ) or {}
    understanding = await db.chess_understanding.find_one(
        {"user_id": user_id},
        {"_id": 0, "dimensions": 1},
    ) or {}
    repertoire = await db.user_opening_progress.find_one(
        {"user_id": user_id},
        {"_id": 0, "opening_key": 1, "opening_name": 1, "updated_at": 1},
        sort=[("updated_at", -1)],
    ) or {}

    focus = {}
    try:
        from services.focus_bridge import get_active_focus_bundle

        focus = await get_active_focus_bundle(db, user_id) or {}
    except Exception:
        focus = {}

    return derive_personal_teaching_profile(
        skill_id=skill_id,
        canonical_lesson=canonical_lesson,
        current_interaction=current_interaction,
        coach_memory=memory,
        active_focus=focus,
        player_profile=profile,
        chess_understanding=understanding,
        repertoire=repertoire,
    )
