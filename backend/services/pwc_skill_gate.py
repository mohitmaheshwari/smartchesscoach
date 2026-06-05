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


# ─── Concept-mastery gate (Path C, 2026-06-05) ───────────────────────────
#
# The original gate above works against the nudge_id → skill_id map +
# Engine 2 SkillProgress records. After Engine 2 Phase 1 shipped
# (user_concept_understanding with mastered_at + streak_clean), we have
# a stronger signal: per-user × per-concept mastery driven by real game
# outcomes. This block adds a parallel gate that consumes that signal
# directly, keyed by concept_id (the central pipeline namespace).
#
# Slipping threshold LOCKED 2026-06-05 via probe across all
# user_concept_understanding rows with mastered_at set: N=10 games
# (docs/pwc_mastery_gate_scope.md Q1 LOCKED).

# Slipping definition: mastered + violation within last N games.
SLIPPING_N_GAMES = 10

# Per-family downgrade strings. Family prefix → 6-8 word reminder.
DOWNGRADE_BY_FAMILY = {
    "TAC_": "Quick check — anything hanging here?",
    "OP_":  "You know this opening shape — careful.",
    "MID_": "Trade defenders, keep attackers — quick reminder.",
    "END_": "Endgame technique — you've got this one.",
    "DEF_": "King safety — quick check.",
    "STR_": "Long-term plan — stay on theme.",
}

GATE_SHOW = "show"  # learning + unseen + no_concept → SHOW (default)


async def get_concept_mastery_state(
    db,
    user_id: str,
    concept_id: Optional[str],
) -> str:
    """Return one of: 'mastered', 'slipping', 'learning', 'unseen'.

    'mastered'  — user_concept_understanding row has mastered_at set
                  AND no violation within last SLIPPING_N_GAMES games
    'slipping'  — has mastered_at AND has a violation in last N games
    'learning'  — row exists, mastered_at is null
    'unseen'    — no row OR no concept_id at all
    """
    if not concept_id or not user_id:
        return "unseen"

    row = await db.user_concept_understanding.find_one(
        {"user_id": user_id, "concept_id": concept_id},
        {"_id": 0, "mastered_at": 1, "last_violation_at": 1,
         "last_evaluated_game_id": 1},
    )
    if not row:
        return "unseen"
    if not row.get("mastered_at"):
        return "learning"
    last_violation = row.get("last_violation_at")
    if not last_violation:
        return "mastered"
    # Slipping check: count games imported AFTER last_violation. If
    # fewer than SLIPPING_N_GAMES, the violation is "recent" → slipping.
    try:
        count = await db.games.count_documents({
            "user_id": user_id,
            "is_analyzed": True,
            "imported_at": {"$gt": last_violation if isinstance(last_violation, str) else last_violation.isoformat()},
        })
        if count < SLIPPING_N_GAMES:
            return "slipping"
        return "mastered"
    except Exception:
        # If the count fails we'd rather show full coaching than risk
        # suppressing a real warning — fall through to mastered only if
        # we KNOW the violation is old; here we don't, so be cautious.
        return "slipping"


def _family_prefix(concept_id: str) -> str:
    """Map a concept_id to its family prefix used by DOWNGRADE_BY_FAMILY."""
    if not concept_id:
        return ""
    for p in ("TAC_", "OP_", "MID_", "END_", "DEF_", "STR_"):
        if concept_id.startswith(p):
            return p
    return ""


def gate_decision_for_concept(
    state: str,
    concept_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Translate a concept's mastery state into a gate decision.

    Returns:
        {
          "decision":       "suppress" | "downgrade" | "show",
          "reason":         short tag for logging
          "downgrade_text": brief reminder string (only when downgrade);
                            "" otherwise
        }

    SUPPRESS = mastered (drop the message entirely)
    DOWNGRADE = slipping (replace with brief reminder)
    SHOW    = learning, unseen, or no signal (no change)
    """
    if state == "mastered":
        return {
            "decision": GATE_SUPPRESS,
            "reason": "mastered",
            "downgrade_text": "",
        }
    if state == "slipping":
        family = _family_prefix(concept_id or "")
        text = DOWNGRADE_BY_FAMILY.get(family, "Quick check on this pattern.")
        return {
            "decision": GATE_DOWNGRADE,
            "reason": "slipping",
            "downgrade_text": text,
        }
    # learning, unseen, anything else → SHOW
    return {
        "decision": GATE_SHOW,
        "reason": state or "unknown",
        "downgrade_text": "",
    }


async def log_gate_event(
    db,
    *,
    user_id: str,
    session_id: str,
    concept_id: Optional[str],
    state: str,
    decision: str,
    move_number: Optional[int] = None,
) -> None:
    """Telemetry write per scope §3. Best-effort; never raises."""
    try:
        from datetime import datetime, timezone
        await db.pwc_skill_gate_events.insert_one({
            "user_id": user_id,
            "session_id": session_id,
            "concept_id": concept_id,
            "mastery_state": state,
            "gate_decision": decision,
            "move_number": move_number,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.debug(f"[pwc_skill_gate] event log failed (non-fatal): {e}")


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
