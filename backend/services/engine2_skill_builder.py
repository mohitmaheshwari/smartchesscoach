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
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TREE_PATH = Path(__file__).resolve().parent.parent / "data" / "coaching" / "skill_tree.json"
_TREE_CACHE: Optional[Dict] = None


_CURRICULUM_PATH = Path(__file__).resolve().parent.parent / "data" / "opening_curriculum.json"


def _augment_openings_from_curriculum(skills: Dict) -> None:
    """Derive a tracking skill for every curriculum opening that doesn't already
    have one — so adding an opening to opening_curriculum.json is the ONLY step
    and the skill tree can never fall out of sync (Mohit 2026-06-09: English was
    in the curriculum but missing here, so it never showed on the progress page).

    Additive + best-effort: existing entries are preserved (never clobbered), and
    a curriculum load failure leaves the tree exactly as authored. Auto-assigns a
    tier (white openings -> T2, defences/gambit-responses -> T3); tunable by adding
    an explicit entry to skill_tree.json, which wins (we only fill gaps)."""
    try:
        with open(_CURRICULUM_PATH, "r", encoding="utf-8") as f:
            cur = json.load(f)
    except Exception as e:
        logger.warning(f"[skill-tree] curriculum augment skipped: {e}")
        return
    from services.curriculum_content_validator import get_publishable_content_ids

    publishable = get_publishable_content_ids("openings")
    tracked = {
        v.get("content_ref") for v in skills.values()
        if isinstance(v, dict) and v.get("kind") == "opening"
    }
    for ck, co in cur.items():
        if (
            ck.startswith("_")
            or not isinstance(co, dict)
            or ck in tracked
            or ck not in publishable
        ):
            continue
        color = co.get("color", "white")
        name = co.get("name", ck.replace("_", " ").title())
        tier = 2 if (color == "white" and ck not in
                     ("modern_defense", "philidor_defense", "englund_gambit_response")) else 3
        skills[f"opening_{ck}"] = {
            "kind": "opening",
            "label": f"{name} ({'White' if color == 'white' else 'Black'})",
            "fixes": "expanding your opening repertoire",
            "content_ref": ck,
            "prerequisites": [],
            "rating_min": 1400 if tier == 2 else 1800,
            "rating_max": 1799 if tier == 2 else 9999,
            "tier": tier,
        }
        logger.info(f"[skill-tree] derived opening skill from curriculum: opening_{ck}")


def _augment_trap_sets_from_catalog(skills: Dict) -> None:
    """Derive one trap-set skill for each verified, teachable opening family.

    Rating and tier are inherited from the matching opening lesson. This adds
    no new rating threshold and prevents a trap family from being recommended
    before its opening foundation.
    """
    try:
        from services.curriculum_content_validator import (
            get_defense_ready_trap_ids,
            trap_content_id,
        )
        from services.trap_library import TRAP_LIBRARY
    except Exception as exc:
        logger.warning(f"[skill-tree] trap-set augment skipped: {exc}")
        return

    ready = get_defense_ready_trap_ids()
    tracked = {
        str(node.get("content_ref") or "").replace("_", "-")
        for node in skills.values()
        if isinstance(node, dict) and node.get("kind") == "trap_set"
    }
    opening_skills = [
        (skill_id, node)
        for skill_id, node in skills.items()
        if isinstance(node, dict) and node.get("kind") == "opening"
    ]
    for opening_key, traps in TRAP_LIBRARY.items():
        if opening_key in tracked:
            continue
        publishable = [
            trap
            for trap in traps
            if trap_content_id(opening_key, trap.get("name", "")) in ready
        ]
        if not publishable:
            continue
        opening_match = next(
            (
                (skill_id, node)
                for skill_id, node in opening_skills
                if str(node.get("content_ref") or "").replace("_", "-")
                == opening_key
            ),
            None,
        )
        if not opening_match:
            # The trap remains available in Explore. Personalized selection
            # waits until its opening has a rating-banded foundation.
            continue
        prerequisite, opening_node = opening_match
        skill_id = f"trap_set_{opening_key.replace('-', '_')}"
        if skill_id in skills:
            continue
        opening_label = str(opening_node.get("label") or opening_key).split(" (")[0]
        skills[skill_id] = {
            "kind": "trap_set",
            "label": f"{opening_label} traps",
            "fixes": f"missing traps in the {opening_label}",
            "content_ref": opening_key,
            "prerequisites": [prerequisite],
            "rating_min": opening_node.get("rating_min", 0),
            "rating_max": opening_node.get("rating_max", 9999),
            "tier": opening_node.get("tier", 1),
        }


def _augment_endgames_from_catalog(skills: Dict) -> None:
    """Derive missing verified endgames using existing category envelopes.

    A category is expanded only when an authored skill already establishes its
    tier/rating envelope. Bishop and knight categories therefore remain Explore
    content until their selection range is data-locked.
    """
    try:
        from services.endgame_theory_service import (
            get_all_categories,
            resolve_content_ref,
        )
    except Exception as exc:
        logger.warning(f"[skill-tree] endgame augment skipped: {exc}")
        return

    tracked_ids = set()
    category_envelopes: Dict[str, Dict] = {}
    for node in skills.values():
        if not isinstance(node, dict) or node.get("kind") not in {
            "endgame", "mate_pattern"
        }:
            continue
        resolved = resolve_content_ref(str(node.get("content_ref") or ""))
        if not resolved:
            continue
        tracked_ids.add(resolved["lesson_id"])
        category_envelopes.setdefault(resolved["category_key"], node)

    for category in get_all_categories():
        category_key = str(category["key"])
        envelope = category_envelopes.get(category_key)
        if not envelope:
            continue
        for lesson in category.get("lessons") or ():
            lesson_id = str(lesson["lesson_id"])
            if lesson_id in tracked_ids:
                continue
            lesson_key = str(lesson["key"])
            skill_id = f"endgame_{lesson_key}"
            if skill_id in skills:
                continue
            skills[skill_id] = {
                "kind": "endgame",
                "label": lesson["name"],
                "fixes": lesson["description"],
                "content_ref": lesson_id,
                "prerequisites": list(envelope.get("prerequisites") or ()),
                "rating_min": envelope.get("rating_min", 0),
                "rating_max": envelope.get("rating_max", 9999),
                "tier": envelope.get("tier", 1),
            }
            tracked_ids.add(lesson_id)


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
            # Auto-derive any curriculum opening missing a tracking skill, so the
            # tree stays in sync with the curriculum without manual edits.
            _augment_openings_from_curriculum(skills)
            _augment_trap_sets_from_catalog(skills)
            _augment_endgames_from_catalog(skills)
            _TREE_CACHE = {"skills": skills, "_meta": raw.get("_meta", {})}
        except Exception as e:
            logger.error(f"Failed to load skill tree: {e}")
            _TREE_CACHE = {"skills": {}}
    return _TREE_CACHE


def reload_tree() -> None:
    """Force-reload the tree. Mostly for tests."""
    global _TREE_CACHE
    _TREE_CACHE = None


def get_skill_tree_snapshot() -> Dict:
    """Return a detached snapshot for read-only composition/audit layers."""
    return deepcopy(_load_tree())


def _identity_token(value: object) -> str:
    """Normalize separators only; never use fuzzy chess-name matching."""
    return str(value or "").strip().lower().replace("-", "_")


def _compatible_skill_kind(requested: str, stored: str) -> bool:
    requested = str(requested or "").strip().lower()
    stored = str(stored or "").strip().lower()
    if requested == stored:
        return True
    # Mate lessons use the endgame workspace even though the curriculum keeps
    # them as a distinct selection kind.
    return requested == "endgame" and stored == "mate_pattern"


def _content_identity_tokens(kind: str, content_ref: object) -> set[str]:
    """Return canonical identifiers owned by the existing content registry."""
    raw = str(content_ref or "").strip()
    if not raw:
        return set()
    tokens = {_identity_token(raw)}
    requested_kind = str(kind or "").strip().lower()
    if requested_kind == "opening":
        try:
            from services.opening_theory_json_service import resolve_opening_key

            resolved = resolve_opening_key(raw)
            if resolved:
                tokens.add(_identity_token(resolved))
        except (KeyError, TypeError, ValueError):
            pass
    elif requested_kind == "endgame":
        try:
            from services.endgame_theory_service import resolve_content_ref

            resolved = resolve_content_ref(raw)
            if resolved:
                tokens.add(_identity_token(resolved.get("lesson_id")))
                tokens.add(_identity_token(resolved.get("lesson_key")))
        except (KeyError, TypeError, ValueError):
            pass
    return {token for token in tokens if token}


def resolve_skill_id(
    content_kind: str,
    content_ref: str,
    *,
    requested_skill_id: Optional[str] = None,
) -> str:
    """Join a canonical lesson identity to its one Engine 2 tracking id.

    The skill tree remains the sole owner of this relationship. Callers may
    supply an exact skill id, but content ids such as ``london_system`` or
    ``king_and_pawn/square_rule`` are resolved through the same tree instead
    of being copied into session history as parallel identities.
    """
    tree = _load_tree()
    skills = tree.get("skills", {})
    requested = str(requested_skill_id or "").strip()
    if requested:
        node = skills.get(requested)
        if node and _compatible_skill_kind(content_kind, node.get("kind")):
            return requested

    wanted = _content_identity_tokens(content_kind, content_ref)
    matches = []
    for skill_id, node in skills.items():
        if not _compatible_skill_kind(content_kind, node.get("kind")):
            continue
        node_tokens = _content_identity_tokens(content_kind, node.get("content_ref"))
        if wanted.intersection(node_tokens):
            matches.append(skill_id)
    if len(matches) == 1:
        return matches[0]

    # Engine 1 repair topics (for example piece_safety) intentionally do not
    # live in the Engine 2 tree. Preserve their exact existing identity.
    return requested or str(content_ref or "").strip()


def lesson_skill_aliases(
    content_kind: str,
    content_ref: str,
    *,
    requested_skill_id: Optional[str] = None,
) -> Tuple[str, ...]:
    """Exact migration aliases for reading pre-canonical lesson history."""
    canonical = resolve_skill_id(
        content_kind,
        content_ref,
        requested_skill_id=requested_skill_id,
    )
    aliases = []
    for candidate in (canonical, requested_skill_id, content_ref):
        text = str(candidate or "").strip()
        if text and text not in aliases:
            aliases.append(text)
    node = get_skill_node(canonical)
    node_ref = str((node or {}).get("content_ref") or "").strip()
    if node_ref and node_ref not in aliases:
        aliases.append(node_ref)
    if str(content_kind or "").strip().lower() == "endgame":
        try:
            from services.endgame_theory_service import resolve_content_ref

            for candidate in (content_ref, node_ref):
                resolved = resolve_content_ref(str(candidate or ""))
                lesson_id = str((resolved or {}).get("lesson_id") or "")
                if lesson_id and lesson_id not in aliases:
                    aliases.append(lesson_id)
        except (KeyError, TypeError, ValueError):
            pass
    return tuple(aliases)


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
        # Mohit 2026-06-01 ("what makes you think I don't know this?"):
        # When seen == 0 the system has NO evidence either way. Earlier
        # copy ("You haven't learned this yet — you're ready") asserted
        # absence of knowledge as a fact, which for a higher-rated user
        # who happens to not have hit the in-game detector or the lesson
        # page yet reads as presumptuous. Be honest about what the
        # system actually knows: it hasn't observed you applying this.
        reason = "Haven't seen you use this in a game yet — worth a quick check?"
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
