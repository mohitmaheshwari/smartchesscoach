"""
Rule-of-the-Square in-game detector.

The rule: a passed pawn is uncatchable by the lone defending king iff
the king cannot step into the geometric "square" running from the
pawn's current rank to its promotion rank. The defending king, on its
move, gets one tempo to enter the zone.

Decision logic:

    User is the defender (no pawn of their own threatening to promote):
        - Catchable on this move      → must step into zone        (test fires)
        - Already inside zone         → trivial; not a teaching pos (skip)
        - Uncatchable                 → lost; not a teaching pos    (skip)

    User is the attacker (owns the passed pawn):
        - Defender cannot catch       → push the pawn (race)        (test fires)
        - Defender can catch          → bring your king instead     (test fires)
        - Promotion already inevitable → skip

Scope: pure K+P vs K only. With more pieces on the board the rule is
no longer the decisive theme and false positives multiply, so we
intentionally return None.
"""

from typing import Optional, Set

import chess


def square_of_the_pawn(
    pawn_square: chess.Square,
    pawn_color: chess.Color,
) -> Set[chess.Square]:
    """The set of squares the defending king must reach to catch the pawn.

    Geometric square from pawn rank to promotion rank, width = distance.
    """
    pawn_file = chess.square_file(pawn_square)
    pawn_rank = chess.square_rank(pawn_square)
    promotion_rank = 7 if pawn_color == chess.WHITE else 0
    distance = abs(promotion_rank - pawn_rank)

    rank_lo = min(pawn_rank, promotion_rank)
    rank_hi = max(pawn_rank, promotion_rank)
    file_lo = max(0, pawn_file - distance)
    file_hi = min(7, pawn_file + distance)

    return {
        chess.square(f, r)
        for f in range(file_lo, file_hi + 1)
        for r in range(rank_lo, rank_hi + 1)
    }


def is_kp_vs_k(board: chess.Board) -> bool:
    """Exactly two kings + one pawn on the board."""
    pieces = list(board.piece_map().values())
    if len(pieces) != 3:
        return False
    kings = sum(1 for p in pieces if p.piece_type == chess.KING)
    pawns = sum(1 for p in pieces if p.piece_type == chess.PAWN)
    return kings == 2 and pawns == 1


def _defender_can_reach_zone(
    board: chess.Board,
    defender_king: chess.Square,
    catch_zone: Set[chess.Square],
    side_to_move: chess.Color,
    defender_color: chess.Color,
) -> bool:
    """Can the defending king step into the zone (one tempo) or is it
    already there?

    If it's the defender's move, they get the tempo. Otherwise the pawn
    pushes once first; we approximate by checking whether the defender
    is already inside the zone-after-push.
    """
    if defender_king in catch_zone:
        return True

    if side_to_move == defender_color:
        # Defender to move: any king step into the zone counts.
        for to_sq in chess.SquareSet(chess.BB_KING_ATTACKS[defender_king]):
            if to_sq in catch_zone:
                # Sanity check the move is actually legal (square not
                # adjacent to enemy king, etc.).
                if chess.Move(defender_king, to_sq) in board.legal_moves:
                    return True
        return False

    # Attacker to move: pawn will push, shrinking the zone by one rank.
    # If defender isn't already in the post-push zone, they can't catch.
    return False


def detect_rule_of_the_square_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    """Was this move a clean test of the rule of the square, and did the
    user pass?

    Args:
        board_before: position immediately before `move` is played.
        move:         the user's move.
        user_color:   chess.WHITE or chess.BLACK — the user's side.

    Returns:
        "applied" | "missed" | None
    """
    if not is_kp_vs_k(board_before):
        return None
    if board_before.turn != user_color:
        return None

    # Find the pawn.
    pawn_square = None
    pawn_color = None
    for square, piece in board_before.piece_map().items():
        if piece.piece_type == chess.PAWN:
            pawn_square = square
            pawn_color = piece.color
            break
    if pawn_square is None:
        return None

    user_is_attacker = (user_color == pawn_color)
    defender_color = not pawn_color
    defender_king = board_before.king(defender_color)
    if defender_king is None:
        return None

    catch_zone = square_of_the_pawn(pawn_square, pawn_color)
    catchable = _defender_can_reach_zone(
        board_before, defender_king, catch_zone,
        side_to_move=board_before.turn,
        defender_color=defender_color,
    )

    moved_piece = board_before.piece_at(move.from_square)
    if moved_piece is None:
        return None

    if user_is_attacker:
        is_pawn_push = moved_piece.piece_type == chess.PAWN
        if not catchable:
            # Race wins: push the pawn.
            return "applied" if is_pawn_push else "missed"
        # Catchable: must bring the king (any non-pawn move that
        # doesn't lose the pawn). Treat king move as the canonical
        # right answer; pawn push is the canonical wrong answer.
        if is_pawn_push:
            return "missed"
        if moved_piece.piece_type == chess.KING:
            return "applied"
        return None  # other piece type — shouldn't happen in K+P vs K

    # User is the defender.
    if defender_king in catch_zone:
        return None  # already safe; no clean test
    if not catchable:
        return None  # lost by force; don't grade

    # Clean test: must step into the zone this move.
    landed_in_zone = move.to_square in catch_zone
    if moved_piece.piece_type != chess.KING:
        return "missed"  # only legal piece is the king anyway, but be explicit
    return "applied" if landed_in_zone else "missed"
