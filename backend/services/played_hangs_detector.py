"""
played_hangs_detector.py — detect when a USER move leaves a piece hanging.

Built 2026-06-06 (overnight). Standalone + fully tested against real flagged
FENs BEFORE wiring into the central caption_facts layer (which has high blast
radius — every caption routes through it). The morning summary carries the
one-spot wiring diff for review.

Failure mode (from bare-caption forensics, ~16 flagged positions): the user
plays a move that leaves one of their own pieces attacked and winnable by the
opponent — either the moved piece itself, or another piece whose defender just
left / whose attacker line just opened.

`detect_played_hangs(board_before, played_move)` returns:
    {"square": "e5", "piece": "knight", "moved_piece": False} | None

Gating (conservative — these are the dials that control misfire):
  - The hung piece must be WINNABLE for the opponent (SEE-lite: attacked, and
    either undefended OR the cheapest attacker is worth less than the piece).
  - The hang must be NEWLY created by this move (not already hanging before) —
    so we don't blame a move for a pre-existing problem.
  - King excluded (that's check/mate logic, not hanging).
"""
from typing import Optional, Dict
import chess

_PIECE_VALUE = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 100000,
}
_PIECE_NAME = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen",
}


# Stockfish stores a forced mate as 10000 - 10*mate_in, so a loss at or above
# this is a mate swing rather than material. The bare 9000 appears in five
# other services; this names it here rather than adding a sixth.
MATE_SCORE_CP = 9000


def _winnable(board: chess.Board, sq: int, color: bool,
              require_legal_capture: bool = False) -> bool:
    """Is the `color` piece on `sq` winnable by the opponent? SEE-lite:
    attacked, and (undefended OR cheapest attacker cheaper than the piece).

    `require_legal_capture` closes the hole that `board.attackers()` is
    PSEUDO-legal: it lists pieces whose move pattern reaches the square, not
    pieces that may actually take. A pinned attacker counts, and so does one
    belonging to a side that is in check and must answer the check first.

    Measured 2026-09-18 on 120 production fires: 13 were provably false
    (11%), and 9 of those 13 were exactly this -- an attacker that cannot
    legally capture. At a 95% promotion bar that alone disqualifies the
    detector, so the review session would have failed after the fact.

    Only safe to pass when the OPPONENT is the side to move, which is true of
    the after-position and not of the before-position. The before-snapshot
    stays pseudo-legal on purpose: over-counting what was already hanging can
    only suppress a fire, never invent one.
    """
    piece = board.piece_at(sq)
    if not piece or piece.color != color or piece.piece_type == chess.KING:
        return False
    attackers = board.attackers(not color, sq)
    if not attackers:
        return False
    if require_legal_capture:
        if not any(move.to_square == sq and board.is_capture(move)
                   for move in board.legal_moves):
            return False
        # And the capture has to actually WIN something. The heuristic below
        # ("cheapest attacker is cheaper than the piece") ignores how many
        # defenders stand behind it, so a rook attacked by three pieces and
        # defended by one read as hanging when the whole exchange comes out
        # level. Measured on 200 production fires: the full exchange keeps
        # 193 and drops 7 (4%), and those 7 are the provably-false ones.
        # Caption grade has no recall floor and a 95% precision floor, so 4%
        # fewer fires for 4% more precision is the right side of that trade.
        from services.legal_exchange_verifier import independent_exchange_gain

        if independent_exchange_gain(board, sq) <= 0:
            return False
    defenders = board.attackers(color, sq)
    if not defenders:
        return True
    piece_val = _PIECE_VALUE[piece.piece_type]
    cheapest_attacker = min(
        _PIECE_VALUE[board.piece_at(a).piece_type] for a in attackers
    )
    # A lower-value attacker means even after recapture the opponent profits.
    return cheapest_attacker < piece_val


def _winnable_squares(board: chess.Board, color: bool,
                      require_legal_capture: bool = False) -> Dict[int, chess.Piece]:
    out = {}
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if (p and p.color == color and p.piece_type != chess.KING
                and _winnable(board, sq, color, require_legal_capture)):
            out[sq] = p
    return out


def detect_played_hangs(
    board_before: chess.Board,
    played_move: chess.Move,
    cp_loss: Optional[int] = None,
    mate_in_play: bool = False,
) -> Optional[Dict]:
    """Return the most valuable piece newly left hanging by `played_move`, or None.

    GATES (validated 2026-06-06 against 105 flagged FENs — without these the
    raw detector misfires on recapture pawns, 16 fires/3 low-cpl misfires;
    with them, 6 fires / 0 low-cpl misfires):
      - cp_loss >= 100 : the move must actually be bad (kills even-recapture
        pawns like exd4 cpl=2 that aren't real hangs).
      - hung-piece value >= 0.5 * min(cp_loss, 900) : the hung piece must
        plausibly EXPLAIN the loss (kills "names a minor a3 pawn on a 698-cp
        blunder" — O-O-O case).
    Pass cp_loss to apply the gates; omit it to get raw detection (testing).

    KNOWN LIMITATION (review before shipping): on positions where the loss is
    actually a discovered attack / zwischenzug (e.g. Be4 -> Qf4+), this reports
    "leaves your bishop hanging — no defender", which is simplistic, not the
    precise mechanism. ~2 of 6 gated fires. Consider suppressing when a
    discovered-attack is present (origin-ray-walk) before promoting to primary.
    """
    mover = board_before.turn
    board_after = board_before.copy()
    board_after.push(played_move)

    before = _winnable_squares(board_before, mover)
    # The opponent is to move here, so "can they actually take it" is a
    # question the board can answer exactly. See _winnable's docstring for why
    # the before-snapshot deliberately stays pseudo-legal.
    after = _winnable_squares(board_after, mover, require_legal_capture=True)

    # Newly winnable squares (created by the move).
    newly = {sq: pc for sq, pc in after.items() if sq not in before}
    if not newly:
        return None

    # Pick the most valuable newly-hanging piece.
    best_sq = max(newly, key=lambda s: _PIECE_VALUE[newly[s].piece_type])
    pc = newly[best_sq]
    hung_value = _PIECE_VALUE[pc.piece_type]

    # A piece that just CAPTURED is not hanging because it gets taken back --
    # that is a trade. Measured on 890 production fires: 193 (21.7%) were an
    # even trade reported as a hang. Bxf3 takes a knight, gxf3 takes the
    # bishop, net zero, and the player was told the bishop hung.
    #
    # The cp_loss >= 100 gate below does not catch these, because the move can
    # be genuinely bad for an unrelated reason -- in the canonical case Bxf3
    # cost 180cp by missing Nxf3+, which wins a rook. The move was a mistake;
    # the hang was not why.
    #
    # `grade_destination_safety_candidate` already prices this correctly with
    # `exact_gain - captured_before_reply`. This is the same subtraction, for
    # the detector that never had it.
    if best_sq == played_move.to_square:
        from services.legal_exchange_verifier import (
            captured_value_cp,
            independent_exchange_gain,
            promotion_gain_cp,
        )

        took = captured_value_cp(board_before, played_move) + promotion_gain_cp(
            played_move)
        if took > 0:
            loses = independent_exchange_gain(board_after, best_sq)
            if took - loses >= 0:
                return None

    # A forced mate on the board is not a material loss, whatever the swing
    # measured. `cp_loss >= MATE_SCORE_CP` catches most of it and misses the
    # case that matters: a player who was ALREADY lost walks into mate, so the
    # delta is small (one real case at 3,449) while the position is mate. The
    # caller knows -- the review queue has mate_info, the caption path has the
    # evals -- so it says so rather than being inferred from a subtraction.
    if mate_in_play:
        return None

    # Apply gates when cp_loss is known.
    if cp_loss is not None:
        # A mate score is not a material loss. Stockfish stores mate as a huge
        # centipawn value (10000 - 10*mate_in), so anything at or above 9000
        # means the game ended or is ending by force -- the same convention
        # move_classification_service, distilled_caption_service,
        # mistake_streak_service and position_strategy_analyzer already use.
        #
        # Mohit's rule: a bigger loss means a PIECE went rather than a pawn.
        # Measured over 9,000 user mistakes it holds cleanly -- piece vs pawn
        # goes 1.1x, 1.5x, 2.2x, 4.0x, 8.1x as the loss grows -- and then
        # REVERSES above 900, where 47.9% of moves lose no material at all.
        # Those are mate swings. Testing his rule is what exposed 41 cards
        # telling a player "your queen on e3 is hanging" when the truth was
        # "you are getting mated in 6", and one where the player was ALREADY
        # being mated before the move.
        #
        # The mate path has its own voice (analysis_interpreter's mate gate,
        # and R12's mate branch). This one stays quiet so that one speaks.
        if cp_loss >= MATE_SCORE_CP:
            return None
        if cp_loss < 100:
            return None
        if hung_value < 0.5 * min(cp_loss, 900):
            return None

    return {
        "square": chess.square_name(best_sq),
        "piece": _PIECE_NAME.get(pc.piece_type, "piece"),
        "moved_piece": best_sq == played_move.to_square,
        "defenders": [chess.square_name(s)
                      for s in board_after.attackers(mover, best_sq)],
    }


def clause_for(hang: Dict) -> str:
    """The R12 failure-mode clause text (1200-friendly, names the square).

    "No defender" is a claim about the board and has to be checked. It used to
    be inferred from whether the hung piece was the one that just moved, which
    is a different question -- a rook on e3 defended by a bishop on g5 was
    still told it had no defender.
    """
    if hang.get("defenders"):
        return (f"it leaves your {hang['piece']} on {hang['square']} hanging — "
                "the defenders do not cover it")
    if hang["moved_piece"]:
        return f"it leaves your {hang['piece']} on {hang['square']} hanging — no defender after the move"
    return f"it leaves your {hang['piece']} on {hang['square']} hanging — its defender just moved away"
