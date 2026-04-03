"""
Pattern Decay Service
=====================

Implements recency-weighted scoring for mistake patterns.
Instead of raw counts, each occurrence decays based on how many games ago
it happened, and consecutive clean games provide recovery credit.

States:
  - ACTIVE:   score > 2, clean streak < 2  → "X times recently. Let's fix it."
  - DECLINING: score 1-2, clean streak >= 3 → "Was a problem (X), clean for Y games."
  - FADING:   score < 1                    → Don't prioritize this pattern.
"""

import math
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

DECAY_RATE = 0.85  # Each game back multiplies by this
RECOVERY_CREDIT_PER_GAME = 0.3  # Each consecutive clean game subtracts this


def compute_pattern_scores(
    enriched_games: List[Dict],
    max_games: int = 20,
) -> Dict[str, Dict]:
    """
    Given a list of enriched games (newest first), compute
    recency-weighted scores for each cognitive gap pattern.

    Returns: {
        "piece_safety": {
            "raw_count": 8,
            "weighted_score": 3.2,
            "clean_streak": 0,
            "state": "active",
            "display_count": 3,
            "message": "...",
            "games_with_pattern": [game_id1, game_id2, ...],
        },
        ...
    }
    """
    games = enriched_games[:max_games]

    # First pass: collect all patterns and their per-game presence
    all_patterns = set()
    for g in games:
        for gap in g.get("cognitive_gaps", []):
            all_patterns.add(gap)

    scores = {}
    for pattern in all_patterns:
        weighted = 0.0
        raw_count = 0
        clean_streak = 0
        clean_streak_set = False
        games_with = []

        for i, g in enumerate(games):
            has_pattern = pattern in g.get("cognitive_gaps", [])

            if has_pattern:
                weight = DECAY_RATE ** i
                weighted += weight
                raw_count += 1
                games_with.append(g.get("game_id", ""))
                if not clean_streak_set:
                    clean_streak_set = True  # streak broken
            else:
                if not clean_streak_set:
                    clean_streak += 1

        # Apply recovery credit
        recovery = clean_streak * RECOVERY_CREDIT_PER_GAME
        effective_score = max(0, weighted - recovery)

        # Determine state
        if effective_score < 1:
            state = "fading"
        elif clean_streak >= 3 and effective_score <= 2:
            state = "declining"
        else:
            state = "active"

        # Display count: round the effective score to a human-friendly integer
        display_count = max(1, round(effective_score)) if raw_count > 0 else 0

        # Recent count (last 15 games only)
        recent_raw = sum(
            1 for g in games[:15]
            if pattern in g.get("cognitive_gaps", [])
        )

        scores[pattern] = {
            "raw_count": raw_count,
            "recent_raw": recent_raw,
            "weighted_score": round(effective_score, 2),
            "clean_streak": clean_streak,
            "state": state,
            "display_count": display_count,
            "games_with_pattern": games_with,
        }

    return scores


def build_pick_message(
    pattern: str,
    score_data: Dict,
    game: Dict,
) -> str:
    """Build the coach's pick reason message based on pattern state."""
    readable = pattern.replace("_", " ")
    state = score_data["state"]
    display = score_data["display_count"]
    clean = score_data["clean_streak"]
    lesson = game.get("lesson", "")

    if state == "declining":
        msg = (
            f"This used to be a problem — {readable} showed up {score_data['recent_raw']} times recently, "
            f"but you've been clean for {clean} game{'s' if clean != 1 else ''}. "
            f"Let's lock it in with one more review."
        )
    elif state == "active":
        if lesson:
            msg = f'I keep seeing this pattern: "{lesson}" — {display} time{"s" if display != 1 else ""} recently. Let\'s fix it here.'
        else:
            msg = f"You've made this mistake ({readable}) {display} time{'s' if display != 1 else ''} recently. Let's fix it here."
    else:
        msg = f"A past pattern ({readable}) — worth a quick refresh."

    return msg


def pick_best_game(
    unreviewed: List[Dict],
    pattern_scores: Dict[str, Dict],
) -> Tuple[Dict, str, str, Dict]:
    """
    Pick the best unreviewed game to review based on pattern scores.

    Returns: (game, pick_reason, pattern_key, score_data) or (None, "", "", {})
    """
    best_game = None
    best_reason = ""
    best_pattern = ""
    best_score_data = {}
    best_effective = -1

    for g in unreviewed:
        # Skip clean wins
        if g.get("result") == "W" and g.get("blunders", 0) == 0:
            continue

        for gap in g.get("cognitive_gaps", []):
            sd = pattern_scores.get(gap)
            if not sd or sd["state"] == "fading":
                continue
            if sd["weighted_score"] > best_effective:
                best_effective = sd["weighted_score"]
                best_game = g
                best_pattern = gap
                best_score_data = sd

    if best_game and best_pattern:
        best_reason = build_pick_message(best_pattern, best_score_data, best_game)

    return best_game, best_reason, best_pattern, best_score_data
