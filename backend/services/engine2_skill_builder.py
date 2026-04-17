"""
Engine 2 — Build New Skills (forward-looking)

When Engine 1 (Fix Your Mess) has no active focus, Engine 2 picks the next
skill the student is READY to learn.

A skill is READY if:
  - prerequisites_learned AND
  - rating_in_range AND
  - not_learned AND
  - (low_exposure OR high_failure)

Selection: score = exploration*0.4 + struggle*0.6, pick max.

12 skills total. Do not expand without product decision.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TREE_PATH = Path(__file__).resolve().parent.parent / "data" / "coaching" / "skill_tree.json"
_TREE_CACHE: Optional[Dict] = None


def _load_tree() -> Dict:
    """Load and cache the skill tree JSON."""
    global _TREE_CACHE
    if _TREE_CACHE is None:
        try:
            with open(_TREE_PATH, "r", encoding="utf-8") as f:
                _TREE_CACHE = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load skill tree: {e}")
            _TREE_CACHE = {"skills": {}}
    return _TREE_CACHE


def _get_skill_stats(memory, skill_id: str) -> Tuple[int, int, int]:
    """Return (seen, correct, failed) for a skill from memory.learning.skills."""
    skills = getattr(memory.learning, "skills", []) or []
    for s in skills:
        if s.skill_id == skill_id:
            return s.seen, s.correct, s.wrong
    return 0, 0, 0


def _is_learned(memory, skill_id: str) -> bool:
    """A skill is learned if it's in any of the learned lists OR its SkillProgress.is_learned() is true."""
    learning = memory.learning
    # Quick check: in any learned list?
    if skill_id in (learning.openings_learned or []):
        return True
    if skill_id in (learning.traps_learned or []):
        return True
    if skill_id in (learning.endgames_learned or []):
        return True
    if skill_id in (learning.concepts_mastered or []):
        return True
    # Check skill progress directly
    for s in (getattr(learning, "skills", []) or []):
        if s.skill_id == skill_id and s.is_learned():
            return True
    return False


def _prerequisites_met(memory, skill_id: str, tree: Dict) -> bool:
    """All prerequisites of this skill must be learned."""
    skill = tree["skills"].get(skill_id, {})
    prereqs = skill.get("prerequisites", [])
    for p in prereqs:
        if not _is_learned(memory, p):
            return False
    return True


def _rating_ok(skill_id: str, user_rating: int, tree: Dict) -> bool:
    """Student's rating must be within the skill's range."""
    skill = tree["skills"].get(skill_id, {})
    rmin = skill.get("rating_min", 0)
    rmax = skill.get("rating_max", 9999)
    return rmin <= user_rating <= rmax


def _low_exposure_or_high_failure(memory, skill_id: str) -> bool:
    """Relevance signal: student hasn't seen it much, OR is failing at it."""
    seen, correct, failed = _get_skill_stats(memory, skill_id)
    if seen < 3:
        return True  # Low exposure — worth introducing
    failure_rate = failed / max(1, seen)
    return failure_rate >= 0.4  # Struggling — worth teaching


def find_ready_skills(memory, user_rating: int) -> List[str]:
    """
    Return list of skill_ids that are READY to teach.

    A skill is READY when all four conditions hold:
      - prerequisites learned
      - rating in range
      - not already learned
      - low exposure OR high failure rate
    """
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
    """
    Score = exploration * 0.4 + struggle * 0.6

    - exploration_score = 1 / (1 + seen)  -> high for new skills
    - struggle_score = failed / max(1, seen)  -> high for struggling skills

    A struggling skill always beats a new one (weighted 0.6 vs 0.4).
    """
    seen, correct, failed = _get_skill_stats(memory, skill_id)
    exploration = 1.0 / (1.0 + seen)
    struggle = failed / max(1, seen)
    return exploration * 0.4 + struggle * 0.6


def pick_next_skill(memory, user_rating: int) -> Optional[Dict]:
    """
    Pick the single next skill to teach. Returns dict with skill details,
    or None if nothing is ready.

    Call this when Engine 1 has no active focus (e.g., clean games, no
    persistent weakness, new user).
    """
    ready = find_ready_skills(memory, user_rating)
    if not ready:
        return None

    ready.sort(key=lambda sid: score_skill(memory, sid), reverse=True)
    best_id = ready[0]

    tree = _load_tree()
    skill = tree["skills"].get(best_id, {})
    seen, correct, failed = _get_skill_stats(memory, best_id)

    # Reason explains WHY this skill now
    failure_rate = failed / max(1, seen) if seen > 0 else 0
    if seen == 0:
        reason = f"You haven't seen this before — ready to learn it."
    elif failure_rate >= 0.5:
        reason = f"You're struggling here ({failed}/{seen} failed). Let's fix it."
    elif failure_rate >= 0.3:
        reason = f"This keeps tripping you up ({failed}/{seen} failed)."
    else:
        reason = f"Next natural skill based on your progress."

    return {
        "skill_id": best_id,
        "label": skill.get("label", best_id.replace("_", " ").title()),
        "fixes": skill.get("fixes", ""),
        "reason": reason,
        "tier": skill.get("tier", 0),
        "stats": {
            "seen": seen,
            "correct": correct,
            "failed": failed,
            "score": round(score_skill(memory, best_id), 3),
        },
    }
