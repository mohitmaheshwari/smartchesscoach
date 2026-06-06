"""
opp_quiet_threat_detector.py — opp ignored a piece you were already winning.

Built 2026-06-07 (overnight, opp-failure V4 "quiet_when_threatened"). The
opponent had a piece you could already win (winnable: attacked + undefended
or by a cheaper attacker), and their move did NOT save it — so on your turn
you just take it. The bare caption was "Opponent's X is a mistake."; this
names the free piece.

Reuses played_hangs_detector._winnable_squares (the SEE-lite primitive,
already validated). Standalone + tested before any central-layer wiring.

STATUS: v0.1, NEEDS REVIEW (do not wire yet). Corpus test: 154 fires across
408 games (from 571 raw ignored-threat, gates cut pawn-noise + non-addressed).
Most fires are clean ("opp left a minor/major hanging, take it"). KNOWN
caveat: the "best_move addresses it" gate doesn't model check-response — a
best_move that gives check (e.g. Qxf2+) can pass the gate without literally
defending the piece, because _winnable ignores "must answer check first".
The user-facing CAPTION ("piece on X is hanging, take it") is still true in
those cases (the piece IS hanging), but the gate semantics should be
tightened (or dropped in favour of a pure board_after "is winnable" test)
before shipping. See MORNING_SUMMARY.md §5C.

detect_quiet_when_threatened(board_before, played_move, best_move_san, cp_loss)
  -> {"piece": "bishop", "square": "g3", "best_san": "Bxe5"} | None

GATES (tighten the 23% raw "ignored-threat" rate from the corpus probe):
  - ignored piece is a MINOR or major (>=320cp) — pawn cases are noisy/incidental
  - cp_loss >= 100 — the move was actually bad
  - best_move ADDRESSES the threat — after best_move the piece is no longer
    winnable (proves the defense existed; else the piece was simply doomed and
    "ignored" is the wrong framing)
"""
from typing import Optional, Dict
import chess
from services.played_hangs_detector import _winnable_squares, _winnable, _PIECE_VALUE, _PIECE_NAME

_MINOR_OR_MAJOR = 320  # knight value; excludes pawns


def detect_quiet_when_threatened(
    board_before: chess.Board,
    played_move: chess.Move,
    best_move_san: Optional[str],
    cp_loss: Optional[int],
) -> Optional[Dict]:
    if cp_loss is None or cp_loss < 100:
        return None
    mover = board_before.turn  # the opponent (whose move this is)

    before = _winnable_squares(board_before, mover)
    # only minor/major pieces — pawn "threats" are noisy
    before = {sq: pc for sq, pc in before.items()
              if _PIECE_VALUE[pc.piece_type] >= _MINOR_OR_MAJOR}
    if not before:
        return None

    board_after = board_before.copy()
    board_after.push(played_move)
    after = _winnable_squares(board_after, mover)

    # pieces that were winnable before AND survived (still winnable) after
    survived = [sq for sq in before if sq in after]
    if not survived:
        return None

    # best_move must address (save) at least one survived piece — proves the
    # defense was available, so "ignored a threat" is the right framing.
    if not best_move_san:
        return None
    try:
        bm = board_before.parse_san(best_move_san)
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        return None
    bb = board_before.copy()
    bb.push(bm)
    addressed = [sq for sq in survived if not _winnable(bb, sq, mover)]
    if not addressed:
        return None

    # report the most valuable addressed piece
    best_sq = max(addressed, key=lambda s: _PIECE_VALUE[before[s].piece_type])
    pc = before[best_sq]
    return {
        "piece": _PIECE_NAME.get(pc.piece_type, "piece"),
        "square": chess.square_name(best_sq),
        "best_san": best_move_san,
    }


def clause_for(v4: Dict, perspective_user: bool = True) -> str:
    """1200-friendly clause. perspective_user=True → addressed to the user
    (their opponent left a piece hanging, they can take it)."""
    return (f"it leaves the {v4['piece']} on {v4['square']} hanging — "
            f"you can just take it")
