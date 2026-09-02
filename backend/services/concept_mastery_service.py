"""
Concept Mastery Service — surface "what you've studied" for Engine 2.

The Engine 2 skill tree (data/coaching/skill_tree.json) tracks 24
skills across 6 kinds: opening, trap_set, endgame, mate_pattern,
concept, coached_play. The coach memory records per-skill
seen/correct/wrong counts and stamps `learned_at` when the kind-aware
graduation rule passes (SkillProgress.is_learned()).

Note on labelling: for knowledge skills (endgame/concept/mate_pattern)
the current graduation rule is just "one correct attempt in a guided
lesson". That proves you can follow the lesson, not that you've
internalised the concept. The user-facing label here is therefore
"studied", not "learned". Until in-game application detectors land,
that's the honest word.

States:

    unseen      Never recorded any outcome on this skill.
    learning    Started but graduation rule not yet met.
    studied     Graduated AND last reinforcement <= STALE_DAYS ago.
    stale       Graduated > STALE_DAYS ago AND no recent reinforcement.
                Worth a refresher.

Public API:

    summarize_mastery(memory) -> Dict
        {
          "summary": {total_skills, studied, learning, unseen, stale},
          "by_kind": {
            "endgame": [<skill records>],
            "opening": [...],
            ...
          }
        }

Read-only — never mutates memory.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from services.engine2_skill_builder import _load_tree
from services.personal_curriculum import (
    ContractViolation,
    LessonResult,
    PIC_CANONICAL_SOURCE,
    PIC_CONTENT_ID,
    PIC_CONTENT_KIND,
    PIC_SKILL_ID,
    StudentState,
)

logger = logging.getLogger(__name__)


# After this many days without reinforcement, a learned skill drops
# to "stale" — the system still considers it known, but a quick
# refresher is recommended. Tune from telemetry once we have it.
STALE_DAYS = 30

# Recent reinforcement threshold. If the user has practiced (seen)
# the skill within this window, don't mark it stale even when
# learned_at is older — they're keeping it sharp.
RECENT_REINFORCEMENT_DAYS = 14

PIC_STATE_LABELS = {
    "learning": "Learning",
    "remembered": "Remembered",
    "proven_in_games": "Proven in games",
}


def reduce_pic_mastery(
    events: Iterable[Dict[str, Any]],
    *,
    diagnosed: bool = False,
) -> Dict[str, Any]:
    """Project eligible PIC evidence into the inherited LES learner states.

    The reducer deliberately accepts explicit evidence decisions instead of
    deriving eligibility from outcome text. That keeps content review,
    assistance, cohort isolation and the future game-proof rule outside the
    projection. Verified own-game positions and assisted practice may
    introduce the skill, but cannot independently advance it.
    """
    ordered = sorted(
        list(events or []),
        key=lambda event: str(event.get("occurred_at") or ""),
    )
    introduced = diagnosed
    current = 0
    highest = 0
    refresh_needed = False
    accepted = 0
    rejected = 0

    for event in ordered:
        event_type = event.get("event_type")
        if event_type in ("lesson_started", "diagnosis_confirmed"):
            introduced = True
            current = max(current, 1)
            highest = max(highest, 1)

        checkpoint = event.get("checkpoint")
        if checkpoint is None:
            checkpoint = event.get("checkpoint_candidate")
        try:
            checkpoint = int(checkpoint)
        except (TypeError, ValueError):
            checkpoint = 0
        checkpoint = checkpoint if 1 <= checkpoint <= 8 else 0

        passed = event.get("result") in (
            "correct",
            "passed",
            "handled",
            "demonstrated",
        )
        eligible = bool(event.get("evidence_eligible"))
        if checkpoint and passed:
            if not eligible:
                rejected += 1
                continue
            accepted += 1
            introduced = True
            current = max(current, checkpoint)
            highest = max(highest, checkpoint)
            refresh_needed = False
            continue

        if event.get("result") not in ("wrong", "failed", "miss"):
            continue
        if not eligible or not event.get("demotion_eligible"):
            rejected += int(bool(checkpoint))
            continue

        if event.get("stage") == "delayed_recall" or checkpoint == 7:
            fallback = event.get("last_redemonstrated_checkpoint", 6)
            try:
                fallback = int(fallback)
            except (TypeError, ValueError):
                fallback = 6
            current = min(current, max(1, min(fallback, 6)))
            refresh_needed = True
        elif (
            event.get("stage") == "external_focus_game"
            and event.get("proof_rule_locked")
            and event.get("repeated_verified_misses")
        ):
            current = min(current, 7)
            refresh_needed = True

    if current >= 8:
        state = "proven_in_games"
        next_step = "Keep applying it in real games"
    elif current >= 7:
        state = "remembered"
        next_step = "Use it in a committed Focus Game"
    else:
        state = "learning"
        next_step = (
            "Take an unassisted checkpoint"
            if current >= 6
            else "Continue the piece-safety lesson"
        )

    return {
        "skill_id": PIC_SKILL_ID,
        "state": state,
        "label": PIC_STATE_LABELS[state],
        "refresh_needed": refresh_needed,
        "current_demonstrated_checkpoint": current,
        "highest_demonstrated_checkpoint": highest,
        "introduced": introduced,
        "next_step": next_step,
        "evidence": {
            "eligible_events": accepted,
            "rejected_events": rejected,
        },
    }


async def get_pic_mastery_projection(
    db,
    user_id: str,
    *,
    diagnosed: bool = False,
) -> Dict[str, Any]:
    """Read PIC evidence adapters and return the one canonical projection."""
    events: List[Dict[str, Any]] = []
    sessions = db.learning_sessions.find(
        {"user_id": user_id, "skill_id": PIC_SKILL_ID},
        {"_id": 0, "events": 1},
    )
    async for session in sessions:
        events.extend(session.get("events") or [])

    game_cursor = db.games.find(
        {
            "user_id": user_id,
            "pic_evidence.proof_detector_id": {"$in": [
                "piece_safety.d_live.v1",
                "piece_safety.destination_safety_exact.v1",
            ]},
        },
        {"_id": 0, "pic_evidence": 1, "date_played": 1},
    )
    async for game in game_cursor:
        evidence = game.get("pic_evidence") or {}
        summary = evidence.get("summary") or {}
        events.append({
            "event_type": "external_game_evidence",
            "occurred_at": game.get("date_played"),
            "stage": evidence.get("evidence_mode") or "ordinary_play",
            "checkpoint_candidate": 8,
            "result": (
                "miss"
                if int(summary.get("misses") or 0) > 0
                else "handled"
            ),
            # The PIC proof rule is intentionally not locked yet. The
            # evidence remains visible and auditable but cannot promote or
            # demote mastery until an explicit eligible decision is stored.
            "evidence_eligible": bool(evidence.get("mastery_eligible")),
            "demotion_eligible": bool(evidence.get("demotion_eligible")),
            "proof_rule_locked": bool(evidence.get("proof_rule_locked")),
            "repeated_verified_misses": bool(
                evidence.get("repeated_verified_misses")
            ),
        })
    return reduce_pic_mastery(events, diagnosed=diagnosed)


_SHADOW_STATE_ORDER = {
    StudentState.NEW: 0,
    StudentState.LEARNING: 1,
    StudentState.CAN_DO_WITH_HELP: 2,
    StudentState.CAN_DO_ALONE: 3,
    StudentState.USED_IN_GAMES: 4,
}


def reduce_lesson_results_shadow(
    events: Iterable[Dict[str, Any]],
    *,
    skill_id: str,
    diagnosed: bool = False,
    required_content_identity: Optional[Tuple[str, str, str]] = None,
    compatible_skill_ids: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """Project one canonical skill without changing visible mastery."""
    if not str(skill_id or "").strip():
        raise ContractViolation("skill_id is required for shadow projection")
    state = StudentState.LEARNING if diagnosed else StudentState.NEW
    accepted = 0
    rejected = 0
    by_attempt: Dict[str, int] = {}
    source_event_ids = set()

    for event in sorted(
        list(events or []),
        key=lambda item: str(item.get("occurred_at") or ""),
    ):
        if (
            event.get("event_type") not in ("lesson_result", "answer_submitted")
            or event.get("rollout_mode") != "shadow"
        ):
            continue
        if event.get("evidence_eligible") is not False:
            rejected += 1
            continue
        payload = event.get("lesson_result") or {}
        if event.get("shadow_earned_state") != payload.get("earned_state"):
            rejected += 1
            continue
        try:
            result = LessonResult.from_event_dict(
                payload
            )
        except (ContractViolation, TypeError, ValueError):
            rejected += 1
            continue
        result_skill_id = str(result.skill_id or result.content_id or "")
        outer_skill_id = str(event.get("skill_id") or result_skill_id)
        if outer_skill_id != result_skill_id:
            rejected += 1
            continue
        if result_skill_id not in {skill_id, *compatible_skill_ids}:
            rejected += 1
            continue
        if required_content_identity is not None and (
            result.content_kind,
            result.content_id,
            result.canonical_source,
        ) != required_content_identity:
            rejected += 1
            continue
        if (
            not result.source_event_id
            or result.source_event_id in source_event_ids
        ):
            rejected += 1
            continue
        source_event_ids.add(result.source_event_id)
        accepted += 1
        by_attempt[result.attempt_kind.value] = (
            by_attempt.get(result.attempt_kind.value, 0) + 1
        )
        earned = result.earned_state()
        if (
            earned is not None
            and _SHADOW_STATE_ORDER[earned] > _SHADOW_STATE_ORDER[state]
        ):
            state = earned

    return {
        "skill_id": skill_id,
        "rollout_mode": "shadow",
        "state": state.value,
        "visible_mastery_changed": False,
        "evidence": {
            "accepted_events": accepted,
            "rejected_events": rejected,
            "by_attempt": dict(sorted(by_attempt.items())),
        },
    }


def reduce_review_learning_shadow(
    events: Iterable[Dict[str, Any]],
    *,
    diagnosed: bool = False,
) -> Dict[str, Any]:
    """Compatibility wrapper for the original PIC-only shadow projection."""
    return reduce_lesson_results_shadow(
        events,
        skill_id=PIC_SKILL_ID,
        diagnosed=diagnosed,
        required_content_identity=(
            PIC_CONTENT_KIND,
            PIC_CONTENT_ID,
            PIC_CANONICAL_SOURCE,
        ),
        compatible_skill_ids=(PIC_CONTENT_ID,),
    )


async def get_learning_shadow_projection(
    db,
    user_id: str,
    *,
    skill_id: str,
    diagnosed: bool = False,
) -> Dict[str, Any]:
    """Read and reduce one private canonical skill ledger."""
    events: List[Dict[str, Any]] = []
    sessions = db.learning_sessions.find(
        {"user_id": user_id, "skill_id": skill_id},
        {"_id": 0, "events": 1},
    )
    async for session in sessions:
        events.extend(session.get("events") or [])
    return reduce_lesson_results_shadow(
        events,
        skill_id=skill_id,
        diagnosed=diagnosed,
    )


async def get_review_learning_shadow_comparison(
    db,
    user_id: str,
    *,
    diagnosed: bool = False,
) -> Dict[str, Any]:
    """Compare the inherited PIC projection to review evidence, privately."""
    events: List[Dict[str, Any]] = []
    sessions = db.learning_sessions.find(
        {
            "user_id": user_id,
            "skill_id": PIC_SKILL_ID,
        },
        {"_id": 0, "events": 1},
    )
    async for session in sessions:
        events.extend(session.get("events") or [])
    return {
        "schema_version": "review_learning_shadow_comparison.v1",
        "current_projection": await get_pic_mastery_projection(
            db, user_id, diagnosed=diagnosed
        ),
        "review_shadow_projection": reduce_review_learning_shadow(
            events, diagnosed=diagnosed
        ),
        "visible_mastery_changed": False,
    }


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """Tolerant ISO parser. Returns None on any failure or empty input."""
    if not ts:
        return None
    try:
        # datetime.fromisoformat handles "+00:00" since 3.11
        s = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _days_since(ts: Optional[str], *, now: Optional[datetime] = None) -> Optional[int]:
    """Whole days between now and a given ISO timestamp. None on parse fail."""
    parsed = _parse_iso(ts)
    if parsed is None:
        return None
    n = now or datetime.now(timezone.utc)
    delta = n - parsed
    return max(0, delta.days)


def _progress_hint(skill, kind: str, studied: bool = False) -> str:
    """One short line describing how close the user is to graduation.

    Kind-aware so the hint matches the actual graduation rule. The
    UI uses this to show "2/3 correct, one more clean attempt to go"
    style copy without re-implementing the rule frontend-side.
    """
    seen = skill.seen
    correct = skill.correct
    wrong = skill.wrong
    last_two = skill.outcomes[-2:] if len(skill.outcomes) >= 2 else skill.outcomes
    last_three = skill.outcomes[-3:] if len(skill.outcomes) >= 3 else skill.outcomes

    if kind in ("mate_pattern", "endgame", "concept"):
        if correct == 0:
            return "One correct attempt to clear the lesson."
        if "wrong" in last_two:
            return "Recent stumble — one clean attempt needed."
        return "Lesson cleared."
    if kind in ("trap_set", "trap"):
        if seen < 1:
            return "Open the trap once."
        if correct < 1:
            return "Apply it correctly once."
        if "wrong" in last_two:
            return "Recent stumble — clean attempt needed."
        return "Lesson cleared."
    if kind == "opening":
        # Honest model (Mohit 2026-06-09): playing an opening — even accurately —
        # shows you HANDLE the structure well; it does NOT mean you've STUDIED or
        # KNOW it (you may have transposed in, or played sensible general moves that
        # happened to land in this opening). So we report the FACT and point to study
        # for real mastery — playing it, however well, is NEVER called "studied".
        # (`correct` here = games where the opening phase was played cleanly — a
        # play-quality fact, not knowledge. Real "studied" comes from the lesson.)
        plural = "s" if seen != 1 else ""
        if studied:
            clean = f", {correct} cleanly" if correct else ""
            return f"Studied. Played {seen} time{plural}{clean} — you know this one. Keep it sharp."
        if seen < 1:
            return "Not played yet. Study it to learn the ideas."
        if correct < 1:
            return (f"Played {seen} time{plural}, but the opening hasn't gone cleanly "
                    f"yet. Study it to learn the ideas.")
        return (f"Played {seen} time{plural} — {correct} cleanly; you handle it well. "
                f"Study it to learn the theory and play it on purpose.")
    if kind == "coached_play":
        if correct < 3:
            need = 3 - correct
            return f"{correct} of 3 graduating sessions complete. {need} more to go."
        if "wrong" in last_three:
            return "Recent fail — 3 clean in a row needed."
        return "Habit established."
    # Legacy / unknown
    if seen < 5:
        return f"Seen {seen}/5 times."
    if correct < 3:
        return f"{correct}/3 correct."
    return "Studied."


def _state_for_skill(skill, kind: str, *, now: Optional[datetime] = None,
                     studied_override: Optional[bool] = None) -> Tuple[str, Optional[int]]:
    """Compute (state, days_since_studied) for a single SkillProgress entry.

    State machine:
      - learned_at set + recent reinforcement → "studied"
      - learned_at set + > STALE_DAYS old + no recent reinforcement → "stale"
      - is_learned() true (just promoted, learned_at not yet set) → "studied"
      - SkillProgress exists, is_learned() false → "learning"

    Note: SkillProgress's internal field is still called `learned_at` —
    it represents the timestamp when the kind's graduation rule passed.
    The user-facing state name is "studied" because for most kinds the
    rule is "completed the guided lesson", not proof of retention.
    """
    n = now or datetime.now(timezone.utc)

    # Openings: "studied" means the user did the LESSON, not that they played it
    # accurately (play != knowledge — Mohit 2026-06-09: Philidor showed "studied"
    # off games played). The caller passes studied_override = skill_id in
    # openings_learned; play-based is_learned() / learned_at are IGNORED for
    # openings so playing one, however well, is never reported as "studied".
    if kind == "opening" and studied_override is not None:
        if studied_override:
            return "studied", _days_since(skill.learned_at, now=n)
        return "learning", None

    graduated_now = skill.is_learned()
    days_graduated = _days_since(skill.learned_at, now=n)
    days_last_seen = _days_since(skill.last_seen, now=n)

    recently_reinforced = (
        days_last_seen is not None and days_last_seen <= RECENT_REINFORCEMENT_DAYS
    )

    if days_graduated is not None:
        if days_graduated > STALE_DAYS and not recently_reinforced:
            return "stale", days_graduated
        return "studied", days_graduated

    if graduated_now:
        return "studied", None

    return "learning", None


def _compute_lesson_url(skill_id: str, node: Dict) -> Optional[str]:
    """Map a skill_id + tree node to the user-facing lesson URL.

    Returns None when no lesson page is wired for this skill kind yet.
    The Progress page renders a 'Study →' link only when this field
    is present, so missing entries fall through silently instead of
    rendering broken links.
    """
    kind = node.get("kind", "")
    ref = node.get("content_ref", "")
    if kind == "opening":
        return f"/openings/{ref}" if ref else None
    if kind == "coached_play":
        return f"/play-with-coach?focus={skill_id}"
    if kind == "endgame":
        # content_ref doesn't always match endgame_theory_tree.json
        # lesson keys directly (e.g. 'lucena_position' vs 'lucena').
        # Hard-coded mapping for the 4 endgame skills currently
        # in the tree.
        ENDGAME_MAP = {
            "opposition":      ("king_and_pawn", "opposition"),
            "rule_of_square":  ("king_and_pawn", "square_rule"),
            "lucena_position": ("rook_endgames", "lucena"),
            "philidor_position": ("rook_endgames", "philidor"),
        }
        cat_lesson = ENDGAME_MAP.get(ref)
        if cat_lesson:
            return f"/endgames/{cat_lesson[0]}/{cat_lesson[1]}"
        return None
    # concept / trap_set / mate_pattern — no lesson page yet. When one
    # ships, register the mapping here.
    return None


def summarize_mastery(memory) -> Dict:
    """Build the user-facing mastery summary across the full skill tree.

    Reads coach_memory.learning.skills (per-user skill state) and the
    Engine 2 skill tree (the catalogue of all skills). Returns:

        {
          "summary": {
            "total_skills": int,    # tree size
            "unseen": int,
            "learning": int,
            "studied": int,
            "stale": int,
          },
          "by_kind": {
            "endgame":      [skill_record, ...],
            "opening":      [...],
            "trap_set":     [...],
            "mate_pattern": [...],
            "concept":      [...],
            "coached_play": [...],
          }
        }

    Each skill_record:
        skill_id, label, kind, tier, state,
        seen, correct, wrong,
        learned_at, days_since_studied,
        progress_hint, fixes
    """
    tree = _load_tree()
    tree_skills = tree.get("skills", {})

    user_skills_by_id = {
        s.skill_id: s for s in (getattr(memory.learning, "skills", []) or [])
    }

    # Real opening study = the user completed the LESSON, recorded in openings_learned
    # by skill_id. The old play-promotion path stored opening NAMES ("Philidor Defense")
    # not skill_ids, so by-skill_id membership cleanly separates real study from play.
    _learned = getattr(memory.learning, "openings_learned", None) or []
    studied_opening_ids = {x for x in _learned if isinstance(x, str) and x.startswith("opening_")}

    by_kind: Dict[str, List[Dict]] = {}
    counts = {"unseen": 0, "learning": 0, "studied": 0, "stale": 0}
    now = datetime.now(timezone.utc)

    for skill_id, node in tree_skills.items():
        kind = node.get("kind", "concept")
        record = {
            "skill_id": skill_id,
            "label": node.get("label", skill_id.replace("_", " ").title()),
            "kind": kind,
            "tier": node.get("tier", 0),
            "fixes": node.get("fixes", ""),
            # Mohit 2026-05-30: lesson_url makes each skill clickable on
            # the Progress page Skills section. None when no lesson page
            # exists yet (concepts, trap sets, mates without a lesson).
            # See _compute_lesson_url() below for the kind->URL mapping.
            "lesson_url": _compute_lesson_url(skill_id, node),
        }

        progress = user_skills_by_id.get(skill_id)
        if progress is None:
            record.update({
                "state": "unseen",
                "seen": 0,
                "correct": 0,
                "wrong": 0,
                "learned_at": None,
                "days_since_studied": None,
                "progress_hint": "Not started.",
            })
            counts["unseen"] += 1
        else:
            studied_override = (skill_id in studied_opening_ids) if kind == "opening" else None
            state, days = _state_for_skill(progress, kind, now=now, studied_override=studied_override)
            record.update({
                "state": state,
                "seen": progress.seen,
                "correct": progress.correct,
                "wrong": progress.wrong,
                "learned_at": progress.learned_at,
                "days_since_studied": days,
                "progress_hint": _progress_hint(progress, kind, studied=bool(studied_override)),
            })
            counts[state] += 1

        by_kind.setdefault(kind, []).append(record)

    # Sort: studied (freshest) → learning (most attempted) → stale → unseen (easiest first)
    state_order = {"studied": 0, "learning": 1, "stale": 2, "unseen": 3}
    for kind, records in by_kind.items():
        records.sort(key=lambda r: (
            state_order.get(r["state"], 99),
            r.get("days_since_studied") or 0,
            -r.get("seen", 0),
            r.get("tier", 0),
        ))

    return {
        "summary": {
            "total_skills": len(tree_skills),
            **counts,
        },
        "by_kind": by_kind,
    }
