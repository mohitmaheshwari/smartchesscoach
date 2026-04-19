"""
Focus Resolver — single source of truth for "what should the user work on now?"

The curriculum brain (postgame_analysis._pick_prescription) writes
coach_memory.learning.current_focus after every game. This module resolves
that value into the exact keys each screen needs (cognitive-gap pattern,
game_reason category, training query param), with a sanity check against
the latest aggregated top problem.

Sanity check:
  If current_focus is stale or the fresh aggregate disagrees by a large
  margin (3x more frequent), trust the fresh aggregate instead.
"""

from typing import Any, Dict, List, Optional

# ── MAPPINGS ──────────────────────────────────────────────────────────

# prescription key (from _pick_prescription)  →  cognitive-gap pattern
# (used by /training/pattern-puzzles and puzzle extraction)
FOCUS_TO_GAP = {
    "hanging_piece":   "piece_safety",
    "missed_fork":     "missed_tactic",
    "missed_pin":      "missed_tactic",
    "missed_skewer":   "missed_tactic",
    "missed_discovery": "missed_tactic",
    "missed_overload":  "missed_tactic",
    "king_safety":     "king_safety",
    "tactical_error":  "tactical_oversight",
}

# prescription key  →  game_reason category (used by top_problems in Lab)
FOCUS_TO_CATEGORY = {
    "hanging_piece":   "one_move_blunder",
    "missed_fork":     "tactical_miss",
    "missed_pin":      "tactical_miss",
    "missed_skewer":   "tactical_miss",
    "missed_discovery": "tactical_miss",
    "missed_overload":  "tactical_miss",
    "king_safety":     "one_move_blunder",
    "tactical_error":  "calculation_error",
}

# game_reason category  →  cognitive-gap pattern
CATEGORY_TO_GAP = {
    "threw_winning":     "calculation_depth",
    "tactical_miss":     "tactical_oversight",
    "one_move_blunder":  "piece_safety",
    "calculation_error": "calculation_depth",
    "time_collapse":     "calculation_depth",
    "opening_disaster":  "opening_knowledge",
    "endgame_collapse":  "endgame_technique",
    "positional":        "piece_activity",
}

# Friendly labels for each focus type (what to show on buttons, home, etc.)
FOCUS_LABELS = {
    "hanging_piece":    "Stop hanging pieces",
    "missed_fork":      "Spot forks",
    "missed_pin":       "Spot pins",
    "missed_skewer":    "Spot skewers",
    "missed_discovery": "Spot discovered attacks",
    "missed_overload":  "Spot overloaded defenders",
    "king_safety":      "Keep your king safe",
    "tactical_error":   "Calculate one move deeper",
}


def _parse_prefix_focus(focus: str) -> Optional[Dict[str, str]]:
    """trap:xxx / opening:xxx / endgame:xxx  →  normalized dict."""
    if not focus or ":" not in focus:
        return None
    kind, _, rest = focus.partition(":")
    kind = kind.strip().lower()
    if kind == "trap":
        return {
            "focus_kind": "trap",
            "gap": "opening_knowledge",
            "category": "opening_disaster",
            "label": f"Learn the {rest.replace('_', ' ')} trap",
        }
    if kind == "opening":
        return {
            "focus_kind": "opening",
            "gap": "opening_knowledge",
            "category": "opening_disaster",
            "label": f"Learn the {rest.replace('_', ' ').replace('-', ' ').title()}",
        }
    if kind == "endgame":
        return {
            "focus_kind": "endgame",
            "gap": "endgame_technique",
            "category": "endgame_collapse",
            "label": f"Master {rest.replace('_', ' ')}",
        }
    return None


async def get_active_focus(
    db,
    user_id: str,
    top_problems: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Return the single source of truth for what the user should work on.

    Priority:
      1. coach_memory.learning.current_focus  (the brain's decision)
         — sanity-checked against fresh aggregate
      2. top_problems[0] from game_reason aggregator (fallback)

    Returns:
      {
        "focus":            prescription key or game_reason category,
        "category":         game_reason category ("one_move_blunder" etc.),
        "gap":              cognitive-gap pattern for puzzles,
        "label":            friendly button text,
        "reason":           sentence explaining why this is the focus,
        "type":             "pattern_drill" | "trap_lesson" | "opening_lesson" | "endgame_lesson" | "aggregate",
        "source":           "brain" | "aggregate" | "none",
        "brain_focus":      raw current_focus (for diagnostics),
        "aggregate_focus":  raw top_problems[0] category (for diagnostics),
      }
    """
    result: Dict[str, Any] = {
        "focus": None,
        "category": None,
        "gap": None,
        "label": None,
        "reason": None,
        "type": None,
        "source": "none",
        "brain_focus": None,
        "aggregate_focus": None,
    }

    # 1. Read the brain's decision
    memory = await db.coach_memory.find_one({"user_id": user_id}, {"learning": 1})
    brain_focus = None
    if memory:
        brain_focus = (memory.get("learning") or {}).get("current_focus")
    result["brain_focus"] = brain_focus

    # 2. Read the fresh aggregate
    agg_category = None
    agg_count = 0
    if top_problems:
        agg_category = top_problems[0].get("category")
        agg_count = top_problems[0].get("count", 0)
    result["aggregate_focus"] = agg_category

    # 3. Prefer the brain when present, with sanity-check vs aggregate
    if brain_focus:
        # Prefix-form (trap: / opening: / endgame:)
        prefix = _parse_prefix_focus(brain_focus)
        if prefix:
            # For prefix-forms, just read latest prescription for the reason
            latest = await db.postgame_analyses.find_one(
                {"user_id": user_id, "coach_prescription": brain_focus},
                sort=[("created_at", -1)],
                projection={"prescription_reason": 1, "prescription_type": 1},
            )
            result.update({
                "focus": brain_focus,
                "category": prefix["category"],
                "gap": prefix["gap"],
                "label": prefix["label"],
                "reason": (latest or {}).get("prescription_reason") or prefix["label"],
                "type": (latest or {}).get("prescription_type") or f"{prefix['focus_kind']}_lesson",
                "source": "brain",
            })
            # Sanity check: if aggregate dominates and disagrees, override
            if _aggregate_overrides(result["category"], agg_category, agg_count, top_problems):
                _fill_from_aggregate(result, top_problems[0])
            return result

        # Pattern-drill form
        gap = FOCUS_TO_GAP.get(brain_focus)
        category = FOCUS_TO_CATEGORY.get(brain_focus)
        if gap and category:
            latest = await db.postgame_analyses.find_one(
                {"user_id": user_id, "coach_prescription": brain_focus},
                sort=[("created_at", -1)],
                projection={"prescription_reason": 1, "prescription_type": 1},
            )
            result.update({
                "focus": brain_focus,
                "category": category,
                "gap": gap,
                "label": FOCUS_LABELS.get(brain_focus, brain_focus.replace("_", " ").title()),
                "reason": (latest or {}).get("prescription_reason")
                          or FOCUS_LABELS.get(brain_focus, "Let's work on this."),
                "type": (latest or {}).get("prescription_type") or "pattern_drill",
                "source": "brain",
            })
            # Sanity check vs aggregate
            if _aggregate_overrides(category, agg_category, agg_count, top_problems):
                _fill_from_aggregate(result, top_problems[0])
            return result

    # 4. No usable brain focus → fall back to aggregate
    if top_problems:
        _fill_from_aggregate(result, top_problems[0])
        return result

    return result


def _aggregate_overrides(
    brain_category: Optional[str],
    agg_category: Optional[str],
    agg_count: int,
    top_problems: Optional[List[Dict]],
) -> bool:
    """
    The brain can get stuck. If the fresh aggregate's #1 category is NOT
    what the brain picked, AND its count is 3x+ larger than the brain
    category's appearance in the aggregate, trust the aggregate.
    """
    if not agg_category or not brain_category or agg_category == brain_category:
        return False
    if agg_count < 3:
        return False  # Not enough signal to override
    # Find brain category in top_problems
    brain_in_agg = next(
        (tp.get("count", 0) for tp in (top_problems or []) if tp.get("category") == brain_category),
        0,
    )
    return agg_count >= 3 * max(brain_in_agg, 1)


def _fill_from_aggregate(result: Dict[str, Any], top_problem: Dict):
    """Populate result dict from the aggregated top problem."""
    cat = top_problem.get("category")
    count = top_problem.get("count", 0)
    result.update({
        "focus": cat,
        "category": cat,
        "gap": CATEGORY_TO_GAP.get(cat, cat),
        "label": top_problem.get("label") or cat,
        "reason": (
            "This is happening in almost every game." if count >= 8
            else f"This happened in {count} of your recent games."
        ),
        "type": "aggregate",
        "source": "aggregate",
    })


def reorder_top_problems_by_focus(
    top_problems: List[Dict],
    focus_category: Optional[str],
) -> List[Dict]:
    """Move the focus category to position 0 so every screen agrees."""
    if not focus_category or not top_problems:
        return top_problems
    for i, tp in enumerate(top_problems):
        if tp.get("category") == focus_category:
            if i == 0:
                return top_problems
            return [tp] + top_problems[:i] + top_problems[i + 1:]
    # Focus category not present in aggregate — prepend a synthetic entry
    return [{
        "category": focus_category,
        "label": focus_category.replace("_", " ").title(),
        "description": "",
        "count": 0,
        "example_moves": [],
        "_from_brain": True,
    }] + top_problems
