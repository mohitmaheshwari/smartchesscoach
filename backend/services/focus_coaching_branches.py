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


# Register on module import so any caller of get_branch_for_focus sees it.
register_branch(PieceSafetyBranch())
