"""focus_coaching_branches.py — the shared architecture for per-focus
in-game coaching.

The piece_safety coaching in routes/coach_play.py (warning + affirm +
nag + streak) works so well because piece_safety has a clean positional
definition: "hanging piece = attackers > 0, defenders == 0" is a
boolean state you can compute on any FEN. That same 4-surface pattern
applies to ~6 of the other focus topics (king_safety, piece_activity,
endgame_technique, pawn_structure, missed_tactic, tactical_oversight)
— each has a "bad shape" that's detectable on-position and a
before/after "improvement" signal.

Rather than duplicating ~350 lines of route code per focus, this
module defines a `FocusCoachingBranch` base class that isolates the
FOCUS-SPECIFIC parts (detectors + copy templates) from the SHARED
plumbing (severity grading, today-count recall, once-per-session
restraint, conductor coordination, message insertion). A concrete
branch is ~60-100 lines instead of ~350.

Design (2026-07-09):
  - Each branch subclasses `FocusCoachingBranch` and implements the
    detector + template methods.
  - Route handlers call `fire_focus_warning / _affirm / _nag / _streak`
    with the current branch — plumbing lives here.
  - Adding a new focus = add a new branch class + register it.

First branch: PieceSafetyBranch (this file). Others follow in
subsequent commits.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ─── SEVERITY GRADING ──────────────────────────────────────────────
# Same grading language used by impulse_warning + piece_safety_warning
# so the coach voice reads consistent across surfaces.


def _grade_by_cp(cp_loss: float) -> str:
    """cp_loss → human severity word for coach messages."""
    if cp_loss >= 300:
        return "blunder"
    if cp_loss >= 150:
        return "big mistake"
    if cp_loss >= 100:
        return "mistake"
    return "inaccuracy"


def _ordinal(n: int) -> str:
    """1 → '1st', 2 → '2nd', 3 → '3rd', 4 → '4th', etc."""
    if n <= 0:
        return "0th"
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


# ─── BASE BRANCH CLASS ─────────────────────────────────────────────


class FocusCoachingBranch:
    """Base class for a focus-specific coaching branch. Subclass and
    override the detectors + copy templates for a specific focus.

    See PieceSafetyBranch below for a fully-worked example.
    """

    # ── Class-level configuration (subclasses override) ──
    focus_topic: str = ""            # e.g., "piece_safety"
    topic_display: str = ""          # e.g., "piece safety" (human words)
    subtype_for_recall: str = ""     # e.g., "hung_piece" — used by
                                     # compute_today_focus_count query

    # Conductor coordination — skip the warning fire if any of these
    # thread keys are in session.conductor_threads_pulled (means the
    # motif/concept layer already spoke about this event).
    conductor_thread_keys: Set[str] = set()

    # Coach-message `type` string per surface. Blank = default derivation
    # of f"{focus_topic}_{surface}". Legacy branches with an established
    # frontend-facing type name (e.g., PieceSafety's affirm is stored as
    # `piece_safe_affirm` not `piece_safety_affirm`) override these.
    warning_type_name: str = ""
    affirm_type_name: str = ""
    nag_type_name: str = ""
    streak_type_name: str = ""

    def _type_for(self, surface: str, override: str) -> str:
        return override or f"{self.focus_topic}_{surface}"

    # Fire gates (subclasses override if needed)
    warning_cp_min: int = 50         # inclusive lower bound
    affirm_cp_max: int = 50          # exclusive upper bound
    streak_min_moves: int = 10       # after this many user moves

    # ── Detector methods (subclasses MUST override) ──

    def find_issues(self, fen: str, user_color: str) -> List[Dict[str, Any]]:
        """Return list of issue dicts describing the focus-specific bad
        shape(s) in the position for the user. Empty list when clean.
        Ordering: most-severe first (top will be named in the message).
        """
        raise NotImplementedError

    def find_improvements(
        self, fen_before: str, fen_after: str, user_color: str,
    ) -> List[Dict[str, Any]]:
        """Return list of issues that were RESOLVED by the user's move
        (present in fen_before, not present in fen_after). Empty when
        the move didn't fix anything. Used for the affirmation fire.
        """
        raise NotImplementedError

    # ── Copy templates (subclasses MUST override) ──

    def warning_text(
        self, top_issue: Dict[str, Any], n_more: int,
        move_san: str, cp_loss: int, grade: str, today_recall: str,
    ) -> str:
        """Return the warning coach_message text. Include the named
        issue, severity grade, and (optional) today-count recall.
        Should end with the goal anchor.
        """
        raise NotImplementedError

    def affirm_text(
        self, top_saved: Dict[str, Any], n_more: int, move_san: str,
    ) -> str:
        """Return the affirmation coach_message text. Name the resolved
        issue. End with the goal anchor.
        """
        raise NotImplementedError

    def nag_text(self, top_issue: Dict[str, Any], n_more: int) -> str:
        """Return the pre-move nag text. Name the issue. Anchor to goal."""
        raise NotImplementedError

    def streak_text(self, clean_moves: int) -> str:
        """Return the mid-game streak-acknowledgment text. Anchor to goal."""
        raise NotImplementedError


# ─── FIRING HELPERS — the shared plumbing ──────────────────────────


async def _get_today_count(db, session_doc: Dict, branch: FocusCoachingBranch) -> int:
    """Reuses services.mission_scoreboard.compute_today_focus_count via
    the branch's subtype. Returns 0 on any failure — a missing recall
    line is silence, not a crash."""
    try:
        from services.mission_scoreboard import compute_today_focus_count
        return await compute_today_focus_count(
            db, session_doc.get("user_id"),
            branch.focus_topic, branch.subtype_for_recall,
        )
    except Exception:
        return 0


async def fire_focus_warning(
    db, session_doc: Dict, branch: FocusCoachingBranch,
    move_san: str, cp_loss: int, fen_after: str, user_color: str,
    session_id: str,
) -> bool:
    """Fire the warning coach_message if the user's move created a
    focus-specific issue. Returns True if fired.

    Gates (in order):
      1. cp_loss >= branch.warning_cp_min
      2. fen_after present
      3. No conductor thread already covered this event
      4. Branch's detector finds at least one issue
      5. Not already fired this session (once per session per branch)
    """
    if cp_loss < branch.warning_cp_min or not fen_after:
        return False

    pulled = session_doc.get("conductor_threads_pulled") or []
    if any(k in branch.conductor_thread_keys for k in pulled):
        return False

    issues = branch.find_issues(fen_after, user_color)
    if not issues:
        return False

    already = await db.coach_messages.count_documents({
        "session_id": session_id, "type": branch._type_for("warning", branch.warning_type_name),
    })
    if already > 0:
        return False

    grade = _grade_by_cp(cp_loss)
    today_count = await _get_today_count(db, session_doc, branch)
    today_recall = (
        f" That's your {_ordinal(today_count + 1)} {branch.topic_display} slip today."
        if today_count >= 3 else ""
    )
    top = issues[0]
    n_more = len(issues) - 1
    text = branch.warning_text(top, n_more, move_san, cp_loss, grade, today_recall)

    await db.coach_messages.insert_one({
        "session_id": session_id,
        "type": branch._type_for("warning", branch.warning_type_name),
        "move_san": move_san,
        "message": text,
        "cp_loss": cp_loss,
        "issues": issues,
        "today_count": today_count,
        "created_at": datetime.now(timezone.utc),
        "read": False,
    })
    logger.info(f"[{branch.focus_topic}_warning] fired for {session_id} move={move_san} cp={cp_loss}")
    return True


async def fire_focus_affirm(
    db, session_doc: Dict, branch: FocusCoachingBranch,
    move_san: str, cp_loss: int, fen_before: str, fen_after: str,
    user_color: str, session_id: str,
) -> bool:
    """Fire the affirmation coach_message if the user's move actually
    resolved a focus-specific issue. Returns True if fired.

    Gates:
      1. cp_loss < branch.affirm_cp_max
      2. fen_before + fen_after present
      3. Not already fired this session
      4. Branch's find_improvements returns non-empty
    """
    if cp_loss >= branch.affirm_cp_max or not fen_before or not fen_after:
        return False

    already = await db.coach_messages.count_documents({
        "session_id": session_id, "type": branch._type_for("affirm", branch.affirm_type_name),
    })
    if already > 0:
        return False

    saved = branch.find_improvements(fen_before, fen_after, user_color)
    if not saved:
        return False

    top = saved[0]
    n_more = len(saved) - 1
    text = branch.affirm_text(top, n_more, move_san)

    await db.coach_messages.insert_one({
        "session_id": session_id,
        "type": branch._type_for("affirm", branch.affirm_type_name),
        "move_san": move_san,
        "message": text,
        "cp_loss": cp_loss,
        "improvements": saved,
        "created_at": datetime.now(timezone.utc),
        "read": False,
    })
    logger.info(f"[{branch.focus_topic}_affirm] fired for {session_id} move={move_san}")
    return True


async def fire_focus_nag(
    db, session_doc: Dict, branch: FocusCoachingBranch,
    fen_after: str, user_color: str, coach_move_san: str,
    session_id: str,
) -> bool:
    """Fire the pre-move nag if the position handed back to the user has
    focus-specific issues. Returns True if fired.

    Gates:
      1. Branch's detector finds at least one issue in fen_after
      2. Not already fired this session
      3. Skip if a warning of the same branch fired earlier this session
         (the user was JUST warned — don't nag them again)
    """
    issues = branch.find_issues(fen_after, user_color)
    if not issues:
        return False

    already = await db.coach_messages.count_documents({
        "session_id": session_id, "type": branch._type_for("nag", branch.nag_type_name),
    })
    if already > 0:
        return False

    # Suppress-if-warning: user was recently warned about the same shape.
    warn_recent = await db.coach_messages.count_documents({
        "session_id": session_id, "type": branch._type_for("warning", branch.warning_type_name),
    })
    if warn_recent > 0:
        return False

    top = issues[0]
    n_more = len(issues) - 1
    text = branch.nag_text(top, n_more)

    await db.coach_messages.insert_one({
        "session_id": session_id,
        "type": branch._type_for("nag", branch.nag_type_name),
        "message": text,
        "focus_topic": branch.focus_topic,
        "fen": fen_after,
        "after_coach_move": coach_move_san,
        "issues": issues,
        "created_at": datetime.now(timezone.utc),
        "read": False,
    })
    logger.info(f"[{branch.focus_topic}_nag] fired for {session_id} after coach {coach_move_san}")
    return True


async def fire_focus_streak(
    db, session_doc: Dict, branch: FocusCoachingBranch,
    fen_after: str, user_color: str, session_id: str,
) -> bool:
    """Fire the mid-game streak acknowledgment if user has played
    enough moves cleanly. Returns True if fired.

    Gates:
      1. User has played >= branch.streak_min_moves moves
      2. No warning fired this session (had a slip, so no streak)
      3. Current position has zero issues
      4. Not already fired this session
    """
    user_moves = [
        m for m in (session_doc.get("move_history") or [])
        if m.get("by") == "player"
    ]
    if len(user_moves) < branch.streak_min_moves:
        return False

    already = await db.coach_messages.count_documents({
        "session_id": session_id, "type": branch._type_for("streak", branch.streak_type_name),
    })
    if already > 0:
        return False

    prior_warn = await db.coach_messages.count_documents({
        "session_id": session_id, "type": branch._type_for("warning", branch.warning_type_name),
    })
    if prior_warn > 0:
        return False

    issues = branch.find_issues(fen_after, user_color)
    if issues:
        return False

    clean_moves = len(user_moves) + 1
    text = branch.streak_text(clean_moves)

    await db.coach_messages.insert_one({
        "session_id": session_id,
        "type": branch._type_for("streak", branch.streak_type_name),
        "message": text,
        "clean_moves": clean_moves,
        "created_at": datetime.now(timezone.utc),
        "read": False,
    })
    logger.info(f"[{branch.focus_topic}_streak] fired for {session_id} clean={clean_moves}")
    return True


# ─── REGISTRY ──────────────────────────────────────────────────────


_REGISTRY: Dict[str, FocusCoachingBranch] = {}


def register_branch(branch: FocusCoachingBranch) -> None:
    """Register a branch instance under its focus_topic key."""
    _REGISTRY[branch.focus_topic] = branch


def get_branch_for_focus(focus_topic: Optional[str]) -> Optional[FocusCoachingBranch]:
    """Return the branch for a focus topic, or None if unregistered.
    Returns None on falsy input so callers can `if branch: ...`."""
    if not focus_topic:
        return None
    return _REGISTRY.get(focus_topic)


# ─── PIECE_SAFETY BRANCH — the first concrete implementation ───────


class PieceSafetyBranch(FocusCoachingBranch):
    """The piece_safety focus: named hanging pieces, before/after save
    detection, coordination with the conductor's TAC_HANGING_PIECE +
    loose motif threads. All detectors delegate to shared helpers in
    services.mission_scoreboard so the mastery gate + focus coaching +
    review captions all agree on what counts as loose.
    """

    focus_topic = "piece_safety"
    topic_display = "piece safety"
    subtype_for_recall = "hung_piece"

    conductor_thread_keys = {
        "concept:TAC_HANGING_PIECE",
        "defense:loose",
        "offense:loose",
    }

    # Legacy: shipped piece_safety affirm uses "piece_safe_affirm" not
    # "piece_safety_affirm" — override so the frontend + downstream code
    # keep matching without a rename migration.
    affirm_type_name = "piece_safe_affirm"

    def find_issues(self, fen: str, user_color: str) -> List[Dict[str, Any]]:
        from services.mission_scoreboard import find_hanging_pieces
        return find_hanging_pieces(fen, user_color == "white")

    def find_improvements(
        self, fen_before: str, fen_after: str, user_color: str,
    ) -> List[Dict[str, Any]]:
        from services.mission_scoreboard import find_saved_hanging_pieces
        return find_saved_hanging_pieces(fen_before, fen_after, user_color == "white")

    def warning_text(
        self, top_issue: Dict[str, Any], n_more: int,
        move_san: str, cp_loss: int, grade: str, today_recall: str,
    ) -> str:
        piece_word = top_issue.get("piece_name", "piece")
        sq = top_issue.get("square", "?")
        also = (
            f" (and {n_more} more piece{'s' if n_more > 1 else ''} unguarded)"
            if n_more > 0 else ""
        )
        return (
            f"{move_san} left your {piece_word} on {sq} undefended — "
            f"a {grade} ({cp_loss}cp lost).{also}{today_recall} "
            f"That's your piece safety focus this week."
        )

    def affirm_text(
        self, top_saved: Dict[str, Any], n_more: int, move_san: str,
    ) -> str:
        piece_word = top_saved.get("piece_name", "piece")
        sq = top_saved.get("square", "?")
        also = f" (and {n_more} more)" if n_more > 0 else ""
        return (
            f"Nice — {move_san} saved your {piece_word} "
            f"from {sq}{also}. That's exactly the shape we're "
            f"working on. That's your piece safety focus this week."
        )

    def nag_text(self, top_issue: Dict[str, Any], n_more: int) -> str:
        piece_word = top_issue.get("piece_name", "piece")
        sq = top_issue.get("square", "?")
        also = f" (and {n_more} more)" if n_more > 0 else ""
        return (
            f"⚠ Your {piece_word} on {sq} is hanging"
            f"{also} — defend before you move. "
            f"That's your piece safety focus this week."
        )

    def streak_text(self, clean_moves: int) -> str:
        return (
            f"You've kept your pieces safe through {clean_moves} moves so far — "
            f"good discipline. Keep scanning before every move. "
            f"That's your piece safety focus this week."
        )


# ─── KING_SAFETY BRANCH ────────────────────────────────────────────
# The second concrete branch. Same 4-surface pattern as piece_safety
# but with king-specific detectors: in-check, attack-density near the
# king, and open files at a castled king. Conservative on false
# positives — a 1200 player already has too much going on to be nagged
# on a routine king walk.

# Which of the conductor's motif keys mean "the king was the target"?
# Skip the warning fire when any is pulled — the motif layer already spoke.
_KING_MOTIF_KEYS = {
    "defense:pin",       # walked into a pin against the king
    "defense:skewer",    # walked into a skewer through the king
    "defense:discovered",# walked into a discovered check
    "concept:MID_KING_SAFETY",
    "concept:DEF_WALK_KING",
    "concept:OP_NOT_CASTLED",
    "concept:OP_LOOSE_KING_PAWNS",
}


_PIECE_NAMES = {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen", 6: "king"}


def _piece_name(piece_type: int) -> str:
    return _PIECE_NAMES.get(piece_type, "piece")


def _king_zone_squares(king_sq: int) -> list:
    """Return squares within 2 of the king (king's own square + 3x3
    neighborhood + a diamond around it). Used for attack-density scan."""
    try:
        import chess as _c
        kf, kr = _c.square_file(king_sq), _c.square_rank(king_sq)
        out = []
        for f in range(max(0, kf - 2), min(7, kf + 2) + 1):
            for r in range(max(0, kr - 2), min(7, kr + 2) + 1):
                out.append(_c.square(f, r))
        return out
    except Exception:
        return []


def _find_king_safety_issues(fen: str, user_color: str) -> list:
    """Return list of king_safety issue dicts for the user in `fen`.
    Kinds:
      - "in_check": user's king is in check (turn matters)
      - "king_zone_swarm": 3+ distinct opponent pieces attack squares
        within 2 of the king
      - "open_file_at_castled_king": king on g1/g8/c1/c8 with no own
        pawn on its file AND opponent rook or queen on the same file
    """
    try:
        import chess as _c
        board = _c.Board(fen)
        own_color = _c.WHITE if user_color == "white" else _c.BLACK
        opp_color = not own_color
        king_sq = board.king(own_color)
        if king_sq is None:
            return []
        king_sq_name = _c.square_name(king_sq)
        issues = []

        # Issue 1: in check when it's the user's turn to move
        if board.turn == own_color and board.is_check():
            for checker_sq in board.checkers():
                checker = board.piece_at(checker_sq)
                if checker is None:
                    continue
                issues.append({
                    "kind": "in_check",
                    "attacker_square": _c.square_name(checker_sq),
                    "attacker_piece": _piece_name(checker.piece_type),
                    "king_square": king_sq_name,
                })

        # Issue 2: king-zone attack density
        zone = _king_zone_squares(king_sq)
        attackers_in_zone = set()
        for sq in zone:
            for asq in board.attackers(opp_color, sq):
                attackers_in_zone.add(asq)
        if len(attackers_in_zone) >= 3:
            issues.append({
                "kind": "king_zone_swarm",
                "attacker_count": len(attackers_in_zone),
                "king_square": king_sq_name,
            })

        # Issue 3: open file at castled king
        # Post-castle king squares: g1/c1 (white) or g8/c8 (black).
        king_file = _c.square_file(king_sq)
        king_rank = _c.square_rank(king_sq)
        is_post_castle = (
            (own_color == _c.WHITE and king_rank == 0 and king_file in (2, 6))
            or (own_color == _c.BLACK and king_rank == 7 and king_file in (2, 6))
        )
        if is_post_castle:
            own_pawn_on_king_file = False
            for r in range(8):
                p = board.piece_at(_c.square(king_file, r))
                if p and p.color == own_color and p.piece_type == _c.PAWN:
                    own_pawn_on_king_file = True
                    break
            if not own_pawn_on_king_file:
                # Opponent rook or queen on same file?
                for r in range(8):
                    p = board.piece_at(_c.square(king_file, r))
                    if p and p.color == opp_color and p.piece_type in (_c.ROOK, _c.QUEEN):
                        issues.append({
                            "kind": "open_file_at_castled_king",
                            "file": chr(ord("a") + king_file),
                            "attacker_piece": _piece_name(p.piece_type),
                            "attacker_square": _c.square_name(_c.square(king_file, r)),
                            "king_square": king_sq_name,
                        })
                        break

        # Sort by severity: in_check > swarm > open_file
        _RANK = {"in_check": 0, "king_zone_swarm": 1, "open_file_at_castled_king": 2}
        issues.sort(key=lambda i: _RANK.get(i.get("kind"), 99))
        return issues
    except Exception:
        return []


def _find_king_safety_improvements(fen_before: str, fen_after: str,
                                   user_color: str) -> list:
    """Return the king_safety issues that were RESOLVED by the user's
    move. Kind-based intersection — any issue kind present in the
    before-set but absent in the after-set counts as a save.
    """
    before = _find_king_safety_issues(fen_before, user_color)
    after = _find_king_safety_issues(fen_after, user_color)
    kinds_after = {i["kind"] for i in after}
    return [i for i in before if i["kind"] not in kinds_after]


def _issue_phrase(issue: dict) -> str:
    """One-liner describing the issue for insertion into templates."""
    kind = issue.get("kind")
    if kind == "in_check":
        return f"in check from the {issue.get('attacker_piece', 'piece')} on {issue.get('attacker_square', '?')}"
    if kind == "king_zone_swarm":
        n = issue.get("attacker_count", 0)
        return f"under {n} attackers near your king on {issue.get('king_square', '?')}"
    if kind == "open_file_at_castled_king":
        f = issue.get("file", "?")
        return f"the {f}-file open at your king with a {issue.get('attacker_piece', 'piece')} bearing down"
    return "under fire"


def _resolution_phrase(issue: dict) -> str:
    """What did the user's move achieve (past tense) for the affirmation."""
    kind = issue.get("kind")
    if kind == "in_check":
        return "got out of check"
    if kind == "king_zone_swarm":
        return "cleared the pressure near your king"
    if kind == "open_file_at_castled_king":
        f = issue.get("file", "?")
        return f"closed the {f}-file at your king"
    return "defended the king"


class KingSafetyBranch(FocusCoachingBranch):
    """The king_safety focus. 3 detectable issue kinds: in_check,
    king_zone_swarm, open_file_at_castled_king. Coordinates with the
    conductor's king-related concept and defensive-motif threads so
    the warning doesn't double-fire on the same event.
    """

    focus_topic = "king_safety"
    topic_display = "king safety"
    subtype_for_recall = "ignored_king_attack"

    conductor_thread_keys = _KING_MOTIF_KEYS

    def find_issues(self, fen, user_color):
        return _find_king_safety_issues(fen, user_color)

    def find_improvements(self, fen_before, fen_after, user_color):
        return _find_king_safety_improvements(fen_before, fen_after, user_color)

    def warning_text(self, top_issue, n_more, move_san, cp_loss, grade, today_recall):
        phrase = _issue_phrase(top_issue)
        also = (
            f" (and {n_more} more king-safety problem{'s' if n_more > 1 else ''})"
            if n_more > 0 else ""
        )
        return (
            f"{move_san} left your king {phrase} — "
            f"a {grade} ({cp_loss}cp lost).{also}{today_recall} "
            f"That's your king safety focus this week."
        )

    def affirm_text(self, top_saved, n_more, move_san):
        resolution = _resolution_phrase(top_saved)
        also = f" (and cleaned up {n_more} more)" if n_more > 0 else ""
        return (
            f"Nice — {move_san} {resolution}{also}. That's exactly "
            f"the discipline we're working on. That's your king safety "
            f"focus this week."
        )

    def nag_text(self, top_issue, n_more):
        phrase = _issue_phrase(top_issue)
        also = f" (and {n_more} more)" if n_more > 0 else ""
        return (
            f"⚠ Your king is {phrase}{also} — defend before you push. "
            f"That's your king safety focus this week."
        )

    def streak_text(self, clean_moves):
        return (
            f"Your king's been safe through {clean_moves} moves so far — "
            f"good discipline. Keep watching for pressure on the king. "
            f"That's your king safety focus this week."
        )


# ─── PIECE_ACTIVITY BRANCH ─────────────────────────────────────────
# Detects passive/undeveloped pieces. Fires WARNING when a user's
# move leaves them with 2+ minor pieces still asleep after move 10,
# or moves a knight to the rim, or leaves a bishop with almost no
# squares.

_STARTING_MINOR_SQUARES_WHITE = {1: "b1", 2: "c1", 5: "f1", 6: "g1"}  # b1, g1 = knights; c1, f1 = bishops
_STARTING_MINOR_SQUARES_BLACK = {57: "b8", 58: "c8", 61: "f8", 62: "g8"}


def _undeveloped_minors(board, own_color) -> list:
    """Return list of {piece, square} for minor pieces still on their
    starting squares."""
    import chess as _c
    starts = _STARTING_MINOR_SQUARES_WHITE if own_color == _c.WHITE else _STARTING_MINOR_SQUARES_BLACK
    out = []
    for sq, name in starts.items():
        p = board.piece_at(sq)
        if p and p.color == own_color and p.piece_type in (_c.KNIGHT, _c.BISHOP):
            out.append({"piece": _piece_name(p.piece_type), "square": name})
    return out


def _knights_on_rim(board, own_color) -> list:
    """Return list of {piece, square} for knights on a- or h-file."""
    import chess as _c
    out = []
    for sq in board.pieces(_c.KNIGHT, own_color):
        f = _c.square_file(sq)
        if f == 0 or f == 7:
            out.append({"piece": "knight", "square": _c.square_name(sq)})
    return out


def _cramped_bishops(board, own_color) -> list:
    """Return list of {piece, square, mobility} for bishops with ≤2
    legal moves in the current position (mobility check via attacks)."""
    import chess as _c
    out = []
    for sq in board.pieces(_c.BISHOP, own_color):
        # Count non-blocked squares the bishop actually reaches.
        moves = 0
        for target in board.attacks(sq):
            t = board.piece_at(target)
            if t is None or t.color != own_color:
                moves += 1
        if moves <= 2:
            out.append({"piece": "bishop", "square": _c.square_name(sq), "mobility": moves})
    return out


def _find_piece_activity_issues(fen: str, user_color: str) -> list:
    """Return piece_activity issue dicts. Kinds:
      - "undeveloped_minors": ≥2 minor pieces on starting squares past
        move 10 (fullmove_number ≥ 10)
      - "knight_on_rim": knight on a- or h-file
      - "cramped_bishop": bishop with ≤2 legal moves
    """
    try:
        import chess as _c
        board = _c.Board(fen)
        own_color = _c.WHITE if user_color == "white" else _c.BLACK
        issues = []

        undeveloped = _undeveloped_minors(board, own_color)
        if len(undeveloped) >= 2 and board.fullmove_number >= 10:
            issues.append({
                "kind": "undeveloped_minors",
                "count": len(undeveloped),
                "pieces": undeveloped,
            })

        rim = _knights_on_rim(board, own_color)
        if rim:
            issues.append({
                "kind": "knight_on_rim",
                "count": len(rim),
                "pieces": rim,
                "square": rim[0]["square"],
            })

        cramped = _cramped_bishops(board, own_color)
        if cramped:
            issues.append({
                "kind": "cramped_bishop",
                "count": len(cramped),
                "square": cramped[0]["square"],
                "mobility": cramped[0]["mobility"],
            })

        # Sort by rank: undeveloped is worst pedagogically, then rim, then cramped
        _RANK = {"undeveloped_minors": 0, "knight_on_rim": 1, "cramped_bishop": 2}
        issues.sort(key=lambda i: _RANK.get(i.get("kind"), 99))
        return issues
    except Exception:
        return []


def _find_piece_activity_improvements(fen_before: str, fen_after: str,
                                      user_color: str) -> list:
    """Kind-based intersection: kinds present before but absent after
    are counted as saves. Also: if undeveloped count strictly decreased
    (a piece was developed), that's a save regardless of kind presence."""
    before = _find_piece_activity_issues(fen_before, user_color)
    after = _find_piece_activity_issues(fen_after, user_color)
    kinds_after = {i["kind"] for i in after}
    saved = [i for i in before if i["kind"] not in kinds_after]

    # Special: undeveloped count went from N to N-1 → still an issue in
    # after but user did develop a piece. Give credit.
    try:
        import chess as _c
        b_before = _c.Board(fen_before)
        b_after = _c.Board(fen_after)
        own_color = _c.WHITE if user_color == "white" else _c.BLACK
        u_before = len(_undeveloped_minors(b_before, own_color))
        u_after = len(_undeveloped_minors(b_after, own_color))
        if u_before > u_after and u_before >= 2:
            already_saved_undev = any(s["kind"] == "undeveloped_minors" for s in saved)
            if not already_saved_undev:
                saved.append({
                    "kind": "piece_developed",
                    "count_before": u_before,
                    "count_after": u_after,
                })
    except Exception:
        pass
    return saved


def _activity_issue_phrase(issue: dict) -> str:
    kind = issue.get("kind")
    if kind == "undeveloped_minors":
        return f"still {issue.get('count', 0)} minor pieces on their starting squares"
    if kind == "knight_on_rim":
        return f"a knight on the rim ({issue.get('square', '?')}) — passive"
    if kind == "cramped_bishop":
        return f"a bishop on {issue.get('square', '?')} with almost no squares"
    return "passive pieces"


def _activity_resolution_phrase(issue: dict) -> str:
    kind = issue.get("kind")
    if kind == "undeveloped_minors":
        return "developed the sleeping pieces"
    if kind == "knight_on_rim":
        return "activated the knight"
    if kind == "cramped_bishop":
        return "freed the bishop"
    if kind == "piece_developed":
        return "developed a sleeping piece"
    return "activated the pieces"


class PieceActivityBranch(FocusCoachingBranch):
    focus_topic = "piece_activity"
    topic_display = "piece activity"
    subtype_for_recall = "passive_piece"
    conductor_thread_keys = {"concept:OP_DEVELOP", "concept:MID_ACTIVITY"}

    def find_issues(self, fen, user_color):
        return _find_piece_activity_issues(fen, user_color)

    def find_improvements(self, fen_before, fen_after, user_color):
        return _find_piece_activity_improvements(fen_before, fen_after, user_color)

    def warning_text(self, top_issue, n_more, move_san, cp_loss, grade, today_recall):
        phrase = _activity_issue_phrase(top_issue)
        also = f" (and {n_more} more activity problems)" if n_more > 0 else ""
        return (
            f"{move_san} left you with {phrase} — a {grade} ({cp_loss}cp lost)."
            f"{also}{today_recall} That's your piece activity focus this week."
        )

    def affirm_text(self, top_saved, n_more, move_san):
        resolution = _activity_resolution_phrase(top_saved)
        also = f" (and cleaned up {n_more} more)" if n_more > 0 else ""
        return (
            f"Nice — {move_san} {resolution}{also}. Active pieces do the work. "
            f"That's your piece activity focus this week."
        )

    def nag_text(self, top_issue, n_more):
        phrase = _activity_issue_phrase(top_issue)
        also = f" (and {n_more} more)" if n_more > 0 else ""
        return (
            f"⚠ You have {phrase}{also} — activate before attacking. "
            f"That's your piece activity focus this week."
        )

    def streak_text(self, clean_moves):
        return (
            f"Your pieces have been busy through {clean_moves} moves — good "
            f"coordination. Keep every piece contributing. That's your piece "
            f"activity focus this week."
        )


# ─── ENDGAME_TECHNIQUE BRANCH ──────────────────────────────────────
# Simplest signals: king on back rank when board is simplified;
# passed pawn present but not being pushed. The "endgame" threshold
# is total non-king material ≤ 20 (roughly: down to 2 minors + a rook
# each side or less).

def _non_king_material(board) -> int:
    """Total centipawn-equivalent material excluding kings, both colors."""
    import chess as _c
    total = 0
    for pt, val in ((_c.PAWN, 1), (_c.KNIGHT, 3), (_c.BISHOP, 3),
                    (_c.ROOK, 5), (_c.QUEEN, 9)):
        total += len(board.pieces(pt, _c.WHITE)) * val
        total += len(board.pieces(pt, _c.BLACK)) * val
    return total


def _has_passed_pawn(board, own_color) -> list:
    """Return list of {square, rank} for user's passed pawns (no opposing
    pawns on same file or adjacent files AHEAD of the pawn)."""
    import chess as _c
    passed = []
    own_pawns = board.pieces(_c.PAWN, own_color)
    opp_pawns = list(board.pieces(_c.PAWN, not own_color))
    for sq in own_pawns:
        f = _c.square_file(sq)
        r = _c.square_rank(sq)
        # Direction of advance
        direction = 1 if own_color == _c.WHITE else -1
        blocked = False
        for opp_sq in opp_pawns:
            of = _c.square_file(opp_sq)
            or_ = _c.square_rank(opp_sq)
            if abs(of - f) > 1:
                continue
            if (direction == 1 and or_ > r) or (direction == -1 and or_ < r):
                blocked = True
                break
        if not blocked:
            passed.append({"square": _c.square_name(sq), "rank": r})
    return passed


def _find_endgame_technique_issues(fen: str, user_color: str) -> list:
    """Kinds:
      - "king_on_back_rank": in simplified position, own king still on
        rank 0 (white) or 7 (black)
      - "passed_pawn_available": user has a passed pawn (recognize the
        winning weapon — this fires with EVERY endgame position; used
        for streak/nag messaging only, NOT the main warning)
    Only fires when non-king material ≤ 20.
    """
    try:
        import chess as _c
        board = _c.Board(fen)
        own_color = _c.WHITE if user_color == "white" else _c.BLACK
        if _non_king_material(board) > 20:
            return []
        issues = []
        king_sq = board.king(own_color)
        if king_sq is not None:
            r = _c.square_rank(king_sq)
            back_rank = 0 if own_color == _c.WHITE else 7
            if r == back_rank:
                issues.append({
                    "kind": "king_on_back_rank",
                    "king_square": _c.square_name(king_sq),
                })
        return issues
    except Exception:
        return []


def _find_endgame_technique_improvements(fen_before: str, fen_after: str,
                                        user_color: str) -> list:
    try:
        import chess as _c
        b_before = _c.Board(fen_before)
        b_after = _c.Board(fen_after)
        own_color = _c.WHITE if user_color == "white" else _c.BLACK
        saved = []
        # King moved off the back rank in a simplified position?
        if _non_king_material(b_before) <= 20 and _non_king_material(b_after) <= 20:
            k_before = b_before.king(own_color)
            k_after = b_after.king(own_color)
            back_rank = 0 if own_color == _c.WHITE else 7
            if k_before is not None and k_after is not None:
                if _c.square_rank(k_before) == back_rank and _c.square_rank(k_after) != back_rank:
                    saved.append({
                        "kind": "king_activated",
                        "from_square": _c.square_name(k_before),
                        "to_square": _c.square_name(k_after),
                    })
        # Pushed a passed pawn?
        passed_before = _has_passed_pawn(b_before, own_color)
        passed_after = _has_passed_pawn(b_after, own_color)
        for p_after in passed_after:
            # Same file, higher rank than any before? = pushed
            matching_before = [
                p for p in passed_before
                if p["square"][0] == p_after["square"][0]
            ]
            if matching_before and p_after["rank"] > max(p["rank"] for p in matching_before):
                saved.append({
                    "kind": "passed_pawn_pushed",
                    "square": p_after["square"],
                    "rank": p_after["rank"],
                })
                break
        return saved
    except Exception:
        return []


def _endgame_issue_phrase(issue: dict) -> str:
    kind = issue.get("kind")
    if kind == "king_on_back_rank":
        return f"your king on {issue.get('king_square', 'the back rank')} — endgames are king endgames"
    return "an endgame technique issue"


def _endgame_resolution_phrase(issue: dict) -> str:
    kind = issue.get("kind")
    if kind == "king_activated":
        return f"activated your king (to {issue.get('to_square', '?')})"
    if kind == "passed_pawn_pushed":
        return f"pushed your passed pawn to {issue.get('square', '?')}"
    return "improved your endgame play"


class EndgameTechniqueBranch(FocusCoachingBranch):
    focus_topic = "endgame_technique"
    topic_display = "endgame technique"
    subtype_for_recall = "poor_endgame"
    conductor_thread_keys = {"concept:END_ACTIVE_KING", "concept:END_PASSED_PAWN"}

    def find_issues(self, fen, user_color):
        return _find_endgame_technique_issues(fen, user_color)

    def find_improvements(self, fen_before, fen_after, user_color):
        return _find_endgame_technique_improvements(fen_before, fen_after, user_color)

    def warning_text(self, top_issue, n_more, move_san, cp_loss, grade, today_recall):
        phrase = _endgame_issue_phrase(top_issue)
        return (
            f"{move_san} kept {phrase} — a {grade} ({cp_loss}cp lost).{today_recall} "
            f"That's your endgame technique focus this week."
        )

    def affirm_text(self, top_saved, n_more, move_san):
        resolution = _endgame_resolution_phrase(top_saved)
        return (
            f"Nice — {move_san} {resolution}. That's the endgame mindset. "
            f"That's your endgame technique focus this week."
        )

    def nag_text(self, top_issue, n_more):
        phrase = _endgame_issue_phrase(top_issue)
        return (
            f"⚠ In this endgame, {phrase}. Activate the king before you push. "
            f"That's your endgame technique focus this week."
        )

    def streak_text(self, clean_moves):
        return (
            f"You've handled {clean_moves} endgame moves cleanly — good technique. "
            f"Keep the king active and pawns coordinated. That's your endgame "
            f"technique focus this week."
        )


# ─── PAWN_STRUCTURE BRANCH ─────────────────────────────────────────
# Delegates to PawnStructureClassifier from pawn_structure_service.
# Kinds:
#   - "doubled_pawns_appeared" — user has doubled pawns
#   - "isolated_pawns_appeared" — user has isolated pawns
#   - "backward_pawn_appeared" — user has backward pawn(s)

def _analyze_pawns(fen: str, user_color: str) -> dict:
    """Return dict with 'doubled', 'isolated', 'backward', 'passed' as
    lists of square-names for user's pieces of that color."""
    from services.pawn_structure_service import PawnStructureClassifier
    import chess as _c
    board = _c.Board(fen)
    classifier = PawnStructureClassifier()
    result = classifier.analyze(board)
    color_key = user_color  # "white" or "black" matches result feature tuples
    out = {"doubled": [], "isolated": [], "backward": [], "passed": []}
    for f in result.features:
        if f.color != color_key:
            continue
        if f.type == "doubled":
            out["doubled"].append(f.square)
        elif f.type == "isolated":
            out["isolated"].append(f.square)
        elif f.type == "backward":
            out["backward"].append(f.square)
        elif f.type == "passed":
            out["passed"].append(f.square)
    return out


def _find_pawn_structure_issues(fen: str, user_color: str) -> list:
    try:
        analysis = _analyze_pawns(fen, user_color)
        issues = []
        if analysis["doubled"]:
            issues.append({
                "kind": "doubled_pawns",
                "count": len(analysis["doubled"]),
                "squares": analysis["doubled"],
                "file": analysis["doubled"][0][0],  # letter
            })
        if analysis["isolated"]:
            issues.append({
                "kind": "isolated_pawns",
                "count": len(analysis["isolated"]),
                "squares": analysis["isolated"],
                "square": analysis["isolated"][0],
            })
        if analysis["backward"]:
            issues.append({
                "kind": "backward_pawns",
                "count": len(analysis["backward"]),
                "squares": analysis["backward"],
                "square": analysis["backward"][0],
            })
        _RANK = {"doubled_pawns": 0, "isolated_pawns": 1, "backward_pawns": 2}
        issues.sort(key=lambda i: _RANK.get(i.get("kind"), 99))
        return issues
    except Exception:
        return []


def _find_pawn_structure_improvements(fen_before: str, fen_after: str,
                                     user_color: str) -> list:
    try:
        before = _find_pawn_structure_issues(fen_before, user_color)
        after = _find_pawn_structure_issues(fen_after, user_color)
        kinds_after = {i["kind"] for i in after}
        saved = []
        for i in before:
            if i["kind"] not in kinds_after:
                saved.append(i)
            else:
                # Count strictly went down?
                match_after = next((a for a in after if a["kind"] == i["kind"]), None)
                if match_after and i.get("count", 0) > match_after.get("count", 0):
                    saved.append(i)
        return saved
    except Exception:
        return []


def _structure_issue_phrase(issue: dict) -> str:
    kind = issue.get("kind")
    if kind == "doubled_pawns":
        return f"doubled pawns on the {issue.get('file', '?')}-file — a long-term weakness"
    if kind == "isolated_pawns":
        return f"an isolated pawn on {issue.get('square', '?')} — no pawn neighbors to defend it"
    if kind == "backward_pawns":
        return f"a backward pawn on {issue.get('square', '?')} — the square in front is weak"
    return "a pawn-structure problem"


def _structure_resolution_phrase(issue: dict) -> str:
    kind = issue.get("kind")
    if kind == "doubled_pawns":
        return f"fixed the doubled pawns on the {issue.get('file', '?')}-file"
    if kind == "isolated_pawns":
        return "resolved an isolated pawn"
    if kind == "backward_pawns":
        return "resolved a backward pawn"
    return "improved the pawn structure"


class PawnStructureBranch(FocusCoachingBranch):
    focus_topic = "pawn_structure"
    topic_display = "pawn structure"
    subtype_for_recall = "weak_pawns"
    conductor_thread_keys = {"concept:MID_PAWN_STRUCTURE", "concept:OP_LOOSE_PAWNS"}
    # Structure damage isn't a snap decision — allow higher cp threshold
    warning_cp_min: int = 40

    def find_issues(self, fen, user_color):
        return _find_pawn_structure_issues(fen, user_color)

    def find_improvements(self, fen_before, fen_after, user_color):
        return _find_pawn_structure_improvements(fen_before, fen_after, user_color)

    def warning_text(self, top_issue, n_more, move_san, cp_loss, grade, today_recall):
        phrase = _structure_issue_phrase(top_issue)
        also = f" (and {n_more} more structure problems)" if n_more > 0 else ""
        return (
            f"{move_san} created {phrase} — a {grade} ({cp_loss}cp lost).{also}"
            f"{today_recall} That's your pawn structure focus this week."
        )

    def affirm_text(self, top_saved, n_more, move_san):
        resolution = _structure_resolution_phrase(top_saved)
        also = f" (and cleaned up {n_more} more)" if n_more > 0 else ""
        return (
            f"Nice — {move_san} {resolution}{also}. Structure decides long games. "
            f"That's your pawn structure focus this week."
        )

    def nag_text(self, top_issue, n_more):
        phrase = _structure_issue_phrase(top_issue)
        return (
            f"⚠ You have {phrase} — think about pawn moves carefully. "
            f"That's your pawn structure focus this week."
        )

    def streak_text(self, clean_moves):
        return (
            f"Your pawn structure has held up through {clean_moves} moves — "
            f"good discipline. Keep watching pawn breaks. That's your pawn "
            f"structure focus this week."
        )


# ─── MISSED_TACTIC BRANCH ──────────────────────────────────────────
# Detects opponent tactics AVAILABLE in the current position. If
# opponent can play a fork/pin/skewer/discovered attack, the user
# "missed" the threat.

def _opp_has_immediate_fork(board, opp_color) -> Optional[dict]:
    """Iterate opponent's knight/queen legal moves and return the first
    one that creates a fork (reuses pv_tactical_analyzer)."""
    import chess as _c
    try:
        from services.pv_tactical_analyzer import _immediate_fork
    except Exception:
        return None
    # Need to make it opp's turn to enumerate their moves. If it isn't,
    # push a null-move-like approach isn't safe with chess — instead
    # temporarily swap turn field.
    if board.turn != opp_color:
        b = board.copy(stack=False)
        b.turn = opp_color
        # Clear en-passant target that references our-color turn
        b.ep_square = None
    else:
        b = board
    # Only check knight/queen moves for MVP fork detection
    for move in b.legal_moves:
        p = b.piece_at(move.from_square)
        if p is None or p.piece_type not in (_c.KNIGHT, _c.QUEEN):
            continue
        result = _immediate_fork(b, move)
        if result is not None:
            return {
                "move_uci": move.uci(),
                "from_square": _c.square_name(move.from_square),
                "to_square": _c.square_name(move.to_square),
                "piece": _piece_name(p.piece_type),
                "targets": result.get("targets", []),
            }
    return None


def _find_missed_tactic_issues(fen: str, user_color: str) -> list:
    """Returns list of tactic-issue dicts. Kind: "opp_has_fork"."""
    try:
        import chess as _c
        board = _c.Board(fen)
        own_color = _c.WHITE if user_color == "white" else _c.BLACK
        opp_color = not own_color
        issues = []
        fork = _opp_has_immediate_fork(board, opp_color)
        if fork:
            issues.append({
                "kind": "opp_has_fork",
                **fork,
            })
        return issues
    except Exception:
        return []


def _find_missed_tactic_improvements(fen_before: str, fen_after: str,
                                    user_color: str) -> list:
    """If opp had a fork before AND doesn't after → user defended it."""
    before = _find_missed_tactic_issues(fen_before, user_color)
    after = _find_missed_tactic_issues(fen_after, user_color)
    kinds_after = {i["kind"] for i in after}
    return [i for i in before if i["kind"] not in kinds_after]


def _tactic_issue_phrase(issue: dict) -> str:
    kind = issue.get("kind")
    if kind == "opp_has_fork":
        piece = issue.get("piece", "piece")
        to_sq = issue.get("to_square", "?")
        n_targets = len(issue.get("targets", []))
        return f"the opponent can now fork with {piece} to {to_sq} (hitting {n_targets} pieces)"
    return "a tactic against you"


def _tactic_resolution_phrase(issue: dict) -> str:
    kind = issue.get("kind")
    if kind == "opp_has_fork":
        return "defused the fork threat"
    return "defended the tactic"


class MissedTacticBranch(FocusCoachingBranch):
    focus_topic = "missed_tactic"
    topic_display = "tactics"
    subtype_for_recall = "missed_threat"
    conductor_thread_keys = {
        "defense:fork", "defense:pin", "defense:skewer",
        "defense:discovered", "concept:TAC_FORK", "concept:TAC_PIN",
    }

    def find_issues(self, fen, user_color):
        return _find_missed_tactic_issues(fen, user_color)

    def find_improvements(self, fen_before, fen_after, user_color):
        return _find_missed_tactic_improvements(fen_before, fen_after, user_color)

    def warning_text(self, top_issue, n_more, move_san, cp_loss, grade, today_recall):
        phrase = _tactic_issue_phrase(top_issue)
        return (
            f"{move_san} missed a tactic — {phrase}. A {grade} ({cp_loss}cp lost)."
            f"{today_recall} That's your tactics focus this week."
        )

    def affirm_text(self, top_saved, n_more, move_san):
        resolution = _tactic_resolution_phrase(top_saved)
        return (
            f"Nice — {move_san} {resolution}. Seeing the threat is half the "
            f"work. That's your tactics focus this week."
        )

    def nag_text(self, top_issue, n_more):
        phrase = _tactic_issue_phrase(top_issue)
        return (
            f"⚠ Watch out — {phrase}. Defend before you push. "
            f"That's your tactics focus this week."
        )

    def streak_text(self, clean_moves):
        return (
            f"You've navigated {clean_moves} moves without missing a tactic — "
            f"good vigilance. Keep looking for two-move threats. That's your "
            f"tactics focus this week."
        )


# ─── TACTICAL_OVERSIGHT BRANCH ─────────────────────────────────────
# The 2-move miss: user played a move that seemed safe but opponent
# has a winning material capture. Uses SEE (from tactical_safety) to
# ensure the capture is genuinely winning.

_TACTICAL_PIECE_VALUES = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 0}


def _opp_has_winning_capture(board, opp_color) -> Optional[dict]:
    """Iterate opponent captures; return the first that gains ≥3 net
    material via SEE. Excludes losing sacrifices and pawn-for-pawn
    trades."""
    import chess as _c
    try:
        from services.tactical_safety import capture_is_safe
    except Exception:
        capture_is_safe = None
    if board.turn != opp_color:
        b = board.copy(stack=False)
        b.turn = opp_color
        b.ep_square = None
    else:
        b = board
    best = None
    for move in b.legal_moves:
        if not b.is_capture(move):
            continue
        target = b.piece_at(move.to_square)
        if target is None:
            continue
        attacker = b.piece_at(move.from_square)
        if attacker is None:
            continue
        target_val = _TACTICAL_PIECE_VALUES.get(target.piece_type, 0)
        attacker_val = _TACTICAL_PIECE_VALUES.get(attacker.piece_type, 0)
        if target_val < 3:
            continue  # ignore pawn captures for MVP
        # Cheap SEE-lite: if defender count zero AND target > attacker,
        # obviously winning. If defended, use capture_is_safe if avail.
        defenders = b.attackers(not opp_color, move.to_square)
        if not defenders and target_val > 0:
            gain = target_val
            if best is None or gain > best.get("gain", 0):
                best = {
                    "move_uci": move.uci(),
                    "from_square": _c.square_name(move.from_square),
                    "to_square": _c.square_name(move.to_square),
                    "attacker": _piece_name(attacker.piece_type),
                    "target": _piece_name(target.piece_type),
                    "gain": gain,
                }
            continue
        if defenders and capture_is_safe is not None:
            # Rough check: is opponent's capture SEE-positive?
            try:
                if capture_is_safe(b, move.to_square, opp_color):
                    gain = target_val - attacker_val
                    if gain >= 3 and (best is None or gain > best.get("gain", 0)):
                        best = {
                            "move_uci": move.uci(),
                            "from_square": _c.square_name(move.from_square),
                            "to_square": _c.square_name(move.to_square),
                            "attacker": _piece_name(attacker.piece_type),
                            "target": _piece_name(target.piece_type),
                            "gain": gain,
                        }
            except Exception:
                pass
    return best


def _find_tactical_oversight_issues(fen: str, user_color: str) -> list:
    try:
        import chess as _c
        board = _c.Board(fen)
        own_color = _c.WHITE if user_color == "white" else _c.BLACK
        opp_color = not own_color
        cap = _opp_has_winning_capture(board, opp_color)
        if cap:
            return [{"kind": "opp_wins_material", **cap}]
        return []
    except Exception:
        return []


def _find_tactical_oversight_improvements(fen_before: str, fen_after: str,
                                         user_color: str) -> list:
    before = _find_tactical_oversight_issues(fen_before, user_color)
    after = _find_tactical_oversight_issues(fen_after, user_color)
    kinds_after = {i["kind"] for i in after}
    return [i for i in before if i["kind"] not in kinds_after]


def _oversight_issue_phrase(issue: dict) -> str:
    kind = issue.get("kind")
    if kind == "opp_wins_material":
        atk = issue.get("attacker", "piece")
        tgt = issue.get("target", "piece")
        to_sq = issue.get("to_square", "?")
        gain = issue.get("gain", 0)
        return f"the opponent can play {atk}x{to_sq} winning the {tgt} for +{gain}"
    return "a material loss"


def _oversight_resolution_phrase(issue: dict) -> str:
    return "prevented the material loss"


class TacticalOversightBranch(FocusCoachingBranch):
    focus_topic = "tactical_oversight"
    topic_display = "tactical oversight"
    subtype_for_recall = "missed_second_move"
    conductor_thread_keys = {"defense:loose", "concept:TAC_HANGING_PIECE"}
    # Oversight often flows from cp_loss ≥ 100; be a touch stricter.
    warning_cp_min: int = 60

    def find_issues(self, fen, user_color):
        return _find_tactical_oversight_issues(fen, user_color)

    def find_improvements(self, fen_before, fen_after, user_color):
        return _find_tactical_oversight_improvements(fen_before, fen_after, user_color)

    def warning_text(self, top_issue, n_more, move_san, cp_loss, grade, today_recall):
        phrase = _oversight_issue_phrase(top_issue)
        return (
            f"{move_san} let it slip — {phrase}. A {grade} ({cp_loss}cp lost)."
            f"{today_recall} That's your tactical oversight focus this week."
        )

    def affirm_text(self, top_saved, n_more, move_san):
        resolution = _oversight_resolution_phrase(top_saved)
        return (
            f"Nice — {move_san} {resolution}. Slowing down works. "
            f"That's your tactical oversight focus this week."
        )

    def nag_text(self, top_issue, n_more):
        phrase = _oversight_issue_phrase(top_issue)
        return (
            f"⚠ Two-move check — {phrase}. Take another look before moving. "
            f"That's your tactical oversight focus this week."
        )

    def streak_text(self, clean_moves):
        return (
            f"You've slowed down and stayed sharp through {clean_moves} moves — "
            f"good discipline. Keep asking 'what do they do next?' That's your "
            f"tactical oversight focus this week."
        )


# Register on module import so any caller of get_branch_for_focus sees it.
register_branch(PieceSafetyBranch())
register_branch(KingSafetyBranch())
register_branch(PieceActivityBranch())
register_branch(EndgameTechniqueBranch())
register_branch(PawnStructureBranch())
register_branch(MissedTacticBranch())
register_branch(TacticalOversightBranch())
