"""
Root Behavior Engine
=====================

Collapses individual signals into behavioral clusters.
Detects the ONE dominant problem. Everything aligns to it.

5 clusters:
  1. Threat Awareness (Tier 1) — not looking at opponent
  2. Calculation (Tier 1) — not calculating consequences
  3. Patience (Tier 2) — rushing instead of building
  4. Coordination (Tier 2) — pieces not working together
  5. Planning (Tier 3) — playing moves, not a plan

Usage:
    result = detect_root_problem(behavior_counts, thinking_scores, problems)
    # {"primary": {...}, "secondary": [...], "minor": [...]}
"""

from typing import Dict, List, Optional


# ─── CLUSTER DEFINITIONS ─────────────────────────────────────────

ROOT_CLUSTERS = {
    "threat_awareness": {
        "label": "Threat Awareness",
        "description": "You are not checking what your opponent is doing",
        "coaching": "Before every move, ask: what is my opponent threatening?",
        "signals": ["ignored_threat", "hung_pieces", "king_safety", "missed_capture"],
        "tier": 1,
    },
    "calculation": {
        "label": "Calculation Discipline",
        "description": "You are moving without calculating consequences",
        "coaching": "Before committing, trace 2 moves ahead. What can your opponent do?",
        "signals": ["blunder", "one_move_blunder", "complex_tactical_miss", "move_verification"],
        "tier": 1,
    },
    "patience": {
        "label": "Patience & Timing",
        "description": "You are rushing instead of building your position",
        "coaching": "Finish your setup before starting action. Development first.",
        "signals": ["premature_attack", "random_move", "threw_winning"],
        "tier": 2,
    },
    "coordination": {
        "label": "Piece Coordination",
        "description": "Your pieces are not working together",
        "coaching": "Connect your pieces. Make sure they defend each other.",
        "signals": ["loose_pieces", "weak_development", "disconnected_pieces"],
        "tier": 2,
    },
    "planning": {
        "label": "Planning & Direction",
        "description": "You are playing moves, not a plan",
        "coaching": "Before each move, ask: what am I trying to achieve in the next 3 moves?",
        "signals": ["no_plan", "aimless_moves"],
        "tier": 3,
    },
}

# Minimum score to be considered a real problem
MIN_THRESHOLD = 3


# ─── SCORING ──────────────────────────────────────────────────────

def score_clusters(
    behavior_counts: Dict[str, int],
    thinking_scores: List[Dict] = None,
    active_problems: List[Dict] = None,
) -> Dict[str, int]:
    """
    Score each cluster from multiple data sources.
    Higher score = bigger problem.

    Sources:
      1. behavior_counts: {signal: count} from current game or recent sessions
      2. thinking_scores: habit_scores from analyzed games
      3. active_problems: from problem_lifecycle
    """
    scores = {}

    for cluster_key, cluster in ROOT_CLUSTERS.items():
        score = 0

        # Source 1: Direct signal counts
        for signal in cluster["signals"]:
            score += behavior_counts.get(signal, 0)

        # Source 2: Thinking scores (low score = weak = add to cluster)
        if thinking_scores:
            HABIT_TO_CLUSTER = {
                "threat_awareness": "threat_awareness",
                "tactical_vision": "calculation",
                "move_verification": "calculation",
                "king_safety": "threat_awareness",
                "patience": "patience",
            }
            for ts in thinking_scores:
                habits = ts.get("habit_scores", {})
                for habit_key, target_cluster in HABIT_TO_CLUSTER.items():
                    if target_cluster != cluster_key:
                        continue
                    raw = habits.get(habit_key, {})
                    habit_score = raw.get("score", 100) if isinstance(raw, dict) else (raw if isinstance(raw, (int, float)) else 100)
                    if habit_score < 50:
                        score += 2
                    elif habit_score < 70:
                        score += 1

        # Source 3: Active problems from lifecycle
        if active_problems:
            PROBLEM_TO_CLUSTER = {
                "tactical_miss": "calculation",
                "one_move_blunder": "calculation",
                "threw_winning": "patience",
                "time_collapse": "patience",
                "opening_disaster": "coordination",
            }
            for prob in active_problems:
                cat = prob.get("category", "")
                target = PROBLEM_TO_CLUSTER.get(cat)
                if target == cluster_key:
                    score += prob.get("count", 1)

        scores[cluster_key] = score

    return scores


# ─── ROOT PROBLEM DETECTION ──────────────────────────────────────

def detect_root_problem(
    behavior_counts: Dict[str, int],
    thinking_scores: List[Dict] = None,
    active_problems: List[Dict] = None,
) -> Dict:
    """
    Detect the ONE dominant behavioral problem.

    Returns:
        {
            "primary": {"key": "threat_awareness", "label": ..., "score": 15, ...} or None,
            "secondary": [...],
            "minor": [...],
        }
    """
    scores = score_clusters(behavior_counts, thinking_scores, active_problems)

    # Sort by score descending, then by tier (lower tier = higher priority)
    ranked = sorted(
        scores.items(),
        key=lambda x: (x[1], -ROOT_CLUSTERS[x[0]]["tier"]),
        reverse=True
    )

    primary = None
    secondary = []
    minor = []

    for i, (key, score) in enumerate(ranked):
        cluster = ROOT_CLUSTERS[key]
        entry = {
            "key": key,
            "label": cluster["label"],
            "description": cluster["description"],
            "coaching": cluster["coaching"],
            "score": score,
            "tier": cluster["tier"],
        }

        if i == 0 and score >= MIN_THRESHOLD:
            primary = entry
        elif score >= 2 and len(secondary) < 3:
            secondary.append(entry)
        else:
            minor.append(entry)

    return {
        "primary": primary,
        "secondary": secondary,
        "minor": minor,
    }


# ─── FOR EVALUATE-PENDING RESPONSE ──────────────────────────────

def get_root_problem_for_session(
    behavior_summary: Optional[Dict],
    thinking_scores: List[Dict] = None,
    active_problems: List[Dict] = None,
) -> Dict:
    """
    Get root problem from session behavior data + player history.
    Called per evaluate-pending request.
    """
    counts = {}

    if behavior_summary:
        counts = behavior_summary.get("counts", {})

    return detect_root_problem(counts, thinking_scores, active_problems)
