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
from typing import Dict, List, Optional, Tuple

from services.engine2_skill_builder import _load_tree

logger = logging.getLogger(__name__)


# After this many days without reinforcement, a learned skill drops
# to "stale" — the system still considers it known, but a quick
# refresher is recommended. Tune from telemetry once we have it.
STALE_DAYS = 30

# Recent reinforcement threshold. If the user has practiced (seen)
# the skill within this window, don't mark it stale even when
# learned_at is older — they're keeping it sharp.
RECENT_REINFORCEMENT_DAYS = 14


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


def _progress_hint(skill, kind: str) -> str:
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
        # Mohit 2026-05-28: the old "Played {seen}/5 times" / "{correct}/3
        # correct" phrasings read as ratios (2 out of 3) when they actually
        # meant "current vs. graduation goal." Rewritten to make the goal
        # explicit and stop misleading the user.
        if seen < 5:
            remaining = 5 - seen
            return f"{seen} games so far. {remaining} more to reach the {seen + remaining}-game baseline."
        if correct < 3:
            need = 3 - correct
            return f"{seen} games played. Need {need} more accurate game{'s' if need != 1 else ''} to graduate."
        if "wrong" in last_two:
            return "Last two attempts had a slip — clean games needed."
        return "Played enough to count as studied."
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


def _state_for_skill(skill, kind: str, *, now: Optional[datetime] = None) -> Tuple[str, Optional[int]]:
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
            state, days = _state_for_skill(progress, kind, now=now)
            record.update({
                "state": state,
                "seen": progress.seen,
                "correct": progress.correct,
                "wrong": progress.wrong,
                "learned_at": progress.learned_at,
                "days_since_studied": days,
                "progress_hint": _progress_hint(progress, kind),
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
