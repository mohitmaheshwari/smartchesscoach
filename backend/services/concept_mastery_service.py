"""
Concept Mastery Service — surface "what you've learned" for Engine 2.

The Engine 2 skill tree (data/coaching/skill_tree.json) tracks 24
skills across 6 kinds: opening, trap_set, endgame, mate_pattern,
concept, coached_play. The coach memory already records per-skill
seen/correct/wrong counts and auto-promotes to a `learned_at`
timestamp when the kind-aware graduation rule passes
(SkillProgress.is_learned()).

What was missing: a USER-VISIBLE summary of all this. The system
silently knows you've learned the rule of the square — it just
doesn't tell you. This service rolls the per-user skill state into
a four-state model the UI can render directly.

States:

    unseen      Never recorded any outcome on this skill.
    learning    Seen at least once but graduation rule not yet met.
    learned     Graduated AND last reinforcement <= STALE_DAYS ago.
    stale       Graduated > STALE_DAYS ago AND no recent reinforcement.
                Implies a refresher would help. The system still
                considers the skill "known" but flags it for review.

Public API:

    summarize_mastery(memory) -> Dict
        {
          "summary": {total_skills, learned, learning, unseen, stale},
          "by_kind": {
            "endgame": [<skill records>],
            "opening": [...],
            ...
          }
        }

This is read-only — it never mutates memory. The promotion logic
already runs inside record_skill_outcome (coach_memory.py); we just
inspect the resulting state.
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
            return "One correct attempt to graduate."
        if "wrong" in last_two:
            return "Recent stumble — get one clean to graduate."
        return "Graduated."
    if kind in ("trap_set", "trap"):
        if seen < 1:
            return "Open the trap once."
        if correct < 1:
            return "Apply it correctly once."
        if "wrong" in last_two:
            return "Recent stumble — clean attempt needed."
        return "Graduated."
    if kind == "opening":
        if seen < 5:
            return f"Played {seen}/5 times."
        if correct < 3:
            return f"Played {seen} times, {correct}/3 correct."
        if "wrong" in last_two:
            return "Last two attempts had a slip — clean games needed."
        return "Graduated."
    if kind == "coached_play":
        if correct < 3:
            return f"{correct}/3 correct sessions."
        if "wrong" in last_three:
            return "Recent fail — 3 clean in a row needed."
        return "Graduated."
    # Legacy / unknown
    if seen < 5:
        return f"Seen {seen}/5 times."
    if correct < 3:
        return f"{correct}/3 correct."
    return "Graduated."


def _state_for_skill(skill, kind: str, *, now: Optional[datetime] = None) -> Tuple[str, Optional[int]]:
    """Compute (state, days_since_learned) for a single SkillProgress entry.

    State machine:
      - learned_at set + recent reinforcement → "learned"
      - learned_at set + > STALE_DAYS old + no recent reinforcement → "stale"
      - is_learned() true (just promoted, learned_at not yet set) → "learned"
      - SkillProgress exists, is_learned() false → "learning"
    """
    n = now or datetime.now(timezone.utc)

    is_learned_now = skill.is_learned()
    days_learned = _days_since(skill.learned_at, now=n)
    days_last_seen = _days_since(skill.last_seen, now=n)

    # Recent reinforcement keeps a skill fresh even if learned_at is old.
    recently_reinforced = (
        days_last_seen is not None and days_last_seen <= RECENT_REINFORCEMENT_DAYS
    )

    if days_learned is not None:
        if days_learned > STALE_DAYS and not recently_reinforced:
            return "stale", days_learned
        return "learned", days_learned

    if is_learned_now:
        # is_learned() true but learned_at not yet written (race / pre-promotion)
        return "learned", None

    return "learning", None


def summarize_mastery(memory) -> Dict:
    """Build the user-facing mastery summary across the full skill tree.

    Reads coach_memory.learning.skills (per-user skill state) and the
    Engine 2 skill tree (the catalogue of all skills). Returns:

        {
          "summary": {
            "total_skills": int,    # tree size
            "unseen": int,
            "learning": int,
            "learned": int,
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
        learned_at, days_since_learned,
        progress_hint, fixes
    """
    tree = _load_tree()
    tree_skills = tree.get("skills", {})

    # Index user's skill progress by skill_id for O(1) lookup
    user_skills_by_id = {
        s.skill_id: s for s in (getattr(memory.learning, "skills", []) or [])
    }

    by_kind: Dict[str, List[Dict]] = {}
    counts = {"unseen": 0, "learning": 0, "learned": 0, "stale": 0}
    now = datetime.now(timezone.utc)

    for skill_id, node in tree_skills.items():
        kind = node.get("kind", "concept")
        record = {
            "skill_id": skill_id,
            "label": node.get("label", skill_id.replace("_", " ").title()),
            "kind": kind,
            "tier": node.get("tier", 0),
            "fixes": node.get("fixes", ""),
        }

        progress = user_skills_by_id.get(skill_id)
        if progress is None:
            record.update({
                "state": "unseen",
                "seen": 0,
                "correct": 0,
                "wrong": 0,
                "learned_at": None,
                "days_since_learned": None,
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
                "days_since_learned": days,
                "progress_hint": _progress_hint(progress, kind),
            })
            counts[state] += 1

        by_kind.setdefault(kind, []).append(record)

    # Sort each kind: learned first (by days_since asc — freshest first),
    # then learning (by seen desc — most attempted first), then unseen
    # (by tier asc — easiest first), then stale.
    state_order = {"learned": 0, "learning": 1, "stale": 2, "unseen": 3}
    for kind, records in by_kind.items():
        records.sort(key=lambda r: (
            state_order.get(r["state"], 99),
            r.get("days_since_learned") or 0,
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
