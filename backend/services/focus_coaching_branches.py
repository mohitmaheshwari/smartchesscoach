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


# Register on module import so any caller of get_branch_for_focus sees it.
register_branch(PieceSafetyBranch())
register_branch(KingSafetyBranch())
