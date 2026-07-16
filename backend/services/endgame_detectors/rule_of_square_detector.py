"""
Rule of the Square Detector — Deterministic endgame principle analyzer.

The rule of the square: In a K+P vs K endgame, the king can catch the pawn
if it can move into an imaginary square with the pawn at one corner.

Distance calculation:
  - If king can reach the queening square within N moves where N = distance
    from pawn to queening square, the king catches it (rule applies).
  - Otherwise, the pawn queens (rule violated).
"""

import chess
from typing import Optional, Tuple


def detect_rule_of_square(
    board: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    """
    Detect if a move demonstrates understanding of the rule of the square.

    Args:
        board: Position BEFORE the move
        move: The move being played (in User's perspective)
        user_color: User's color (chess.WHITE or chess.BLACK)

    Returns:
        "applies"  → move correctly uses rule of square (catches pawn or avoids loss)
        "violates" → move ignores rule of square (allows pawn to queen)
        None       → rule of square not relevant to this position
    """

    # Check if position is a K+P vs K endgame
    if not _is_kp_vs_k_endgame(board):
        return None

    # Identify which side has pawn, which has king
    white_has_pawn = bool(board.pieces(chess.PAWN, chess.WHITE))
    black_has_pawn = bool(board.pieces(chess.PAWN, chess.BLACK))

    if white_has_pawn and black_has_pawn:
        return None  # Multiple pawns, not simple K+P vs K

    if not (white_has_pawn or black_has_pawn):
        return None  # No pawns at all

    # Determine attacking side (has pawn) and defending side (has king only)
    attacking_side = chess.WHITE if white_has_pawn else chess.BLACK
    defending_side = chess.BLACK if white_has_pawn else chess.WHITE

    # User must be the defending side (trying to catch the pawn)
    if user_color != defending_side:
        return None  # User is attacking; rule of square not their concern

    # Get pawn and defending king positions
    pawn_sq = list(board.pieces(chess.PAWN, attacking_side))[0]
    defending_king_sq = board.king(defending_side)

    # Apply rule of the square BEFORE the move
    pawn_can_be_caught_before = _can_king_catch_pawn(board, defending_king_sq, pawn_sq, defending_side)

    # Apply rule after the move
    board.push(move)
    new_king_sq = board.king(defending_side)
    # Check if pawn advanced
    new_pawn_sq = _get_pawn_position(board, attacking_side) or pawn_sq
    pawn_can_be_caught_after = _can_king_catch_pawn(board, new_king_sq, new_pawn_sq, defending_side)
    board.pop()

    # Analyze the move
    if pawn_can_be_caught_after:
        # King can still catch pawn after move
        return "applies"
    elif pawn_can_be_caught_before and not pawn_can_be_caught_after:
        # Move lost the catching zone (violated rule)
        return "violates"
    elif not pawn_can_be_caught_before:
        # Pawn was already queening; move doesn't matter
        return None

    return None


# =============================================================================
# Rule-of-the-square POSITION classifier (concept-accurate, engine-validated).
#
# The rule of the square is a DECISION concept, not a material count: a position
# qualifies when a pawn's fate is decided SOLELY by whether the defending king
# can enter the square. Concretely:
#   - no non-king, non-pawn piece on the board (a N/B/R/Q would be the stopper
#     or escort — that's Lucena / Philidor / knight-blockade, not rule of square);
#   - at least one passed pawn (a real promotion threat);
#   - the OTHER pawns must not change the outcome. Verified with the engine by
#     "strip and compare": eval the full position, then eval "both kings + the
#     critical passed pawn only". If the verdict (win/draw/loss) is unchanged,
#     the king-vs-pawn race is what decides -> rule of the square.
# Keeps: K+P vs K, K+P + irrelevant pawns, simplifications into pawn races, and
# opposite-side races (mutual passers whose two-pawn race reproduces the verdict).
# Rejects: piece-controlled and other-pawn-decided positions.
#
# Callers pass a chess.engine instance for the precise check. Without one it
# falls back to a permissive deterministic filter (no pieces + a passed pawn) so
# extraction never crashes when Stockfish is unavailable.
# =============================================================================

_NON_PAWN_PIECES = (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)


def _has_non_pawn_pieces(board: chess.Board) -> bool:
    return any(board.pieces(pt, c) for pt in _NON_PAWN_PIECES for c in (chess.WHITE, chess.BLACK))


def _passed_pawns(board: chess.Board, color: chess.Color) -> list:
    """Squares of `color`'s passed pawns (no enemy pawn on same/adjacent file ahead)."""
    out = []
    enemy = board.pieces(chess.PAWN, not color)
    for sq in board.pieces(chess.PAWN, color):
        f, r = chess.square_file(sq), chess.square_rank(sq)

        def ahead(e):
            er = chess.square_rank(e)
            return er > r if color == chess.WHITE else er < r

        if not any(abs(chess.square_file(e) - f) <= 1 and ahead(e) for e in enemy):
            out.append(sq)
    return out


def _verdict(board: chess.Board, engine) -> str:
    """Coarse White-POV verdict (win/draw/loss) — enough for king-and-pawn races."""
    import chess.engine
    sc = engine.analyse(board, chess.engine.Limit(depth=14))["score"].white().score(mate_score=100000)
    if sc is None:
        return "?"
    return "white" if sc > 150 else "black" if sc < -150 else "draw"


def _kings_and_pawns_board(board: chess.Board, pawns: list) -> chess.Board:
    """A board with only the two kings + the given [(square, color), ...] pawns."""
    nb = chess.Board.empty()
    nb.turn = board.turn
    nb.set_piece_at(board.king(chess.WHITE), chess.Piece(chess.KING, chess.WHITE))
    nb.set_piece_at(board.king(chess.BLACK), chess.Piece(chess.KING, chess.BLACK))
    for sq, color in pawns:
        nb.set_piece_at(sq, chess.Piece(chess.PAWN, color))
    return nb


def _most_advanced(squares: list, color: chess.Color):
    """The passed pawn closest to promotion for `color`."""
    if not squares:
        return None
    key = (lambda s: chess.square_rank(s)) if color == chess.WHITE else (lambda s: -chess.square_rank(s))
    return max(squares, key=key)


def is_rule_of_square_relevant(fen: str, engine=None) -> bool:
    """True iff the position is a genuine rule-of-the-square lesson (see module
    header). Pass a chess.engine instance for the precise strip-and-compare
    check; without one, uses a permissive deterministic fallback that never
    crashes."""
    try:
        board = chess.Board(fen)
    except (ValueError, TypeError):
        return False
    if _has_non_pawn_pieces(board):
        return False  # a piece controls the race, not the king's square
    pw = _passed_pawns(board, chess.WHITE)
    pb = _passed_pawns(board, chess.BLACK)
    if not (pw or pb):
        return False  # no promotion threat
    if engine is None:
        return True  # deterministic fallback (permissive)
    try:
        full = _verdict(board, engine)
        # single-pawn race: does one passed pawn's isolated race reproduce the outcome?
        for sq in pw:
            if _verdict(_kings_and_pawns_board(board, [(sq, chess.WHITE)]), engine) == full:
                return True
        for sq in pb:
            if _verdict(_kings_and_pawns_board(board, [(sq, chess.BLACK)]), engine) == full:
                return True
        # opposite-side race: the two most-advanced passers, alone, reproduce it?
        if pw and pb:
            wq, bq = _most_advanced(pw, chess.WHITE), _most_advanced(pb, chess.BLACK)
            two = _kings_and_pawns_board(board, [(wq, chess.WHITE), (bq, chess.BLACK)])
            if _verdict(two, engine) == full:
                return True
        return False
    except Exception:
        return True  # engine hiccup -> keep the plausible candidate rather than crash


def _is_kp_vs_k_endgame(board: chess.Board) -> bool:
    """Check if position is K+P vs K (or close to it)"""
    # Only kings and at most one pawn total
    total_pieces = sum(
        len(board.pieces(piece, color))
        for piece in [chess.PAWN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.QUEEN]
        for color in [chess.WHITE, chess.BLACK]
    )

    total_pawns = len(board.pieces(chess.PAWN, chess.WHITE)) + len(board.pieces(chess.PAWN, chess.BLACK))

    return total_pieces <= 1 and total_pawns <= 1


def _get_pawn_position(board: chess.Board, color: chess.Color) -> Optional[int]:
    """Get square of pawn for given color, or None if no pawn"""
    pawns = list(board.pieces(chess.PAWN, color))
    return pawns[0] if pawns else None


def _can_king_catch_pawn(
    board: chess.Board,
    king_sq: int,
    pawn_sq: int,
    king_color: chess.Color,
) -> bool:
    """
    Apply rule of the square: can the king catch the pawn?

    The rule: Imagine a square with the pawn at one corner and the queening
    square at opposite corner. If the king can step into this square, it can
    catch the pawn.

    Simpler calculation:
    - Moves to queen: distance from pawn to 8th rank (for white) or 1st rank (for black)
    - If king can reach queening square in <= moves_to_queen, king catches pawn
    """

    pawn_file = chess.square_file(pawn_sq)
    pawn_rank = chess.square_rank(pawn_sq)
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)

    # Queening rank
    pawn_owner = chess.WHITE if pawn_rank < 4 else chess.BLACK
    queening_rank = 7 if pawn_owner == chess.WHITE else 0
    queening_sq = chess.square(pawn_file, queening_rank)

    # Moves needed for pawn to queen
    pawn_moves_to_queen = abs(pawn_rank - queening_rank)

    # Moves needed for king to reach queening square
    king_moves_to_queen = max(abs(king_file - pawn_file), abs(king_rank - queening_rank))

    # Rule of the square: king catches if it reaches within pawn_moves_to_queen moves
    # Add 1 because if king can reach queening square in same moves, it's too late
    return king_moves_to_queen < pawn_moves_to_queen or (
        king_moves_to_queen == pawn_moves_to_queen and board.turn != pawn_owner
    )
