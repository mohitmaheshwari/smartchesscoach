"""
Engine 2 — Build New Skills (forward-looking, knowledge-based)

Engine 2 teaches chess KNOWLEDGE — openings, traps, endgames, mate patterns,
strategic concepts. It is NOT for tactical mistake remediation (that's
Engine 1). Each node in the skill tree points at content in an existing
library (opening_curriculum.json, trap_library, endgame_teaching, etc.)

Node shape (from skill_tree.json v2.0):
    {
      "kind": "opening" | "trap_set" | "endgame" | "mate_pattern" | "concept" | "coached_play",
      "label": "...",
      "content_ref": "<key_into_content_library>",
      "fixes": "short sentence",
      "prerequisites": [...],
      "rating_min": N, "rating_max": N,
      "tier": 0 | 1 | 2 | 3
    }

A skill is READY when:
  - prerequisites learned AND
  - rating in range AND
  - not learned AND
  - (low exposure OR high failure) — same curiosity/struggle signal

Selection: score = exploration * 0.4 + struggle * 0.6.

The public API (pick_next_skill, find_ready_skills) is unchanged — callers
still get {skill_id, label, fixes, reason, tier, stats}. New fields added:
kind and content_ref for the frontend/today_composer to route correctly.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TREE_PATH = Path(__file__).resolve().parent.parent / "data" / "coaching" / "skill_tree.json"
_TREE_CACHE: Optional[Dict] = None


def _load_tree() -> Dict:
    """Load and cache the skill tree JSON. Filters out `_meta` and `_*_note` keys."""
    global _TREE_CACHE
    if _TREE_CACHE is None:
        try:
            with open(_TREE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Strip documentation keys (anything starting with _) from the skills dict.
            skills = {
                k: v for k, v in (raw.get("skills") or {}).items()
                if not k.startswith("_") and isinstance(v, dict)
            }
            _TREE_CACHE = {"skills": skills, "_meta": raw.get("_meta", {})}
        except Exception as e:
            logger.error(f"Failed to load skill tree: {e}")
            _TREE_CACHE = {"skills": {}}
    return _TREE_CACHE


def reload_tree() -> None:
    """Force-reload the tree. Mostly for tests."""
    global _TREE_CACHE
    _TREE_CACHE = None


def _get_skill_stats(memory, skill_id: str) -> Tuple[int, int, int]:
    """Return (seen, correct, failed) for a skill from memory.learning.skills."""
    skills = getattr(memory.learning, "skills", []) or []
    for s in skills:
        if s.skill_id == skill_id:
            return s.seen, s.correct, s.wrong
    return 0, 0, 0


def _is_learned(memory, skill_id: str) -> bool:
    """A skill is learned if it's in any learned list OR its SkillProgress.is_learned() is true.
    Learned lists are keyed by `kind`:
      opening       → openings_learned
      trap_set      → traps_learned
      endgame       → endgames_learned
      mate_pattern  → endgames_learned
      concept       → concepts_mastered
      coached_play  → concepts_mastered
    """
    learning = memory.learning

    if skill_id in (learning.openings_learned or []): return True
    if skill_id in (learning.traps_learned or []):    return True
    if skill_id in (learning.endgames_learned or []): return True
    if skill_id in (learning.concepts_mastered or []): return True

    for s in (getattr(learning, "skills", []) or []):
        if s.skill_id == skill_id and s.is_learned():
            return True
    return False


def _prerequisites_met(memory, skill_id: str, tree: Dict) -> bool:
    skill = tree["skills"].get(skill_id, {})
    for p in skill.get("prerequisites", []):
        if not _is_learned(memory, p):
            return False
    return True


def _rating_ok(skill_id: str, user_rating: int, tree: Dict) -> bool:
    skill = tree["skills"].get(skill_id, {})
    return skill.get("rating_min", 0) <= user_rating <= skill.get("rating_max", 9999)


def _low_exposure_or_high_failure(memory, skill_id: str) -> bool:
    seen, correct, failed = _get_skill_stats(memory, skill_id)
    if seen < 3:
        return True
    return (failed / max(1, seen)) >= 0.4


def find_ready_skills(memory, user_rating: int) -> List[str]:
    """skill_ids ready to teach: prereqs met + rating in range + not learned + relevant."""
    tree = _load_tree()
    ready = []
    for skill_id in tree.get("skills", {}):
        if _is_learned(memory, skill_id):
            continue
        if not _rating_ok(skill_id, user_rating, tree):
            continue
        if not _prerequisites_met(memory, skill_id, tree):
            continue
        if not _low_exposure_or_high_failure(memory, skill_id):
            continue
        ready.append(skill_id)
    return ready


def score_skill(memory, skill_id: str) -> float:
    """exploration*0.4 + struggle*0.6. Struggling beats fresh by weighting."""
    seen, correct, failed = _get_skill_stats(memory, skill_id)
    exploration = 1.0 / (1.0 + seen)
    struggle = failed / max(1, seen)
    return exploration * 0.4 + struggle * 0.6


def pick_next_skill(memory, user_rating: int) -> Optional[Dict]:
    """
    Pick the single next skill to teach. Returns a dict with:
      skill_id, label, fixes, reason, tier, kind, content_ref, stats
    (or None if nothing ready).

    `kind` and `content_ref` are new in v2.0 so the frontend knows how
    to deliver the lesson (puzzle / live game / study page).
    """
    ready = find_ready_skills(memory, user_rating)
    if not ready:
        return None

    ready.sort(key=lambda sid: score_skill(memory, sid), reverse=True)
    best_id = ready[0]

    tree = _load_tree()
    skill = tree["skills"].get(best_id, {})
    seen, correct, failed = _get_skill_stats(memory, best_id)

    # Reason explains WHY this skill now — phrased for a beginner, not technical.
    failure_rate = failed / max(1, seen) if seen > 0 else 0
    if seen == 0:
        reason = "You haven't learned this yet — you're ready."
    elif failure_rate >= 0.5:
        reason = "You've struggled with this — let's work on it."
    elif failure_rate >= 0.3:
        reason = "This has tripped you up before."
    else:
        reason = "Next natural thing for your level."

    return {
        "skill_id": best_id,
        "label": skill.get("label", best_id.replace("_", " ").title()),
        "fixes": skill.get("fixes", ""),
        "reason": reason,
        "tier": skill.get("tier", 0),
        "kind": skill.get("kind", "concept"),
        "content_ref": skill.get("content_ref"),
        "stats": {
            "seen": seen,
            "correct": correct,
            "failed": failed,
            "score": round(score_skill(memory, best_id), 3),
        },
    }


# ─── LOOKUPS FOR CALLERS ──────────────────────────────────────────────


def get_skill_node(skill_id: str) -> Optional[Dict]:
    """Return the raw node for a given skill_id, or None."""
    tree = _load_tree()
    return tree.get("skills", {}).get(skill_id)


def list_skills_by_kind(kind: str) -> List[str]:
    """Every skill_id of the given kind. Useful for the recorder."""
    tree = _load_tree()
    return [sid for sid, node in tree.get("skills", {}).items() if node.get("kind") == kind]
