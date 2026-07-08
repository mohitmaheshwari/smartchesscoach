"""
Mission Scoreboard — per-game accounting of how the user handled moves
that match their active focus topic.

Wired into the Play with Coach move-handling loop. Called after each
user move with the FEN before, the played move, and the position
evaluation (cp_loss). Decides:

  1. Did this position match the user's focus? (topic-specific board rules)
  2. If so, did they handle it correctly? (cp_loss <= 50 counts as
     "handled")

Result is stored on `CoachGameSession.mission_scoreboard` and surfaced
via `/coach/play/session/{id}` for the frontend post-game screen.

Board-rules per focus topic reuse the same classifiers from
`services.cognitive_gap_subtypes` (king_safety, missed_tactic, etc.)
and `move_observation_deriver` (piece_safety). This is intentional
single-source-of-truth for what counts as a "focus-relevant moment."
"""
from typing import Any, Dict, Optional

import chess


HANDLED_CP_THRESHOLD = 50   # cp_loss <= 50 = handled correctly
MISS_CP_THRESHOLD = 150     # cp_loss >= 150 = definitively missed


def _is_king_safety_moment(fen_before: str, user_color: str) -> bool:
    """A moment is 'king_safety-relevant' if the user's king has ≥1 opp
    attacker on any square within 2 of it."""
    if not fen_before:
        return False
    try:
        b = chess.Board(fen_before)
    except Exception:
        return False
    user_col = chess.WHITE if user_color == "white" else chess.BLACK
    king_sq = b.king(user_col)
    if king_sq is None:
        return False
    opp_col = not user_col
    for sq in chess.SQUARES:
        if chess.square_distance(sq, king_sq) <= 2:
            if b.attackers(opp_col, sq):
                return True
    return False


def _is_piece_safety_moment(fen_before: str, move_uci: str) -> bool:
    """A moment is 'piece_safety-relevant' if the user is about to move
    a piece to a square where opponent attackers > defenders."""
    if not fen_before or not move_uci or len(move_uci) < 4:
        return False
    try:
        b = chess.Board(fen_before)
        mv = chess.Move.from_uci(move_uci)
        piece = b.piece_at(mv.from_square)
        if piece is None or piece.piece_type == chess.KING:
            return False
        b.push(mv)
        dest = mv.to_square
        opp_col = b.turn
        n_att = len(list(b.attackers(opp_col, dest)))
        n_def = len(list(b.attackers(not opp_col, dest)))
        return n_att > n_def
    except Exception:
        return False


def position_is_critical(fen: str) -> bool:
    """Return True if the position at `fen` is critical for the side to move.

    Extracted 2026-07-08 for the pre-move nag (Mohit's Phase 2 follow-up).
    Mirrors coach_play.live_behavior_extractor._is_critical_position — same
    rules (king in check OR ≥2 of the moving side's pieces attacked). Kept
    as a standalone module-level function so it can be called without
    instantiating LiveBehaviorExtractor from the coach_play route.
    """
    try:
        import chess as _c
        board = _c.Board(fen)
        if board.is_check():
            return True
        our_color = board.turn
        attacked = 0
        for sq in _c.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == our_color:
                if board.is_attacked_by(not our_color, sq):
                    attacked += 1
                    if attacked >= 2:
                        return True
        return False
    except Exception:
        return False


def _is_time_management_moment(is_critical: bool, time_spent_seconds: Optional[float]) -> bool:
    """A moment is 'time_management-relevant' if it's critical AND the user's
    time_spent is being tracked (regardless of whether they went fast)."""
    return bool(is_critical)


def is_focus_moment(
    focus_topic: str,
    fen_before: str,
    move_uci: str,
    user_color: str,
    is_critical: bool = False,
    time_spent_seconds: Optional[float] = None,
) -> bool:
    """Dispatch to the topic-specific rule."""
    if focus_topic == "king_safety":
        return _is_king_safety_moment(fen_before, user_color)
    if focus_topic == "piece_safety":
        return _is_piece_safety_moment(fen_before, move_uci)
    if focus_topic == "time_management":
        return _is_time_management_moment(is_critical, time_spent_seconds)
    if focus_topic in ("missed_tactic", "tactical_oversight", "calculation_depth"):
        # These are analyzer-tagged — approximate live via is_critical
        return bool(is_critical)
    if focus_topic in ("piece_activity", "opening_knowledge",
                       "endgame_technique", "pawn_structure"):
        # Positional topics that aren't easily live-verified — treat
        # any decently deep evaluation as an "opportunity to demonstrate"
        return bool(is_critical)
    return False


def update_scoreboard(
    scoreboard: Optional[Dict[str, Any]],
    *,
    move_number: int,
    move_san: str,
    move_uci: str,
    fen_before: str,
    user_color: str,
    cp_loss: float,
    is_critical: bool = False,
    time_spent_seconds: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Mutate + return the scoreboard for the given move.

    Returns the same dict (or None if no scoreboard was initialized).
    Safe to call every move — no-ops when the focus topic isn't set.
    """
    if not scoreboard or not scoreboard.get("focus_topic"):
        return scoreboard

    focus_topic = scoreboard["focus_topic"]
    matched = is_focus_moment(
        focus_topic, fen_before, move_uci, user_color,
        is_critical=is_critical, time_spent_seconds=time_spent_seconds,
    )
    if not matched:
        return scoreboard

    scoreboard["matched_moments"] = scoreboard.get("matched_moments", 0) + 1

    # Time management: simpler rule per 2026-07-03 spec from Mohit —
    # a MISTAKE (cp_loss >= 100) played FAST (<3s) is the impulse signal.
    # No need for critical-moment complexity gating; the mistake itself
    # is the evidence that thinking would have helped.
    if focus_topic == "time_management":
        handled = (time_spent_seconds is not None and time_spent_seconds >= 5)
        missed = (time_spent_seconds is not None and time_spent_seconds < 3
                  and cp_loss >= 100)
    else:
        handled = cp_loss <= HANDLED_CP_THRESHOLD
        missed = cp_loss >= MISS_CP_THRESHOLD

    if handled:
        scoreboard["handled_correctly"] = scoreboard.get("handled_correctly", 0) + 1
        outcome = "handled"
    elif missed:
        scoreboard["handled_incorrectly"] = scoreboard.get("handled_incorrectly", 0) + 1
        outcome = "missed"
    else:
        outcome = "partial"

    scoreboard.setdefault("events", []).append({
        "move_number": move_number,
        "move": move_san,
        "cp_loss": round(cp_loss, 1),
        "outcome": outcome,
        "time_spent": time_spent_seconds,
    })
    return scoreboard


async def compute_today_focus_count(db, user_id: str, focus_topic: str, dominant_subtype: Optional[str]) -> int:
    """Count how many focus-relevant events the user has already had TODAY
    across all their analyzed games. Used to inject 'this is your Nth
    critical moment today' into live coach feedback."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    day_start_iso = f"{now.date().isoformat()}T00:00:00+00:00"
    day_game_ids = await db.games.distinct("game_id", {
        "user_id": user_id, "is_analyzed": True,
        "date_played": {"$gte": day_start_iso},
    })
    if not day_game_ids:
        return 0
    # Handle time_management (uses time_flag) vs standard topics (missed_pattern + subtype)
    if focus_topic == "time_management" and dominant_subtype:
        q = {"user_id": user_id, "game_id": {"$in": day_game_ids},
             "time_flag": dominant_subtype}
    elif dominant_subtype:
        q = {"user_id": user_id, "game_id": {"$in": day_game_ids},
             "missed_pattern": focus_topic, "subtype": dominant_subtype}
    else:
        q = {"user_id": user_id, "game_id": {"$in": day_game_ids},
             "missed_pattern": focus_topic}
    return await db.move_observations.count_documents(q)


def build_recall_callout(
    scoreboard: Optional[Dict[str, Any]],
    today_count_before_move: int,
) -> Optional[str]:
    """Live in-game recall — the coach's move-by-move 'you're doing this
    RIGHT NOW' voice. Fires when the user just registered a new
    focus-relevant miss.

    Called AFTER update_scoreboard for a missed event.
    """
    if not scoreboard:
        return None
    # Only fire on 'missed' outcomes (last event added)
    events = scoreboard.get("events", [])
    if not events or events[-1].get("outcome") != "missed":
        return None
    session_missed = scoreboard.get("handled_incorrectly", 0)
    session_matched = scoreboard.get("matched_moments", 0)
    today_total = today_count_before_move + 1   # include this new one
    topic = scoreboard.get("focus_topic", "focus")
    subtype = scoreboard.get("focus_subtype", "")
    subject = _subject_for(subtype)
    if session_matched >= 2:
        return (f"That's the {_ord(session_missed)} miss this game — "
                f"and your {_ord(today_total)} {subject} today. "
                f"Slow down on the next critical moment.")
    return (f"That's your {_ord(today_total)} {subject} today. Watch the pattern.")


def _ord(n: int) -> str:
    if n <= 0:
        return "0th"
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _subject_for(subtype: str) -> str:
    return {
        "impulsive_critical":     "impulsive-critical moment",
        "time_pressure_blunder":  "time-pressure blunder",
        "slow_paralysis":         "slow-paralysis moment",
        "simple_hang":            "simple hang",
        "threat_ignored":         "ignored threat",
        "tactical_seq_loss":      "tactical-sequence loss",
        "quiet_blunder":          "quiet-position blunder",
        "ignored_king_attack":    "ignored king attack",
        "weakened_shelter":       "shelter weakening",
        "king_in_center":         "king-in-center moment",
        "missed_fork":            "missed fork",
        "missed_pin":             "missed pin",
        "missed_skewer":          "missed skewer",
        "missed_discovered_attack":"missed discovered attack",
        "ignored_forcing_threat": "ignored forcing threat",
        "queen_out_early":        "early-queen moment",
        "piece_parked_on_start":  "parked-piece moment",
        "isolated_pawn_created":  "isolated-pawn moment",
        "backward_pawn_created":  "backward-pawn moment",
        "passive_king_in_endgame":"passive-king endgame moment",
    }.get(subtype, "focus moment")


def build_postgame_summary(scoreboard: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Compute the display-ready summary shown on the post-game screen."""
    if not scoreboard or not scoreboard.get("focus_topic"):
        return None
    matched = scoreboard.get("matched_moments", 0)
    handled = scoreboard.get("handled_correctly", 0)
    missed = scoreboard.get("handled_incorrectly", 0)
    if matched == 0:
        headline = "No focus moments came up this game — different pattern next time."
        pct = None
    else:
        pct = round(100 * handled / matched)
        if pct >= 80:
            headline = f"Strong session — you handled {handled}/{matched} focus moments correctly."
        elif pct >= 50:
            headline = f"Middle of the road — {handled}/{matched} focus moments handled cleanly."
        else:
            headline = f"Work to do — only {handled}/{matched} focus moments handled cleanly."
    return {
        "focus_topic": scoreboard["focus_topic"],
        "focus_label": scoreboard.get("focus_label"),
        "matched": matched,
        "handled_correctly": handled,
        "handled_incorrectly": missed,
        "handled_pct": pct,
        "headline": headline,
        "events": scoreboard.get("events", []),
    }
