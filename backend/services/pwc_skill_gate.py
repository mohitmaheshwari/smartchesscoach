"""PWC live-coaching skill-mastery gate.

Mohit 2026-06-02. Spec: docs/pwc_skills_aware_coaching.md.

PWC coaching candidates carry an optional `nudge_id` that maps to one
or more Engine 2 `skill_id`s via data/coaching/coaching_skill_map.json.
Before a candidate is shown to the user, gate it by their mastery
state — suppress nudges the user has mastered, escalate nudges where
the user keeps making the same mistake.

The 6 outcomes:

  candidate has no nudge_id                       → PASS (unchanged)
  nudge_id not in the map                         → PASS (default; ungated)
  candidate's skills are all "mastered"           → SUPPRESS (return None)
  candidate's skills show "struggling" pattern    → ESCALATE (prepend cross-game framing)
  candidate's skills are mixed                    → ESCALATE wins over SUPPRESS
  user has no learning.skills data                → PASS (graceful degradation)

The "mastery" and "struggling" thresholds match the spec §2 defaults:
  mastered    = applied ≥ 3 AND wrong / max(seen, 1) < 0.2
  struggling  = wrong ≥ correct AND seen ≥ 3

The thresholds are intentionally STRICTER than SkillProgress.is_learned()'s
default graduation rule. is_learned() can return True after one
correct lesson attempt; we want PWC suppression to require evidence
of in-game application (`applied ≥ 3`), which is a higher bar.

Default OFF behind PWC_SKILL_GATE_ENABLED env var per the spec; this
module's pure functions can be tested without the wiring.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Configuration (per spec §5) ─────────────────────────────────────────

# Mastery: applied count meets the bar AND the wrong rate is acceptably
# low. Numbers from spec §2. Calibration is observable post-ship via
# per-user suppression count.
MASTERY_MIN_APPLIED = 3
MASTERY_MAX_WRONG_RATE = 0.2

# Struggling: at least 3 attempts AND wrongs >= corrects. Stricter than
# the engine2 default to avoid hammering users on a few unlucky games.
STRUGGLE_MIN_SEEN = 3


# ── Data loading ────────────────────────────────────────────────────────

_SKILL_MAP_CACHE: Optional[Dict[str, List[str]]] = None
_SKILL_MAP_PATH = (
    Path(__file__).resolve().parent.parent
    / "data" / "coaching" / "coaching_skill_map.json"
)


def _load_skill_map() -> Dict[str, List[str]]:
    """Load and cache the nudge_id → [skill_id] map. Strips _meta key."""
    global _SKILL_MAP_CACHE
    if _SKILL_MAP_CACHE is not None:
        return _SKILL_MAP_CACHE
    try:
        with open(_SKILL_MAP_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        cleaned = {
            k: v for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, list)
        }
        _SKILL_MAP_CACHE = cleaned
    except Exception as e:
        logger.warning(f"[pwc_skill_gate] failed to load skill map: {e}")
        _SKILL_MAP_CACHE = {}
    return _SKILL_MAP_CACHE


def reload_skill_map() -> None:
    """Force-reload (for tests)."""
    global _SKILL_MAP_CACHE
    _SKILL_MAP_CACHE = None


# ── Classification of skill state ───────────────────────────────────────


def _is_mastered(skill_record: Dict[str, Any]) -> bool:
    """Returns True iff the user has applied this skill confidently
    enough in real games that PWC suppression is safe."""
    applied = int(skill_record.get("applied", 0) or 0)
    seen = int(skill_record.get("seen", 0) or 0)
    wrong = int(skill_record.get("wrong", 0) or 0)
    if applied < MASTERY_MIN_APPLIED:
        return False
    wrong_rate = wrong / max(seen, 1)
    return wrong_rate < MASTERY_MAX_WRONG_RATE


def _is_struggling(skill_record: Dict[str, Any]) -> bool:
    """Returns True iff the user keeps missing this skill — wrongs
    meet or exceed corrects across at least STRUGGLE_MIN_SEEN attempts."""
    seen = int(skill_record.get("seen", 0) or 0)
    correct = int(skill_record.get("correct", 0) or 0)
    wrong = int(skill_record.get("wrong", 0) or 0)
    if seen < STRUGGLE_MIN_SEEN:
        return False
    return wrong >= correct


# ── Public API ──────────────────────────────────────────────────────────


# Gate outcomes. Strings (not enums) for log-friendliness and to keep
# the consumer side simple — the field shows up directly in logs.
GATE_PASS = "pass"
GATE_SUPPRESS = "suppress"   # retained for the API; not used by default
GATE_ESCALATE = "escalate"
# Mohit 2026-06-03 — replaces SUPPRESS as the mastered-skill outcome.
# Reasoning: full suppression has an asymmetric downside (missing one
# warning > redundant warning). DOWNGRADE prepends an "you've handled
# this before" line, keeping the warning visible while signalling that
# the coach is aware of the user's mastery.
GATE_DOWNGRADE = "downgrade"


def gate_decision(
    nudge_id: Optional[str],
    learning_skills: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Decide whether to pass, suppress, or escalate a PWC coaching
    candidate given the user's Engine 2 mastery state.

    Args:
        nudge_id: stable identifier of the coaching candidate. None or
            unrecognised → PASS (no change). Pure function; doesn't
            mutate either argument.
        learning_skills: list of skill records (dicts) in the shape
            SkillProgress is serialised to. Pass `mem.learning.skills`
            converted to dicts.

    Returns:
        dict with keys:
          decision          — GATE_PASS / GATE_DOWNGRADE / GATE_ESCALATE
                              (SUPPRESS exists in the API but is no longer
                              used as a default outcome — replaced by
                              DOWNGRADE 2026-06-03)
          reason            — short tag for logging (e.g. "no_nudge_id",
                              "unmapped", "mastered:defend_fried_liver",
                              "struggling:endgame_opposition")
          matched_skills    — list of skill_id strings that drove the
                              decision (empty for PASS on unmapped)
          escalate_prefix   — when decision == ESCALATE, a one-line
                              cross-game framing string the caller
                              prepends to the nudge. Empty otherwise.
          downgrade_prefix  — when decision == DOWNGRADE, a one-line
                              "you've handled this before" reminder.
                              Empty otherwise.

    No mutation, no logging side-effects (caller logs).
    """
    if not nudge_id:
        return {
            "decision": GATE_PASS, "reason": "no_nudge_id",
            "matched_skills": [], "escalate_prefix": "", "downgrade_prefix": "",
        }

    skill_map = _load_skill_map()
    target_skill_ids = skill_map.get(nudge_id) or []
    if not target_skill_ids:
        return {
            "decision": GATE_PASS, "reason": "unmapped",
            "matched_skills": [], "escalate_prefix": "", "downgrade_prefix": "",
        }

    if not learning_skills:
        return {
            "decision": GATE_PASS, "reason": "no_skill_data",
            "matched_skills": [], "escalate_prefix": "", "downgrade_prefix": "",
        }

    # Index user's skills by id.
    by_id: Dict[str, Dict[str, Any]] = {}
    for s in learning_skills:
        sid = s.get("skill_id") if isinstance(s, dict) else getattr(s, "skill_id", None)
        if sid:
            by_id[sid] = s if isinstance(s, dict) else _to_dict(s)

    # Look at each mapped skill's state.
    struggling_hits: List[str] = []
    mastered_hits: List[str] = []
    for sid in target_skill_ids:
        rec = by_id.get(sid)
        if rec is None:
            continue
        if _is_struggling(rec):
            struggling_hits.append(sid)
        elif _is_mastered(rec):
            mastered_hits.append(sid)

    # ESCALATE wins over DOWNGRADE (mixed mastered/struggling → struggling
    # is the more important signal to act on).
    if struggling_hits:
        sid = struggling_hits[0]
        wrong_count = int(by_id[sid].get("wrong", 0) or 0)
        prefix = (
            f"You've missed this pattern {wrong_count} times before — "
            f"let's lock it in."
        )
        return {
            "decision": GATE_ESCALATE, "reason": f"struggling:{sid}",
            "matched_skills": struggling_hits,
            "escalate_prefix": prefix, "downgrade_prefix": "",
        }

    if mastered_hits and len(mastered_hits) == len(target_skill_ids):
        # ALL mapped skills mastered → DOWNGRADE the nudge instead of
        # suppressing it. Mohit 2026-06-03: asymmetric cost analysis —
        # missing one warning > redundant warning, so we keep the
        # warning visible but signal that the coach knows you've
        # handled this before.
        prefix = "You've handled this before — quick reminder."
        return {
            "decision": GATE_DOWNGRADE,
            "reason": "mastered:" + ",".join(mastered_hits),
            "matched_skills": mastered_hits,
            "escalate_prefix": "", "downgrade_prefix": prefix,
        }

    # Default — at least one mapped skill exists in user data but isn't
    # mastered or struggling. PASS unchanged.
    return {
        "decision": GATE_PASS, "reason": "default",
        "matched_skills": [s.get("skill_id") for s in learning_skills if s.get("skill_id") in target_skill_ids],
        "escalate_prefix": "", "downgrade_prefix": "",
    }


def is_enabled() -> bool:
    """Env-flag check — match the spec's PWC_SKILL_GATE_ENABLED default-off."""
    return os.environ.get("PWC_SKILL_GATE_ENABLED", "false").lower() == "true"


# ── Helpers ─────────────────────────────────────────────────────────────


def _to_dict(skill_record: Any) -> Dict[str, Any]:
    """Convert SkillProgress dataclass to dict for uniform handling.
    Robust to either dict input (already dict) or dataclass-like attrs."""
    if isinstance(skill_record, dict):
        return skill_record
    return {
        "skill_id": getattr(skill_record, "skill_id", None),
        "seen": getattr(skill_record, "seen", 0),
        "correct": getattr(skill_record, "correct", 0),
        "wrong": getattr(skill_record, "wrong", 0),
        "applied": getattr(skill_record, "applied", 0),
    }
