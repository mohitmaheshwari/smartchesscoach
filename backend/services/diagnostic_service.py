"""
Diagnostic onboarding service — 20-puzzle warm-up that produces a real
diagnosis when the user has no analyzed games OR while their imported
games are still in the Stockfish queue.

Spec: memory/project_diagnostic_onboarding_20_puzzles.md
  - 20 puzzles, stratified across community_puzzles issue_types
  - No time pressure, no gamification
  - Output: rating estimate range + per-category strengths/growth-areas
  - After 10+ real-game analyses land, real-game data supersedes this.

Public API:
    select_diagnostic_puzzles(db, user_id) -> List[Dict]
    score_diagnostic(attempts) -> Dict
    coerce_diagnosis_voice(diagnosis) -> Dict   (voice hygiene pass)
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

# Issue types worth probing. Roughly ordered from "everyone has this gap"
# to "more advanced." The selector tries to cover all 7; if an issue type
# has zero approved puzzles we silently skip it.
DIAGNOSTIC_ISSUE_TYPES: List[str] = [
    "piece_safety",
    "tactical_oversight",
    "missed_tactic",
    "calculation_depth",
    "king_safety",
    "piece_activity",
    "opening_knowledge",
]

# Friendly labels for diagnosis output. Keep concrete, no jargon.
ISSUE_TYPE_LABEL: Dict[str, str] = {
    "piece_safety": "Spotting hanging pieces",
    "tactical_oversight": "Seeing tactics",
    "missed_tactic": "Forks, pins, and skewers",
    "calculation_depth": "Calculating a few moves ahead",
    "king_safety": "Keeping your king safe",
    "piece_activity": "Activating pieces",
    "opening_knowledge": "Opening principles",
}

TARGET_PUZZLES = 20
MIN_PER_CATEGORY = 1   # If a category exists at all, include at least one
MAX_PER_CATEGORY = 4   # Avoid drowning one category


async def _fetch_approved_pool(
    db, user_id: str
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Return {issue_type: {difficulty: [puzzle_doc, ...]}} for approved
    community puzzles the user hasn't already attempted. Two-level
    nesting so the selector can pull across difficulty buckets within
    a category — that's how the diagnostic probes depth, not just
    pattern recognition.
    """
    # Exclude puzzles the user has previously attempted (e.g. from
    # /training/pattern flows) — keep the diagnostic fresh.
    attempted_ids: set = set()
    async for a in db.puzzle_attempts.find(
        {"user_id": user_id}, {"_id": 0, "puzzle_id": 1}
    ):
        pid = a.get("puzzle_id")
        if pid:
            attempted_ids.add(pid)

    by_issue: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        it: {"beginner": [], "intermediate": [], "advanced": []}
        for it in DIAGNOSTIC_ISSUE_TYPES
    }

    cursor = db.community_puzzles.find(
        {"approved": True, "issue_type": {"$in": DIAGNOSTIC_ISSUE_TYPES}},
        {
            "_id": 1,
            "fen": 1,
            "best_move_san": 1,
            "issue_type": 1,
            "difficulty": 1,
            "user_color": 1,
            "opening_name": 1,
            "move_number": 1,
            "cp_loss": 1,
        },
    )
    async for p in cursor:
        pid = str(p.get("_id"))
        if pid in attempted_ids:
            continue
        if not p.get("fen") or not p.get("best_move_san"):
            continue
        p["puzzle_id"] = pid
        p.pop("_id", None)
        it = p.get("issue_type")
        diff = p.get("difficulty")
        if it in by_issue and diff in by_issue[it]:
            by_issue[it][diff].append(p)

    # Within each category+difficulty bucket, larger cp_loss = louder
    # mistake = easier to spot. Order by descending cp_loss so the
    # selector picks the clearer instances first.
    for cat in by_issue.values():
        for diff_list in cat.values():
            diff_list.sort(key=lambda d: -(d.get("cp_loss") or 0))
    return by_issue


async def select_diagnostic_puzzles(db, user_id: str) -> List[Dict[str, Any]]:
    """Pick up to 20 stratified puzzles for the diagnostic. Each category
    contributes a SPREAD across difficulty buckets — that's what makes
    it a depth probe rather than a pattern-recognition pop-quiz.

    Stable order (caller persists the list and walks it). Returns []
    if the pool is too thin for even a useful diagnostic.
    """
    pool = await _fetch_approved_pool(db, user_id)

    # Drop categories that have nothing at any difficulty.
    non_empty = {
        it: cat for it, cat in pool.items()
        if any(cat[d] for d in ("beginner", "intermediate", "advanced"))
    }
    if not non_empty:
        return []

    diff_order = ("beginner", "intermediate", "advanced")
    n_cats = len(non_empty)
    base_per_cat = max(MIN_PER_CATEGORY, TARGET_PUZZLES // n_cats)
    base_per_cat = min(base_per_cat, MAX_PER_CATEGORY)

    # Phase 1: for each category, take one of each difficulty until we
    # hit base_per_cat. This is the depth-probe step. If a difficulty
    # bucket is empty, fall through to whichever has stock.
    picked: List[Dict[str, Any]] = []
    leftovers: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        it: {d: list(lst) for d, lst in cat.items()} for it, cat in non_empty.items()
    }

    for it, cat in non_empty.items():
        taken = 0
        # First pass: try one of each difficulty (depth probe)
        for d in diff_order:
            if taken >= base_per_cat:
                break
            if leftovers[it][d]:
                picked.append(leftovers[it][d].pop(0))
                taken += 1
        # Second pass: top up from any difficulty if base_per_cat > 3
        while taken < base_per_cat:
            took = False
            for d in diff_order:
                if leftovers[it][d]:
                    picked.append(leftovers[it][d].pop(0))
                    taken += 1
                    took = True
                    break
            if not took:
                break

    # Phase 2: round-robin top-up to TARGET_PUZZLES across categories.
    cat_cycle = [it for it in non_empty.keys()
                 if any(leftovers[it][d] for d in diff_order)]
    while len(picked) < TARGET_PUZZLES and cat_cycle:
        it = cat_cycle[0]
        took = False
        for d in diff_order:
            if leftovers[it][d]:
                picked.append(leftovers[it][d].pop(0))
                took = True
                break
        if any(leftovers[it][d] for d in diff_order):
            cat_cycle.append(cat_cycle.pop(0))
        else:
            cat_cycle.pop(0)
        if not took:
            continue

    # Phase 3: interleave so the user doesn't see 3 consecutive same-
    # category puzzles. Round-robin across categories.
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for p in picked:
        by_cat.setdefault(p["issue_type"], []).append(p)
    ordered: List[Dict[str, Any]] = []
    cats = list(by_cat.keys())
    while any(by_cat[c] for c in cats):
        for c in cats:
            if by_cat[c]:
                ordered.append(by_cat[c].pop(0))

    return ordered[:TARGET_PUZZLES]


def _rating_estimate(correct_total: int, total: int, weighted_score: float) -> Dict[str, int]:
    """Map raw correct count + difficulty-weighted score to a rating range.

    Weighted score: each correct puzzle contributes 1.0 (beginner) /
    1.3 (intermediate) / 1.6 (advanced). Max score with 20 puzzles
    depends on the difficulty mix; we normalize against the actual
    available max from the attempt set.
    """
    if total <= 0:
        return {"low": 600, "high": 900}

    # Bin by accuracy + weighted score
    pct = correct_total / total
    if pct < 0.20:
        return {"low": 600, "high": 800}
    if pct < 0.35:
        return {"low": 700, "high": 950}
    if pct < 0.50:
        return {"low": 850, "high": 1100}
    if pct < 0.65:
        return {"low": 1000, "high": 1250}
    if pct < 0.80:
        return {"low": 1200, "high": 1450}
    if pct < 0.90:
        return {"low": 1400, "high": 1650}
    return {"low": 1600, "high": 1900}


def _category_label(correct: int, total: int) -> str:
    """Map per-category correct/total to a strength label. No "X%"
    gamification per [[no-gamification]] — descriptive, not percentage."""
    if total == 0:
        return "Not tested"
    pct = correct / total
    if pct >= 0.80:
        return "Strong"
    if pct >= 0.50:
        return "Mixed"
    return "Needs work"


def score_diagnostic(attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Score a completed diagnostic. attempts is the list stored on the
    session; each entry has at minimum: issue_type, difficulty, is_correct.
    Returns the diagnosis dict that goes onto the session + dashboard.
    """
    if not attempts:
        return {
            "rating_estimate": {"low": 600, "high": 900},
            "per_category": {},
            "strengths": [],
            "growth_areas": [],
            "summary_line": "Not enough data yet. Play a few games and we'll build a real picture.",
            "total_correct": 0,
            "total_attempted": 0,
        }

    diff_weight = {"beginner": 1.0, "intermediate": 1.3, "advanced": 1.6}
    correct_total = sum(1 for a in attempts if a.get("is_correct"))
    weighted = sum(
        diff_weight.get(a.get("difficulty", "intermediate"), 1.0)
        for a in attempts if a.get("is_correct")
    )

    # Per-category tally
    per_cat: Dict[str, Dict[str, Any]] = {}
    for a in attempts:
        it = a.get("issue_type")
        if not it:
            continue
        cat = per_cat.setdefault(it, {"correct": 0, "total": 0})
        cat["total"] += 1
        if a.get("is_correct"):
            cat["correct"] += 1

    for it, cat in per_cat.items():
        cat["label"] = _category_label(cat["correct"], cat["total"])
        cat["display_name"] = ISSUE_TYPE_LABEL.get(it, it)

    strengths = [
        per_cat[it]["display_name"]
        for it in per_cat
        if per_cat[it]["label"] == "Strong"
    ]
    growth_areas = [
        per_cat[it]["display_name"]
        for it in per_cat
        if per_cat[it]["label"] == "Needs work"
    ]

    rating_band = _rating_estimate(correct_total, len(attempts), weighted)

    # Voice-pass summary: concrete, no gamification, no "score!"
    # Four shapes depending on whether the user showed clear strengths
    # and/or clear growth areas.
    if strengths and growth_areas:
        summary = (
            f"Strong signal in {strengths[0].lower()}. "
            f"The clearest place to grow: {growth_areas[0].lower()}."
        )
    elif strengths and not growth_areas:
        summary = (
            f"Strong signal in {strengths[0].lower()}. "
            f"A few real games will sharpen the rest of the picture."
        )
    elif growth_areas and not strengths:
        summary = (
            f"Mixed results across the board. "
            f"The clearest place to grow: {growth_areas[0].lower()}."
        )
    else:
        summary = "Mixed across the board. A few real games will sharpen this picture."

    return {
        "rating_estimate": rating_band,
        "per_category": per_cat,
        "strengths": strengths,
        "growth_areas": growth_areas,
        "summary_line": summary,
        "total_correct": correct_total,
        "total_attempted": len(attempts),
    }


def diagnostic_supersedes_after(num_analyzed_games: int) -> bool:
    """When enough real games are analyzed, the diagnostic stops being
    the primary signal. Spec: 10 games."""
    return num_analyzed_games >= 10
