"""
Player Behavior Tracker
========================

Tracks 5 core behavior signals per game.
Computes top 2-3 weaknesses across recent games.
Provides focus concept and scoring bias for the decision engine.

Simple: counts + bias. No ML. No overfit.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ─── BEHAVIOR SIGNALS ─────────────────────────────────────────────

TRACKED_SIGNALS = [
    "ignored_threat",
    "hung_pieces",
    "premature_attack",
    "king_safety",
    "weak_development",
]

SIGNAL_LABELS = {
    "ignored_threat": "Checking opponent threats",
    "hung_pieces": "Piece safety",
    "premature_attack": "Coordinating before attacking",
    "king_safety": "King safety",
    "weak_development": "Completing development",
}

# How signals map from fast_eval signals to behavior categories
SIGNAL_MAPPING = {
    "ignored_threat": ["missed_threat", "ignored_capture"],
    "hung_pieces": ["hung_piece"],
    "premature_attack": ["premature_attack"],
    "king_safety": ["king_unsafe"],
    "weak_development": ["development_incomplete"],
}


# ─── PER-SESSION TRACKING ─────────────────────────────────────────

class SessionBehaviorTracker:
    """Tracks behavior signals during a single game session."""

    def __init__(self):
        self.counts: Dict[str, int] = {s: 0 for s in TRACKED_SIGNALS}
        self.move_occurrences: Dict[str, List[int]] = {s: [] for s in TRACKED_SIGNALS}
        self.total_moves = 0

    def record_signals(self, move_index: int, fast_signals: Dict):
        """Record which behavior signals triggered on this move."""
        self.total_moves += 1

        for behavior, signal_keys in SIGNAL_MAPPING.items():
            for sk in signal_keys:
                if fast_signals.get(sk):
                    self.counts[behavior] += 1
                    self.move_occurrences[behavior].append(move_index)
                    break  # One match per behavior per move

    def get_session_summary(self) -> Dict:
        """Get behavior summary for this session."""
        return {
            "counts": dict(self.counts),
            "total_moves": self.total_moves,
            "top_issues": self._get_top_issues(),
        }

    def _get_top_issues(self) -> List[str]:
        """Get top 2-3 issues from this session."""
        sorted_signals = sorted(
            self.counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [s for s, count in sorted_signals if count >= 2][:3]

    def get_concept_count_this_game(self, concept_key: str) -> int:
        """How many times has this concept triggered in the current game?"""
        # Map concept_key to behavior signal
        for behavior, signal_keys in SIGNAL_MAPPING.items():
            if concept_key in signal_keys or concept_key == behavior:
                return self.counts.get(behavior, 0)
        return 0


# ─── CROSS-GAME WEAKNESS COMPUTATION ──────────────────────────────

async def compute_top_weaknesses(db, user_id: str, recent_games: int = 10) -> List[Dict]:
    """
    Compute top 2-3 weaknesses.

    Uses EXISTING analyzed game data first (thinking_scores, problem_lifecycle,
    player_profiles). Only falls back to coach session behavior data if no
    analyzed games exist.

    Returns:
        [
            {"signal": "ignored_threat", "label": "Checking opponent threats",
             "count": 12, "games": 5, "severity": "high"},
            ...
        ]
    """
    result = []

    # ─── SOURCE 1: Analyzed game data (primary, already exists) ─────

    # thinking_scores: habit_scores per game (threat_awareness, king_safety, etc.)
    # Low scores = weakness
    thinking_docs = await db.thinking_scores.find(
        {"user_id": user_id},
        {"_id": 0, "habit_scores": 1}
    ).sort("calculated_at", -1).limit(recent_games).to_list(recent_games)

    if thinking_docs:
        # Map habit_scores to our 5 signals
        HABIT_TO_SIGNAL = {
            "threat_awareness": "ignored_threat",
            "tactical_vision": "hung_pieces",
            "king_safety": "king_safety",
            "move_verification": "premature_attack",
            "patience": "weak_development",
        }

        # Count games where each habit scored below 60 (weak)
        signal_weak_count = {s: 0 for s in TRACKED_SIGNALS}
        signal_total_score = {s: 0.0 for s in TRACKED_SIGNALS}

        for doc in thinking_docs:
            habits = doc.get("habit_scores", {})
            for habit_key, signal_key in HABIT_TO_SIGNAL.items():
                raw = habits.get(habit_key, 100)
                # Handle both formats: plain number OR dict with "score" key
                if isinstance(raw, dict):
                    score = raw.get("score", 100)
                elif isinstance(raw, (int, float)):
                    score = raw
                else:
                    score = 100
                signal_total_score[signal_key] += score
                if score < 60:
                    signal_weak_count[signal_key] += 1

        num_games = len(thinking_docs)

        # Also check problem_lifecycle for active patterns
        lifecycle_docs = await db.problem_lifecycle.find(
            {"user_id": user_id, "state": "active"},
            {"_id": 0, "category": 1, "count": 1, "anger": 1}
        ).to_list(10)

        LIFECYCLE_TO_SIGNAL = {
            "tactical_miss": "hung_pieces",
            "one_move_blunder": "ignored_threat",
            "threw_winning": "premature_attack",
            "opening_disaster": "weak_development",
        }

        for lc in lifecycle_docs:
            cat = lc.get("category", "")
            signal = LIFECYCLE_TO_SIGNAL.get(cat)
            if signal:
                signal_weak_count[signal] += lc.get("count", 1)

        # Also check player_profiles.top_weaknesses
        profile = await db.player_profiles.find_one(
            {"user_id": user_id},
            {"_id": 0, "top_weaknesses": 1}
        )
        if profile:
            for tw in profile.get("top_weaknesses", []):
                if isinstance(tw, dict):
                    tw_name = (tw.get("name") or tw.get("subcategory") or tw.get("category") or "").lower()
                else:
                    tw_name = str(tw).lower()
                if "threat" in tw_name or "tactic" in tw_name or "blunder" in tw_name:
                    signal_weak_count["ignored_threat"] += 2
                elif "piece" in tw_name or "hanging" in tw_name:
                    signal_weak_count["hung_pieces"] += 2
                elif "king" in tw_name:
                    signal_weak_count["king_safety"] += 2

        # Rank by weakness count
        ranked = sorted(
            [(s, signal_weak_count[s]) for s in TRACKED_SIGNALS if signal_weak_count[s] > 0],
            key=lambda x: x[1],
            reverse=True
        )

        for signal, count in ranked[:3]:
            avg_score = signal_total_score[signal] / num_games if num_games > 0 else 50
            sev = "high" if count >= 5 or avg_score < 40 else ("medium" if count >= 2 else "low")
            result.append({
                "signal": signal,
                "label": SIGNAL_LABELS.get(signal, signal),
                "count": count,
                "games": num_games,
                "severity": sev,
            })

        if result:
            return result

    # ─── SOURCE 2: Coach session behavior data (fallback) ─────

    sessions = await db.coach_sessions.find(
        {"user_id": user_id, "behavior_summary": {"$exists": True}},
        {"_id": 0, "behavior_summary": 1}
    ).sort("created_at", -1).limit(recent_games).to_list(recent_games)

    if not sessions:
        return []

    totals = {s: 0 for s in TRACKED_SIGNALS}
    game_counts = {s: 0 for s in TRACKED_SIGNALS}

    for session in sessions:
        summary = session.get("behavior_summary", {})
        counts = summary.get("counts", {})
        for signal in TRACKED_SIGNALS:
            c = counts.get(signal, 0)
            if c > 0:
                totals[signal] += c
                game_counts[signal] += 1

    ranked = sorted(
        [(s, totals[s], game_counts[s]) for s in TRACKED_SIGNALS if totals[s] > 0],
        key=lambda x: x[1],
        reverse=True
    )

    for signal, count, games in ranked[:3]:
        sev = "high" if count >= 8 else ("medium" if count >= 4 else "low")
        result.append({
            "signal": signal,
            "label": SIGNAL_LABELS.get(signal, signal),
            "count": count,
            "games": games,
            "severity": sev,
        })

    return result


async def get_focus_concept(db, user_id: str) -> Optional[Dict]:
    """
    Get the ONE focus concept for this session.
    This is the player's top weakness that we'll reinforce throughout.

    Returns:
        {"signal": "ignored_threat", "label": "Checking opponent threats",
         "count": 12, "severity": "high"} or None
    """
    weaknesses = await compute_top_weaknesses(db, user_id)
    return weaknesses[0] if weaknesses else None


# ─── SCORING BIAS ─────────────────────────────────────────────────

def get_weakness_score_boost(concept_key: str, top_weaknesses: List[Dict]) -> int:
    """
    Get scoring boost if this concept matches a known player weakness.

    Returns 0, 12, or 20 depending on match and severity.
    """
    if not top_weaknesses:
        return 0

    weakness_signals = {w["signal"]: w for w in top_weaknesses}

    # Direct match
    if concept_key in weakness_signals:
        sev = weakness_signals[concept_key].get("severity", "low")
        return 20 if sev == "high" else 12

    # Mapped match (e.g., "hung_piece" → "hung_pieces")
    for behavior, signal_keys in SIGNAL_MAPPING.items():
        if concept_key in signal_keys and behavior in weakness_signals:
            sev = weakness_signals[behavior].get("severity", "low")
            return 20 if sev == "high" else 12

    return 0


# ─── PATTERN ESCALATION ──────────────────────────────────────────

def get_escalation_level(
    concept_key: str,
    count_this_game: int,
    top_weaknesses: List[Dict],
) -> str:
    """
    Determine escalation level for a concept.

    Returns: "first", "repeated", "pattern"
    """
    is_known_weakness = any(
        concept_key == w["signal"] or
        concept_key in SIGNAL_MAPPING.get(w["signal"], [])
        for w in top_weaknesses
    )

    if count_this_game >= 3 or (count_this_game >= 2 and is_known_weakness):
        return "pattern"
    elif count_this_game >= 2 or is_known_weakness:
        return "repeated"
    return "first"


def get_escalated_message(concept_key: str, escalation: str, base_text: str) -> str:
    """
    Modify message tone based on escalation level.

    first    → base message (neutral)
    repeated → "still" / "again" language
    pattern  → "this keeps happening" language
    """
    if escalation == "first":
        return base_text

    if escalation == "repeated":
        REPEATED_PREFIXES = {
            "ignored_threat": "Again — you moved without checking what changed.",
            "hung_piece": "Again — you left a piece undefended.",
            "hung_pieces": "Again — you left a piece undefended.",
            "premature_attack": "You are still attacking before finishing your setup.",
            "king_safety": "Your king safety is still unresolved.",
            "weak_development": "You still have undeveloped pieces.",
        }
        return REPEATED_PREFIXES.get(concept_key, f"This is happening again. {base_text}")

    if escalation == "pattern":
        PATTERN_PREFIXES = {
            "ignored_threat": "This keeps happening — you are not checking threats before moving.",
            "hung_piece": "Same pattern — you keep leaving pieces unprotected.",
            "hung_pieces": "Same pattern — you keep leaving pieces unprotected.",
            "premature_attack": "Same habit — attack first, coordination later. This is costing you games.",
            "king_safety": "Your king keeps being the problem. This is a pattern.",
            "weak_development": "Development keeps being rushed. This is your main pattern right now.",
        }
        return PATTERN_PREFIXES.get(concept_key, f"This is a pattern now. {base_text}")

    return base_text


# ─── ADAPTIVE FRICTION ───────────────────────────────────────────

def get_adaptive_hold_boost(
    concept_key: str,
    count_this_game: int,
    top_weaknesses: List[Dict],
) -> int:
    """
    Extra hold time in ms for concepts matching player weaknesses.

    Returns 0, 1000, or 1500 ms boost.
    """
    escalation = get_escalation_level(concept_key, count_this_game, top_weaknesses)

    if escalation == "pattern":
        return 1500
    elif escalation == "repeated":
        return 1000
    return 0


# ─── SESSION START MESSAGES ───────────────────────────────────────

def get_session_focus_message(focus: Optional[Dict]) -> Optional[str]:
    """
    Generate the pre-game focus message.
    "Focus today: checking opponent threats"
    """
    if not focus:
        return None

    FOCUS_MESSAGES = {
        "ignored_threat": "Focus today: check what your opponent threatens before every move.",
        "hung_pieces": "Focus today: make sure every piece is defended before you move.",
        "premature_attack": "Focus today: finish your setup before starting an attack.",
        "king_safety": "Focus today: get your king safe early.",
        "weak_development": "Focus today: bring all your pieces into the game before doing anything else.",
    }

    return FOCUS_MESSAGES.get(focus["signal"],
        f"Focus today: {focus['label'].lower()}.")


# ─── SAVE BEHAVIOR TO SESSION ─────────────────────────────────────

async def save_session_behavior(db, session_id: str, tracker: 'SessionBehaviorTracker'):
    """Save behavior summary to the session document for cross-game analysis."""
    try:
        summary = tracker.get_session_summary()
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"behavior_summary": summary}}
        )
    except Exception as e:
        logger.warning(f"Failed to save behavior summary: {e}")
