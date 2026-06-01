"""
Rule-of-the-Square in-game detector.

The rule: a passed pawn racing toward promotion is uncatchable by the
defending king iff the king cannot step into the geometric "square"
running from the pawn's current rank to its promotion rank. The
defending king, on its move, gets one tempo to enter the zone.

Mohit 2026-06-01: original detector only fired on pure K+P vs K
(exactly 3 pieces on the board). That's too strict — the SKILL applies
any time a passed pawn race is the decisive question and the
defending king is the only realistic stopper. Empirically: 0 fires
on 50 of Mohit's analyzed games. Widened the definition to fire on
ANY position where:

  1. There exists a passed pawn (no enemy pawn on same / adjacent
     files ahead of it).
  2. The pawn is past the middle of the board (rank >= 4 for white,
     <= 4 for black) — race is real.
  3. The path to promotion (squares the pawn will traverse) is empty
     AND not attacked by any non-king enemy piece.
  4. The promotion square itself is not attacked by any non-king
     enemy piece.
  5. The pawn itself is not attacked by any non-king enemy piece
     (no easy capture by rook / bishop / knight).
  6. No own piece blocks the pawn's path.

When all six hold, the king-vs-pawn geometric square IS the decisive
question. Other pieces are spectators in this race.

PRECISION GUARDS for the verdict:

  Attacker (owns the racing pawn):
    - Race wins:   pushing THIS pawn → "applied". Any other move → None
                   (don't grade — user might be doing something else
                   tactical that's also fine).
    - Race fails:  pawn push → "missed". King move → "applied".
                   Other → None.

  Defender:
    - King already in zone → None (no clean test).
    - Catchable + user moves king into zone → "applied".
    - Catchable + user moves king OUT of zone → "missed".
    - Catchable + user moves a non-king piece → None (other-piece
      response might be a tactical reason we can't assess here; don't
      falsely penalise).

This errs on the side of FALSE NEGATIVES, not false positives. The
worst case is the user doesn't get credited for a position they
played correctly. The best case is we get an accurate "seen" count.

Scope: see the empirical scan results in commit message. Backfill
script in scripts/backfill_rule_of_square_evidence.py credits the
two cleanly-applied cases in Mohit's last 50 games against
coach_memory.
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
    """Exactly two kings + one pawn on the board.

    Kept for callers that want the strict version. The detector itself
    no longer requires this — see is_pure_king_pawn_race.
    """
    pieces = list(board.piece_map().values())
    if len(pieces) != 3:
        return False
    kings = sum(1 for p in pieces if p.piece_type == chess.KING)
    pawns = sum(1 for p in pieces if p.piece_type == chess.PAWN)
    return kings == 2 and pawns == 1


def _is_passed_pawn(board: chess.Board, sq: int, color: chess.Color) -> bool:
    """No enemy pawn on same / adjacent files ahead of this pawn."""
    f = chess.square_file(sq)
    r = chess.square_rank(sq)
    enemy_color = not color
    direction = 1 if color == chess.WHITE else -1
    for ef in (f - 1, f, f + 1):
        if not (0 <= ef <= 7):
            continue
        for er in range(r + direction, 8 if color == chess.WHITE else -1, direction):
            t = chess.square(ef, er)
            p = board.piece_at(t)
            if p and p.piece_type == chess.PAWN and p.color == enemy_color:
                return False
    return True


def _path_to_promotion(sq: int, color: chess.Color):
    """Squares the pawn traverses to promote (exclusive of current, inclusive of promotion)."""
    f = chess.square_file(sq)
    r = chess.square_rank(sq)
    promo = 7 if color == chess.WHITE else 0
    step = 1 if color == chess.WHITE else -1
    return [chess.square(f, rr) for rr in range(r + step, promo + step, step)]


def is_pure_king_pawn_race(board: chess.Board, pawn_sq: int, pawn_color: chess.Color) -> bool:
    """Is the pawn on this square in a clean king-vs-pawn race?

    Six conditions (see module docstring). Returns True only when the
    geometric square calculation IS the decisive question for this
    position.
    """
    if not _is_passed_pawn(board, pawn_sq, pawn_color):
        return False
    pawn_rank = chess.square_rank(pawn_sq)
    if pawn_color == chess.WHITE and pawn_rank < 3:
        return False  # rank 4+ in human terms (0-indexed rank 3)
    if pawn_color == chess.BLACK and pawn_rank > 4:
        return False
    path = _path_to_promotion(pawn_sq, pawn_color)
    if not path:
        return False
    enemy = not pawn_color
    for sq in path:
        if board.piece_at(sq):
            return False  # path blocked (could be own piece or enemy)
        for atk in board.attackers(enemy, sq):
            pc = board.piece_at(atk)
            if pc and pc.piece_type != chess.KING:
                return False  # non-king enemy attacks the path
    for atk in board.attackers(enemy, pawn_sq):
        pc = board.piece_at(atk)
        if pc and pc.piece_type != chess.KING:
            return False  # pawn itself capturable by non-king enemy
    return True


def _defender_can_reach_zone(
    board: chess.Board,
    defender_king: chess.Square,
    catch_zone: Set[chess.Square],
    side_to_move: chess.Color,
    defender_color: chess.Color,
) -> bool:
    """Can the defending king step into the zone (one tempo) or is it
    already there?
    """
    if defender_king in catch_zone:
        return True

    if side_to_move == defender_color:
        for to_sq in chess.SquareSet(chess.BB_KING_ATTACKS[defender_king]):
            if to_sq in catch_zone:
                if chess.Move(defender_king, to_sq) in board.legal_moves:
                    return True
        return False

    return False


def detect_rule_of_the_square_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    """Was this move a clean test of the rule of the square?

    Args:
        board_before: position immediately before `move` is played.
        move:         the user's move.
        user_color:   chess.WHITE or chess.BLACK — the user's side.

    Returns:
        "applied" | "missed" | None

    See module docstring for the broadened detection rules and the
    precision guards on the verdict.
    """
    if board_before.turn != user_color:
        return None

    # Find a passed pawn whose race is the clean test.
    # If multiple passed pawns qualify, take the first one — multi-race
    # situations are rare and the rule applies to each independently.
    qualifying_pawn = None
    for sq, p in board_before.piece_map().items():
        if p.piece_type != chess.PAWN:
            continue
        if is_pure_king_pawn_race(board_before, sq, p.color):
            qualifying_pawn = (sq, p.color)
            break

    if qualifying_pawn is None:
        return None

    pawn_sq, pawn_color = qualifying_pawn
    user_is_attacker = (user_color == pawn_color)
    defender_color = not pawn_color
    defender_king = board_before.king(defender_color)
    if defender_king is None:
        return None

    catch_zone = square_of_the_pawn(pawn_sq, pawn_color)
    catchable = _defender_can_reach_zone(
        board_before, defender_king, catch_zone,
        side_to_move=board_before.turn,
        defender_color=defender_color,
    )

    moved_piece = board_before.piece_at(move.from_square)
    if moved_piece is None:
        return None

    is_pawn_push = (
        moved_piece.piece_type == chess.PAWN
        and moved_piece.color == user_color
        and move.from_square == pawn_sq
    )
    is_king_move = (
        moved_piece.piece_type == chess.KING
        and moved_piece.color == user_color
    )

    # PRECISION GUARDS: only credit "applied" when the user clearly
    # demonstrated the skill, and only flag "missed" when the user
    # CLEARLY did the wrong thing. For anything ambiguous (e.g. the
    # attacker walks the king to support a race they've already won),
    # return None — neither credit nor penalise.
    if user_is_attacker:
        if not catchable:
            # Race wins: pushing is the canonical skill demonstration.
            # Walking the king is fine in many positions (supporting
            # the promotion / king activation) — don't penalise.
            if is_pawn_push:
                return "applied"
            return None
        else:
            # Race fails: pushing into a lost race is a clear miss.
            # Bringing the king is the right answer.
            if is_pawn_push:
                return "missed"
            if is_king_move:
                return "applied"
            return None

    # User is the defender — must catch with the king.
    if defender_king in catch_zone:
        return None  # already safe; no clean test
    if not catchable:
        return None  # lost by force; don't grade

    # Clean test: must step the king into the zone this move.
    if is_king_move:
        return "applied" if move.to_square in catch_zone else "missed"
    return None  # non-king move — could be tactical, don't grade
