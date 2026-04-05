"""
Game Conversation Thread
========================

Tracks what the coach has said during THIS game session.
When the same behavior recurs, references the earlier coaching moment.

This is NOT cross-game memory (that's pattern_memory_service).
This is WITHIN a single game — "I told you this 5 moves ago."

Stored in memory (not DB) — lives for the duration of one game session.
On new game, the thread resets.

Usage:
    thread = GameConversationThread()
    thread.record("mistake", "piece_safety", 10, "Check what your opponent is attacking.")
    ...
    callback = thread.get_callback(14, "piece_safety")
    # Returns: "Move 10, I told you to check threats. You forgot again."
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class CoachingMoment:
    """A single coaching intervention during the game."""
    move_number: int
    behavior_type: str      # "piece_safety", "ignore_threat", "time_pressure", etc.
    severity: str           # "mistake", "blunder", "inaccuracy"
    rule_given: str         # The rule that was communicated
    message_summary: str    # Short version of what was said


@dataclass
class GameConversationThread:
    """Tracks coaching moments within a single game session."""
    moments: List[CoachingMoment] = field(default_factory=list)
    good_streaks: int = 0           # Consecutive good moves since last coaching
    last_coached_move: int = 0      # Move number of last coaching intervention

    def record(self, move_number: int, behavior_type: str, severity: str, rule_given: str, message_summary: str = ""):
        """Record a coaching moment."""
        self.moments.append(CoachingMoment(
            move_number=move_number,
            behavior_type=behavior_type,
            severity=severity,
            rule_given=rule_given,
            message_summary=message_summary,
        ))
        self.last_coached_move = move_number
        self.good_streaks = 0

    def record_good_move(self):
        """Track that user played well (no coaching needed)."""
        self.good_streaks += 1

    def get_callback(self, current_move: int, behavior_type: str) -> Optional[str]:
        """
        Check if the same behavior was coached earlier in this game.
        Returns a callback reference or None.

        Callback examples:
        - "I mentioned this on move 10. Same thing."
        - "Move 10, I told you to check threats. You did it for a while — then stopped."
        - "Third time this game. You know the rule."
        """
        # Find matching earlier moments
        matching = [m for m in self.moments if m.behavior_type == behavior_type]

        if not matching:
            return None

        last_match = matching[-1]
        count = len(matching)
        moves_ago = current_move - last_match.move_number

        # Don't callback if it just happened (within 2 moves)
        if moves_ago <= 2:
            return None

        # First callback: reference the specific move
        if count == 1:
            if self.good_streaks >= 3:
                # User was doing well after coaching, then relapsed
                return f"Move {last_match.move_number}, I said this. You listened for {self.good_streaks} moves — then stopped."
            else:
                return f"I mentioned this on move {last_match.move_number}. Same thing happening again."

        # Second callback: firmer
        if count == 2:
            first = matching[0]
            return f"Move {first.move_number} and move {last_match.move_number}. This is the third time this game."

        # Third+: very direct
        return f"That's {count + 1} times this game. You know the rule."

    def get_rule_reminder(self, behavior_type: str) -> Optional[str]:
        """Get the rule that was previously given for this behavior."""
        matching = [m for m in self.moments if m.behavior_type == behavior_type]
        if matching:
            return matching[-1].rule_given
        return None

    def get_session_summary(self) -> Dict:
        """Get a summary of coaching during this game."""
        behavior_counts = {}
        for m in self.moments:
            behavior_counts[m.behavior_type] = behavior_counts.get(m.behavior_type, 0) + 1

        return {
            "total_coaching_moments": len(self.moments),
            "behaviors_coached": behavior_counts,
            "most_coached": max(behavior_counts, key=behavior_counts.get) if behavior_counts else None,
            "most_coached_count": max(behavior_counts.values()) if behavior_counts else 0,
        }


# ── Session-level storage ──
# Key: session_id → GameConversationThread
# This lives in memory. When the server restarts, threads reset (which is fine —
# they're per-game, not persistent).
_active_threads: Dict[str, GameConversationThread] = {}


def get_thread(session_id: str) -> GameConversationThread:
    """Get or create a conversation thread for a session."""
    if session_id not in _active_threads:
        _active_threads[session_id] = GameConversationThread()
    return _active_threads[session_id]


def clear_thread(session_id: str):
    """Clear thread when game ends or new game starts."""
    _active_threads.pop(session_id, None)


def cleanup_old_threads(max_threads: int = 500):
    """Prevent memory leak — remove oldest threads if too many."""
    if len(_active_threads) > max_threads:
        # Remove oldest half
        keys = list(_active_threads.keys())
        for key in keys[:len(keys) // 2]:
            del _active_threads[key]
