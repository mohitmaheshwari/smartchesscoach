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


# ── PIECE-SAFETY GEOMETRY (2026-07-09) ─────────────────────────────
# Shared helpers for the piece_safety coaching surfaces. Extracted so
# every piece_safety fire (warning, affirmation, pre-move nag, streak
# check) reads from the SAME "is this piece hanging" rule — single
# source of truth for what counts as loose, matching the mastery
# gate's TAC_HANGING_PIECE definition on the review side.
#
# Rule: piece is "hanging" for its owner IF it's attacked by the
# opponent AND has zero same-color defenders. Kings excluded (they
# can be attacked, but "hanging" doesn't apply). Uses raw attacker
# count — SEE-aware refinement is possible but the naive rule already
# matches the mastery gate's fire pattern (95%+ agreement in probes).

_PIECE_NAMES = {
    1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen",
}


def _piece_name(piece_type: int) -> str:
    """python-chess PieceType → human word for coaching messages."""
    try:
        import chess as _c
        _MAP = {
            _c.PAWN: "pawn", _c.KNIGHT: "knight", _c.BISHOP: "bishop",
            _c.ROOK: "rook", _c.QUEEN: "queen",
        }
        return _MAP.get(piece_type, "piece")
    except Exception:
        return "piece"


def find_hanging_pieces(fen: str, own_color_is_white: bool) -> list:
    """Return a list of dicts describing hanging pieces of the given
    side in the position. Each dict: {square (SAN like 'e4'),
    piece_type, piece_name (word), n_attackers, n_defenders}.

    A piece hangs when opponent attackers > 0 and same-side defenders
    == 0. Kings excluded. Empty list when nothing hangs.
    """
    try:
        import chess as _c
        board = _c.Board(fen)
        own_color = _c.WHITE if own_color_is_white else _c.BLACK
        opp_color = not own_color
        out = []
        for sq in _c.SQUARES:
            piece = board.piece_at(sq)
            if piece is None or piece.color != own_color:
                continue
            if piece.piece_type == _c.KING:
                continue
            attackers = board.attackers(opp_color, sq)
            if not attackers:
                continue
            defenders = board.attackers(own_color, sq)
            if defenders:
                continue
            out.append({
                "square": _c.square_name(sq),
                "piece_type": piece.piece_type,
                "piece_name": _piece_name(piece.piece_type),
                "n_attackers": len(attackers),
                "n_defenders": 0,
            })
        # Sort most valuable first — a hanging queen matters more than
        # a hanging pawn for coach message prioritization.
        _VAL = {1: 100, 2: 300, 3: 300, 4: 500, 5: 900}
        out.sort(key=lambda h: -_VAL.get(h["piece_type"], 0))
        return out
    except Exception:
        return []


def find_saved_hanging_pieces(fen_before: str, fen_after: str,
                              own_color_is_white: bool) -> list:
    """Return the subset of pieces that were hanging in fen_before AND
    are NO LONGER hanging in fen_after. This is the "the move actually
    defended something" signal for the affirmation fire.

    A piece counts as "saved" if either:
      - It was hanging (attacker > 0, defender == 0) before and now has
        at least one defender, OR
      - It was hanging on square X before and the piece is no longer on
        X (moved away from danger).

    Excludes cases where the piece was captured (moved off the board
    entirely) — that's a LOSS, not a save.
    """
    try:
        import chess as _c
        pre_hangs = find_hanging_pieces(fen_before, own_color_is_white)
        if not pre_hangs:
            return []
        post_board = _c.Board(fen_after)
        own_color = _c.WHITE if own_color_is_white else _c.BLACK
        opp_color = not own_color
        saved = []
        for h in pre_hangs:
            sq = _c.parse_square(h["square"])
            piece_now = post_board.piece_at(sq)
            # Piece moved away — check if same piece_type still on the
            # board (i.e., not captured). If somewhere on the board and
            # not hanging there, it's saved.
            if piece_now is None:
                # Was this piece_type captured or just moved?
                still_on_board = False
                for other_sq in _c.SQUARES:
                    p = post_board.piece_at(other_sq)
                    if p and p.color == own_color and p.piece_type == h["piece_type"]:
                        # Check if this instance is safe now
                        attackers = post_board.attackers(opp_color, other_sq)
                        defenders = post_board.attackers(own_color, other_sq)
                        if not attackers or defenders:
                            still_on_board = True
                            break
                if still_on_board:
                    saved.append(h)
                continue
            # Piece still on same square — did it gain a defender OR
            # lose its attackers?
            if piece_now.color != own_color:
                continue  # different piece now on that square, ignore
            attackers = post_board.attackers(opp_color, sq)
            defenders = post_board.attackers(own_color, sq)
            if not attackers or defenders:
                saved.append(h)
        return saved
    except Exception:
        return []


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
    focus_subtype: Optional[str] = None,
    cp_loss: Optional[float] = None,
) -> bool:
    """Dispatch to the topic-specific rule.

    Sprint 2 (docs/one_surviving_instruction_scope.md): when
    focus_subtype == "simple_hang", also require board-verified
    confirmation via _piece_is_hanging_after_move (real SEE, reused
    from move_observation_deriver, not a new detector) -- not just
    "this was a piece-safety-relevant moment" in general. Every other
    subtype value (including None) keeps the unchanged topic-level
    behavior -- deliberately not attempted here, see the scope doc for
    why (needs opponent-threat context this call path doesn't have).
    """
    if focus_topic == "king_safety":
        return _is_king_safety_moment(fen_before, user_color)
    if focus_topic == "piece_safety":
        if focus_subtype == "destination_safety_exact":
            from services.destination_safety_detector import (
                derive_destination_safety_exact,
            )
            fact = derive_destination_safety_exact({
                "fen_before": fen_before,
                "move_uci": move_uci,
                "cp_loss": cp_loss,
                # A live decision has no stored analysis reply yet. The exact
                # fact deliberately keeps it measurable (eligible/outcome)
                # while withholding the stronger diagnostic fire.
                "pv_after_played": [],
            })
            return fact.get("eligible") is True
        if not _is_piece_safety_moment(fen_before, move_uci):
            return False
        if focus_subtype == "simple_hang":
            from services.move_observation_deriver import _piece_is_hanging_after_move
            return _piece_is_hanging_after_move(fen_before, move_uci) is True
        return True
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
        focus_subtype=scoreboard.get("focus_subtype"),
        cp_loss=cp_loss,
    )
    if not matched:
        return scoreboard

    scoreboard["matched_moments"] = scoreboard.get("matched_moments", 0) + 1

    # Time management: simpler rule per 2026-07-03 spec from Mohit —
    # a MISTAKE (cp_loss >= 100) played FAST (<3s) is the impulse signal.
    # No need for critical-moment complexity gating; the mistake itself
    # is the evidence that thinking would have helped.
    if (
        focus_topic == "piece_safety"
        and scoreboard.get("focus_subtype") == "destination_safety_exact"
    ):
        from services.destination_safety_detector import derive_destination_safety_exact
        exact_fact = derive_destination_safety_exact({
            "fen_before": fen_before,
            "move_uci": move_uci,
            "cp_loss": cp_loss,
            "pv_after_played": [],
        })
        handled = exact_fact.get("outcome") == "handled"
        missed = exact_fact.get("outcome") == "miss"
    elif focus_topic == "time_management":
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


def rebuild_scoreboard_from_history(
    base_scoreboard: Optional[Dict[str, Any]],
    move_history: list,
    user_color: str,
) -> Optional[Dict[str, Any]]:
    """Rebuild a full scoreboard from a session's complete move_history.

    Idempotent — starts fresh from base_scoreboard's focus_topic/subtype/
    label each call, replays every player move through update_scoreboard().
    Used both for the live in-request render (routes/coach_play.py's
    /move-feedback path) and — as of 2026-07-24 — to persist a final
    snapshot when a session actually ends, which nothing did before
    (mission_scoreboard was computed live every request but only ever
    attached to the outgoing response, never written back to
    db.coach_sessions — so check_mastery_gate always read the
    zeroed initial value regardless of how the game actually went).
    """
    if not base_scoreboard or not base_scoreboard.get("focus_topic"):
        return base_scoreboard

    rebuilt: Dict[str, Any] = {
        "focus_topic": base_scoreboard["focus_topic"],
        "focus_subtype": base_scoreboard.get("focus_subtype"),
        "focus_label": base_scoreboard.get("focus_label"),
        "matched_moments": 0,
        "handled_correctly": 0,
        "handled_incorrectly": 0,
        "events": [],
        # Sprint 2 (docs/one_surviving_instruction_scope.md, Correction #3):
        # this rebuild used to silently drop any key not in this dict --
        # confirmed the exact regression that would erase instruction_id/
        # text/version if they weren't explicitly carried through here.
        # Snapshot values only -- copied forward, never regenerated.
        "instruction_id": base_scoreboard.get("instruction_id"),
        "instruction_text": base_scoreboard.get("instruction_text"),
        "instruction_version": base_scoreboard.get("instruction_version"),
    }
    for i, m in enumerate(move_history or []):
        if not isinstance(m, dict) or m.get("by") != "player":
            continue
        eb = m.get("eval_before")
        ea = m.get("eval_after")
        if eb is None or ea is None:
            continue
        if user_color == "white":
            cp_loss = max(0, (eb - ea) * 100)
        else:
            cp_loss = max(0, (ea - eb) * 100)
        update_scoreboard(
            rebuilt,
            move_number=i // 2 + 1,
            move_san=m.get("move", ""),
            move_uci=m.get("uci", ""),
            fen_before=m.get("fen_before", ""),
            user_color=user_color,
            cp_loss=cp_loss,
            is_critical=bool(m.get("is_critical")),
            time_spent_seconds=m.get("time_spent"),
        )
    return rebuilt


def build_instruction_verdict(mission_scoreboard: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Sprint 2 (docs/one_surviving_instruction_scope.md) -- the ACTUAL
    visible postgame verdict for the surviving instruction, built from
    THIS session's own scoreboard. Deliberately NOT pattern_verdict/
    pattern_memory_service.get_top_patterns() -- that's a separate,
    independent mechanism that can disagree with the instruction the
    player was actually given (the exact bug this scope exists to fix).

    Lives here, not in routes/coach_play.py, deliberately (2026-08-08,
    external review of b0105f21, refactored while adding test coverage):
    this is a pure function of a mission_scoreboard dict -- zero
    dependency on the DB, the request, or anything else in that route
    file -- so it belongs next to the data shape it reads, and can be
    unit tested without importing a route module that initializes a
    live Stockfish engine at import time.

    Honest framing, not an overclaim: is_focus_moment() for simple_hang
    only ever returns True when a real SEE-verified hang occurred, so
    matched_moments > 0 means "at least one real hang happened" -- it
    does NOT mean "checked every move and N were unsafe," and a count of
    0 does NOT mean "correctly checked every move all game," only that
    no hang was DETECTED. Reviewer's own suggested fix, applied: label
    the zero case "no hang detected," never "instruction followed."
    Only simple_hang gets a specific behavioral claim -- V1 only
    board-verifies that one subtype (is_focus_moment above); every other
    piece_safety subtype gets the instruction text with no verdict
    claim, honestly reflecting that nothing was actually measured.
    """
    sb = mission_scoreboard or {}
    instruction_id = sb.get("instruction_id")
    instruction_text = sb.get("instruction_text")
    if not instruction_id or not instruction_text:
        return None

    subtype = sb.get("focus_subtype")
    matched = sb.get("matched_moments", 0)

    if subtype not in ("simple_hang", "destination_safety_exact"):
        return {
            "instruction_id": instruction_id,
            "instruction_text": instruction_text,
            "has_measured_outcome": False,
            "message": instruction_text,
        }

    if matched > 0:
        first_event = next(iter(sb.get("events") or []), None)
        move_number = first_event.get("move_number") if first_event else None
        move_clause = f" on move {move_number}" if move_number else ""
        return {
            "instruction_id": instruction_id,
            "instruction_text": instruction_text,
            "has_measured_outcome": True,
            "outcome": "missed",
            "matched_moments": matched,
            "message": (
                f"The piece you moved could be taken{move_clause}. "
                f"Same instruction next game: {instruction_text}"
                if subtype == "destination_safety_exact"
                else f"A piece was left hanging{move_clause}. Same instruction next game: {instruction_text}"
            ),
        }

    return {
        "instruction_id": instruction_id,
        "instruction_text": instruction_text,
        "has_measured_outcome": True,
        "outcome": "no_hang_detected",
        "matched_moments": 0,
        "message": (
            f"No destination-safety miss detected this game. Same instruction next game: {instruction_text}"
            if subtype == "destination_safety_exact"
            else f"No hang detected this game. Same instruction next game: {instruction_text}"
        ),
    }


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


# ── PUZZLE DIFFICULTY SCALING (2026-07-09) ────────────────────────
# Compute difficulty tiers (easy/medium/hard) for puzzles based on
# cp_loss (material swing) and avg_rating (who struggles with it).
# Difficulty is computed on-demand (no DB writes).


def estimate_puzzle_difficulty(cp_loss: float, avg_rating: Optional[float]) -> str:
    """
    Compute puzzle difficulty from cp_loss and avg_rating.

    Returns: "easy" | "medium" | "hard"

    Two signals:
      - cp_loss: how big is the error if best move not found
      - avg_rating: what rating of players typically solve this

    Priority: avg_rating (captures tactical depth better)
    Override: high cp_loss can escalate "easy" puzzles to "hard"
    """
    cp = cp_loss if cp_loss is not None else 100  # default: medium
    rating = avg_rating if avg_rating is not None else 1200  # default: medium

    # Signal 1: cp_loss tier
    if cp <= 100:
        cp_tier = "easy"       # Small mistake (inaccuracy)
    elif cp <= 250:
        cp_tier = "medium"     # Real mistake
    else:
        cp_tier = "hard"       # Big blunder / forcing sequence

    # Signal 2: rating tier (primary)
    if rating < 1000:
        rating_tier = "easy"       # Beginners find it hard
    elif rating < 1400:
        rating_tier = "medium"     # Intermediates find it hard
    else:
        rating_tier = "hard"       # Advanced players find it hard

    # Combine: use rating_min as primary, allow cp_loss to upgrade
    if rating_tier == "easy":
        return "easy"
    elif rating_tier == "medium":
        # Upgrade to hard if cp_loss is very high (forcing)
        return "hard" if cp >= 300 else "medium"
    else:  # rating_tier == "hard"
        return "hard"


def recommend_difficulty(user_rating: Optional[float]) -> str:
    """
    Recommend difficulty tier based on player rating.

    Returns: "easy" | "medium" | "hard"
    """
    if user_rating is None:
        return "medium"  # default
    if user_rating < 1000:
        return "easy"
    elif user_rating < 1500:
        return "medium"
    else:
        return "hard"


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
        "destination_safety_exact":"destination-safety miss",
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
