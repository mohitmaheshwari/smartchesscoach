"""
Trap Detection Service — Escape Square Awareness Engine (v2)
=============================================================

Detects trapped and nearly-trapped opponent pieces using a coach-like
approach: ray tracing, restriction analysis, punishability check.

Classifications:
  TRAPPED        — 0 safe escapes, no freeing move, enemy-restricted, punishable
  ALMOST_TRAPPED — ≤2 safe escapes, enemy restriction dominates
  (CRAMPED)      — mostly own-piece blocks, can be freed → NOT reported

Key design:
  - Light SEE (2-3 exchange depth) for escape safety
  - Ray tracing to distinguish own-piece blocks vs enemy control
  - Freeing move check (can adjacent own pieces unblock?)
  - Punishability gate (can we actually win the piece?)
  - Max 1-2 results per position to avoid over-reporting
"""

import chess
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

PIECE_NAMES = {
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
}

# Pre-filter thresholds: below this legal move count, piece MIGHT be restricted
SPATIAL_THRESHOLDS = {
    chess.KNIGHT: 4,
    chess.BISHOP: 3,
    chess.ROOK: 3,
    chess.QUEEN: 5,
}

# Starting squares for each piece type + color
STARTING_SQUARES = {
    (chess.ROOK, chess.WHITE): {chess.A1, chess.H1},
    (chess.ROOK, chess.BLACK): {chess.A8, chess.H8},
    (chess.KNIGHT, chess.WHITE): {chess.B1, chess.G1},
    (chess.KNIGHT, chess.BLACK): {chess.B8, chess.G8},
    (chess.BISHOP, chess.WHITE): {chess.C1, chess.F1},
    (chess.BISHOP, chess.BLACK): {chess.C8, chess.F8},
    (chess.QUEEN, chess.WHITE): {chess.D1},
    (chess.QUEEN, chess.BLACK): {chess.D8},
}


@dataclass
class TrapOpportunity:
    """A detected trap opportunity on the board."""
    target_square: str
    target_piece: str
    target_piece_symbol: str
    escape_count: int
    escape_squares: List[str]
    blocked_squares: List[str]
    reduction_moves: List[Dict]
    trap_level: str               # "trapped", "near_trap", "pressured" (backward compat)
    value: int
    is_attacked: bool
    classification: str = ""      # "TRAPPED" or "ALMOST_TRAPPED"
    reason: str = ""              # Human-readable explanation
    is_trappable_in_2: bool = False
    trap_sequence: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# LIGHT SEE — Static Exchange Evaluation (simplified, 2-3 depth)
# ═══════════════════════════════════════════════════════════════════════

def _light_see(board: chess.Board, target_sq: int, side_to_capture: chess.Color) -> int:
    """
    Simplified SEE: simulate capture chain on target_sq.
    Returns material gain/loss for side_to_capture.
    Positive = winning, negative = losing.

    Limits to 3 exchanges for speed.
    """
    sim = board.copy()
    gains = []
    current_side = side_to_capture

    target_piece = sim.piece_at(target_sq)
    if not target_piece:
        return 0

    gains.append(PIECE_VALUES.get(target_piece.piece_type, 0))

    for _ in range(3):  # Max 3 exchanges
        # Find cheapest attacker for current_side
        attackers = list(sim.attackers(current_side, target_sq))
        if not attackers:
            break

        cheapest = min(attackers, key=lambda sq: PIECE_VALUES.get(
            sim.piece_at(sq).piece_type, 99) if sim.piece_at(sq) else 99)
        attacker_piece = sim.piece_at(cheapest)
        if not attacker_piece:
            break

        # Simulate the capture
        move = chess.Move(cheapest, target_sq)
        if move not in sim.legal_moves:
            # Try with promotion
            move = chess.Move(cheapest, target_sq, promotion=chess.QUEEN)
            if move not in sim.legal_moves:
                break

        gains.append(PIECE_VALUES.get(attacker_piece.piece_type, 0))
        sim.push(move)
        current_side = not current_side

    # Minimax the gains
    # gains[0] = value of initial capture
    # gains[1] = value of recapture piece (what we lose if they retake)
    # etc.
    score = 0
    for i in range(len(gains) - 1, -1, -1):
        score = max(gains[i] - score, 0) if i % 2 == 0 else min(score - gains[i], 0)

    # Simpler: just check if first capture is worth it
    # gains[0] = what we win, gains[1] = what we might lose
    if len(gains) >= 2:
        net = gains[0] - gains[1]
        if len(gains) >= 3:
            net += gains[2]
        return net
    return gains[0] if gains else 0


def _is_safe_escape(board: chess.Board, piece_sq: int, dest_sq: int,
                     piece_color: chess.Color, user_color: chess.Color) -> bool:
    """
    Check if moving piece from piece_sq to dest_sq is safe.

    Safe if:
    - Destination not attacked by opponent → safe
    - Destination attacked → run light SEE → safe only if not losing
    """
    # Make the move
    move = chess.Move(piece_sq, dest_sq)
    sim = board.copy()

    # Flip turn if needed so the piece can move
    if sim.turn != piece_color:
        fen_parts = sim.fen().split(' ')
        fen_parts[1] = 'w' if piece_color == chess.WHITE else 'b'
        try:
            sim = chess.Board(' '.join(fen_parts))
        except ValueError:
            return False

    if move not in sim.legal_moves:
        move = chess.Move(piece_sq, dest_sq, promotion=chess.QUEEN)
        if move not in sim.legal_moves:
            return False

    sim.push(move)

    # After move, is the piece attacked?
    opponent = not piece_color
    if not sim.is_attacked_by(opponent, dest_sq):
        return True  # Not attacked → safe

    # Attacked — check if defenders hold
    attackers = list(sim.attackers(opponent, dest_sq))
    defenders = list(sim.attackers(piece_color, dest_sq))

    if not attackers:
        return True

    # Quick check: cheapest attacker value vs our piece value
    piece = sim.piece_at(dest_sq)
    if not piece:
        return True
    piece_val = PIECE_VALUES.get(piece.piece_type, 0)
    cheapest_attacker_val = min(
        (PIECE_VALUES.get(sim.piece_at(a).piece_type, 99) for a in attackers if sim.piece_at(a)),
        default=99
    )

    # If cheapest attacker is less valuable, we lose material
    if cheapest_attacker_val < piece_val and len(defenders) <= len(attackers):
        return False

    # If equal value and fewer defenders, losing
    if cheapest_attacker_val <= piece_val and len(defenders) < len(attackers):
        return False

    return True


# ═══════════════════════════════════════════════════════════════════════
# RAY TRACING — Identify WHY squares are blocked
# ═══════════════════════════════════════════════════════════════════════

def _analyze_restriction_causes(
    board: chess.Board, square: int, piece: chess.Piece, user_color: chess.Color,
    safe_escapes: List[int], unsafe_escapes: List[int]
) -> Dict:
    """
    Trace movement rays to determine what's blocking this piece.
    Returns counts of own-piece blocks vs enemy-controlled blocks.
    """
    piece_color = piece.color
    own_blocks = 0
    own_blocks_immobile = 0  # Pinned or no safe move → treat as enemy restriction
    enemy_blocks = len(unsafe_escapes)  # Unsafe destinations = enemy control
    geometric_blocks = 0

    if piece.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        # Sliding pieces: trace rays
        if piece.piece_type == chess.BISHOP:
            directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        elif piece.piece_type == chess.ROOK:
            directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        else:  # Queen
            directions = [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]

        file_idx = chess.square_file(square)
        rank_idx = chess.square_rank(square)

        for df, dr in directions:
            f, r = file_idx + df, rank_idx + dr
            if not (0 <= f <= 7 and 0 <= r <= 7):
                geometric_blocks += 1
                continue

            # Walk the ray until we hit something
            while 0 <= f <= 7 and 0 <= r <= 7:
                sq = chess.square(f, r)
                blocker = board.piece_at(sq)
                if blocker:
                    if blocker.color == piece_color:
                        own_blocks += 1
                        # Is this blocker immobile?
                        if board.is_pinned(piece_color, sq):
                            own_blocks_immobile += 1
                        elif not _has_safe_move(board, sq, piece_color):
                            own_blocks_immobile += 1
                    # Enemy blocker is already counted via unsafe_escapes
                    break
                f += df
                r += dr
            else:
                geometric_blocks += 1  # Ray hit board edge

    elif piece.piece_type == chess.KNIGHT:
        # Knight: check each potential jump square
        knight_offsets = [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                          (1, -2), (1, 2), (2, -1), (2, 1)]
        file_idx = chess.square_file(square)
        rank_idx = chess.square_rank(square)

        for df, dr in knight_offsets:
            f, r = file_idx + df, rank_idx + dr
            if not (0 <= f <= 7 and 0 <= r <= 7):
                geometric_blocks += 1
                continue
            sq = chess.square(f, r)
            blocker = board.piece_at(sq)
            if blocker and blocker.color == piece_color:
                own_blocks += 1
                if board.is_pinned(piece_color, sq) or not _has_safe_move(board, sq, piece_color):
                    own_blocks_immobile += 1

    # Immobile own blockers count as enemy restriction
    effective_enemy = enemy_blocks + own_blocks_immobile
    effective_own = own_blocks - own_blocks_immobile

    return {
        "own_blocks": effective_own,
        "enemy_blocks": effective_enemy,
        "geometric_blocks": geometric_blocks,
        "enemy_dominates": effective_enemy > effective_own,
    }


def _has_safe_move(board: chess.Board, square: int, color: chess.Color) -> bool:
    """Quick check: does this piece have at least one non-losing legal move?"""
    # Only check if it's this color's turn, or approximate
    if board.turn == color:
        for move in board.legal_moves:
            if move.from_square == square:
                return True
    else:
        # Approximate: check if piece has any attack squares not blocked
        attacks = board.attacks(square)
        for sq in attacks:
            target = board.piece_at(sq)
            if target is None or target.color != color:
                return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# FREEING MOVE CHECK — Can opponent unblock their own piece in 1 move?
# ═══════════════════════════════════════════════════════════════════════

def _has_freeing_move(board: chess.Board, trapped_sq: int, piece_color: chess.Color,
                       user_color: chess.Color) -> bool:
    """
    Check if the opponent can free their trapped piece in 1 move.
    Only checks obvious freeing moves (adjacent blockers, pawn pushes).
    Does NOT brute-force all legal moves.
    """
    piece = board.piece_at(trapped_sq)
    if not piece:
        return False

    # Find own pieces that are blocking escape squares
    blocker_squares = set()
    if piece.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        for sq in board.attacks(trapped_sq):
            blocker = board.piece_at(sq)
            if blocker and blocker.color == piece_color:
                blocker_squares.add(sq)
    elif piece.piece_type == chess.KNIGHT:
        knight_offsets = [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                          (1, -2), (1, 2), (2, -1), (2, 1)]
        f, r = chess.square_file(trapped_sq), chess.square_rank(trapped_sq)
        for df, dr in knight_offsets:
            nf, nr = f + df, r + dr
            if 0 <= nf <= 7 and 0 <= nr <= 7:
                sq = chess.square(nf, nr)
                blocker = board.piece_at(sq)
                if blocker and blocker.color == piece_color:
                    blocker_squares.add(sq)

    if not blocker_squares:
        return False

    # Check if it's opponent's turn (they can free their piece)
    if board.turn != piece_color:
        return False  # It's our turn, they can't free it right now

    # Check if any blocker can move away
    for blocker_sq in blocker_squares:
        if board.is_pinned(piece_color, blocker_sq):
            continue  # Pinned, can't move

        for move in board.legal_moves:
            if move.from_square == blocker_sq:
                # Would moving this blocker open an escape?
                test = board.copy()
                test.push(move)
                # Now check if the trapped piece has more safe escapes
                new_escapes = _count_safe_escapes_quick(test, trapped_sq, piece_color, user_color)
                if new_escapes > 0:
                    return True
                break  # Only need to check one move per blocker

    return False


def _count_safe_escapes_quick(board: chess.Board, square: int,
                                piece_color: chess.Color, user_color: chess.Color) -> int:
    """Quick count of safe escapes (no full analysis)."""
    # Flip turn if needed
    sim = board.copy()
    if sim.turn != piece_color:
        fen_parts = sim.fen().split(' ')
        fen_parts[1] = 'w' if piece_color == chess.WHITE else 'b'
        try:
            sim = chess.Board(' '.join(fen_parts))
        except ValueError:
            return 0

    count = 0
    for move in sim.legal_moves:
        if move.from_square == square:
            # Quick safety: not attacked, or defended
            sim2 = sim.copy()
            sim2.push(move)
            if not sim2.is_attacked_by(not piece_color, move.to_square):
                count += 1
            elif len(list(sim2.attackers(piece_color, move.to_square))) >= len(list(sim2.attackers(not piece_color, move.to_square))):
                count += 1
    return count


# ═══════════════════════════════════════════════════════════════════════
# PUNISHABILITY — Can we actually exploit this trap?
# ═══════════════════════════════════════════════════════════════════════

def _is_punishable(board: chess.Board, square: int, user_color: chess.Color,
                    safe_escape_count: int) -> bool:
    """
    Check if we can realistically win this piece.
    - Already under attack by us
    - We can attack it in 1 move
    - All exits covered and piece is stuck
    """
    # Already under direct attack
    if board.is_attacked_by(user_color, square):
        return True

    # Can we attack it in 1 move?
    if board.turn == user_color:
        for move in board.legal_moves:
            test = board.copy()
            test.push(move)
            if test.is_attacked_by(user_color, square):
                return True

    # All exits blocked and piece can't escape → it's stuck regardless
    if safe_escape_count == 0:
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════
# MAIN DETECTION — The core algorithm
# ═══════════════════════════════════════════════════════════════════════

def detect_trap_opportunities(board: chess.Board, user_color: chess.Color) -> List[TrapOpportunity]:
    """
    Detect trapped and nearly-trapped opponent pieces.

    Algorithm:
    1. Pre-filter: skip pieces with high mobility + not attacked + not spatially restricted
    2. Evaluate safe vs unsafe escapes (light SEE)
    3. Ray trace to identify WHY squares are blocked (own army vs enemy control)
    4. Check freeing moves (can own pieces unblock?)
    5. Punishability check (can we actually win it?)
    6. Classify: TRAPPED / ALMOST_TRAPPED / skip
    7. Return top 1-2 best opportunities

    Returns:
        List of TrapOpportunity sorted by priority (max 2)
    """
    opponent_color = not user_color
    candidates = []

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece or piece.color != opponent_color:
            continue
        if piece.piece_type in (chess.PAWN, chess.KING):
            continue

        piece_value = PIECE_VALUES.get(piece.piece_type, 0)
        piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
        is_attacked = board.is_attacked_by(user_color, square)

        # ── STEP 1: PRE-FILTER ──
        legal_moves = _get_piece_legal_moves(board, square, piece.color)
        legal_count = len(legal_moves)

        threshold = SPATIAL_THRESHOLDS.get(piece.piece_type, 4)

        # Edge check: only meaningful if the piece has MOVED from its home rank
        # A rook on a8 at game start is normal. A rook on a4 is on the edge in a real way.
        home_rank = 7 if piece.color == chess.BLACK else 0
        piece_rank = chess.square_rank(square)
        piece_file = chess.square_file(square)
        # "On the edge" = on a/h file or rank 1/8 BUT not on their starting rank
        is_edge = (piece_file in (0, 7) or piece_rank in (0, 7)) and piece_rank != home_rank

        spatially_restricted = legal_count < threshold or is_edge

        if legal_count >= 4 and not is_attacked and not spatially_restricted:
            continue  # Piece has plenty of mobility, skip

        # If piece has 0 legal moves and is on its STARTING SQUARE → just undeveloped, skip
        # A queen on d8 with 0 moves = undeveloped. A knight on a8 with 0 moves = trapped.
        is_on_starting_sq = square in STARTING_SQUARES.get((piece.piece_type, piece.color), set())
        if legal_count == 0 and is_on_starting_sq and not is_attacked:
            continue

        # ── STEP 2: EVALUATE SAFE VS UNSAFE ESCAPES ──
        safe_escapes = []
        unsafe_escapes = []

        for dest in legal_moves:
            if _is_safe_escape(board, square, dest, piece.color, user_color):
                safe_escapes.append(dest)
            else:
                unsafe_escapes.append(dest)

        safe_count = len(safe_escapes)

        # Quick exit: if 3+ safe escapes, not trapped
        if safe_count >= 3:
            continue

        # If piece is on its starting square and has 2+ safe escapes → undeveloped, not trapped
        if is_on_starting_sq and safe_count >= 2:
            continue

        # ── STEP 3: RAY TRACE — why is it restricted? ──
        restriction = _analyze_restriction_causes(
            board, square, piece, user_color, safe_escapes, unsafe_escapes
        )

        # ── STEP 4: CHECK FREEING MOVES ──
        freeing = _has_freeing_move(board, square, piece.color, user_color)

        # ── STEP 5: PUNISHABILITY ──
        punishable = _is_punishable(board, square, user_color, safe_count)

        # ── STEP 6: CLASSIFY ──
        classification = None
        trap_level = None

        if (safe_count == 0
                and not freeing
                and restriction["enemy_dominates"]
                and punishable):
            classification = "TRAPPED"
            trap_level = "trapped"

        elif (safe_count <= 2
              and restriction["enemy_dominates"]):
            classification = "ALMOST_TRAPPED"
            trap_level = "near_trap" if safe_count <= 1 else "pressured"

        elif (safe_count == 0
              and not freeing
              and punishable):
            # Edge case: mostly own-piece blocks but all immobile → still trapped
            classification = "TRAPPED"
            trap_level = "trapped"

        if not classification:
            continue  # CRAMPED or fine → don't report

        # ── BUILD RESULT ──
        safe_sq_names = [chess.square_name(s) for s in safe_escapes]
        unsafe_sq_names = [chess.square_name(s) for s in unsafe_escapes]

        # Find reduction moves (only for ALMOST_TRAPPED with safe escapes)
        reduction_moves = []
        if safe_count > 0 and board.turn == user_color:
            reduction_moves = find_escape_reducers(
                board, square, safe_sq_names, user_color
            )

        # 2-move trap sequence
        trap_sequence = []
        is_trappable_in_2 = False
        if safe_count in (1, 2) and reduction_moves and board.turn == user_color:
            try:
                seq = find_forced_trap_sequence(
                    board, square, safe_sq_names, reduction_moves, user_color
                )
                if seq:
                    is_trappable_in_2 = True
                    trap_sequence = seq
            except Exception:
                pass

        # Generate reason
        reason = _generate_reason(piece_name, chess.square_name(square),
                                   safe_count, classification, is_attacked,
                                   restriction, is_trappable_in_2)

        candidates.append(TrapOpportunity(
            target_square=chess.square_name(square),
            target_piece=piece_name,
            target_piece_symbol=piece.symbol().upper(),
            escape_count=safe_count,
            escape_squares=safe_sq_names,
            blocked_squares=unsafe_sq_names,
            reduction_moves=reduction_moves[:3],
            trap_level=trap_level,
            value=piece_value,
            is_attacked=is_attacked,
            classification=classification,
            reason=reason,
            is_trappable_in_2=is_trappable_in_2,
            trap_sequence=trap_sequence,
        ))

    # ── STEP 7: SORT AND LIMIT ──
    # Priority: TRAPPED > ALMOST_TRAPPED, then by piece value, then fewer escapes
    candidates.sort(key=lambda t: (
        0 if t.classification == "TRAPPED" else 1,
        -t.value,
        t.escape_count,
    ))

    return candidates[:2]  # Max 2 results per position


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _get_piece_legal_moves(board: chess.Board, square: int, piece_color: chess.Color) -> List[int]:
    """Get legal destination squares for a piece, handling turn-flipping."""
    sim = board.copy()
    if sim.turn != piece_color:
        fen_parts = sim.fen().split(' ')
        fen_parts[1] = 'w' if piece_color == chess.WHITE else 'b'
        try:
            sim = chess.Board(' '.join(fen_parts))
        except ValueError:
            return []

    return [m.to_square for m in sim.legal_moves if m.from_square == square]


def _generate_reason(piece_name: str, square: str, safe_count: int,
                      classification: str, is_attacked: bool,
                      restriction: Dict, is_trappable_in_2: bool) -> str:
    """Generate a short, human-readable explanation."""
    if classification == "TRAPPED":
        if is_attacked:
            return f"Their {piece_name} on {square} is trapped and under attack — no safe squares left."
        if is_trappable_in_2:
            return f"Their {piece_name} on {square} is trapped. It has nowhere safe to go."
        return f"Their {piece_name} on {square} has no safe squares. Find a way to attack it."

    # ALMOST_TRAPPED
    if safe_count == 1:
        return f"Their {piece_name} has only 1 safe square. Block it and the {piece_name} is yours."
    if is_trappable_in_2:
        return f"Their {piece_name} can be trapped in 2 moves. It only has {safe_count} safe squares left."
    return f"Their {piece_name} on {square} has only {safe_count} safe squares — it's running out of room."


# ═══════════════════════════════════════════════════════════════════════
# ESCAPE REDUCERS — Find moves that reduce opponent's escapes
# ═══════════════════════════════════════════════════════════════════════

def find_escape_reducers(
    board: chess.Board,
    target_square: int,
    escape_squares: List[str],
    user_color: chess.Color,
) -> List[Dict]:
    """
    Find user moves that reduce the opponent piece's escape squares.
    """
    if isinstance(target_square, str):
        target_square = chess.parse_square(target_square)

    reducers = []
    escape_sq_ints = [chess.parse_square(s) for s in escape_squares]

    if board.turn != user_color:
        return []

    for user_move in board.legal_moves:
        moving_piece = board.piece_at(user_move.from_square)
        if not moving_piece or moving_piece.piece_type == chess.KING:
            continue

        test_board = board.copy()
        test_board.push(user_move)

        # Count safe escapes after our move
        new_safe = _count_safe_escapes_quick(test_board, target_square, not user_color, user_color)

        # Which escape squares did we block?
        blocked_by_this = []
        for esc_sq in escape_sq_ints:
            # Check if this escape is still safe
            if not _is_safe_escape(test_board, target_square, esc_sq, not user_color, user_color):
                blocked_by_this.append(chess.square_name(esc_sq))

        if blocked_by_this:
            try:
                move_san = board.san(user_move)
            except Exception:
                move_san = user_move.uci()

            reducers.append({
                "move_uci": user_move.uci(),
                "move_san": move_san,
                "from": chess.square_name(user_move.from_square),
                "to": chess.square_name(user_move.to_square),
                "blocks_squares": blocked_by_this,
                "new_escape_count": new_safe,
            })

    reducers.sort(key=lambda r: r["new_escape_count"])
    return reducers[:5]


def find_forced_trap_sequence(
    board: chess.Board,
    target_square: int,
    escape_squares: List[str],
    reduction_moves: List[Dict],
    user_color: chess.Color
) -> List[str]:
    """
    Check if we can force a trap in 2 moves:
    1. We play a reducing move
    2. Opponent responds (best escape)
    3. We play another reducing move → 0 escapes

    Returns the sequence as SAN moves, or empty list.
    """
    if isinstance(target_square, str):
        target_square = chess.parse_square(target_square)

    if not reduction_moves:
        return []

    for reducer in reduction_moves[:3]:
        try:
            move1 = chess.Move.from_uci(reducer["move_uci"])
            if move1 not in board.legal_moves:
                continue

            board1 = board.copy()
            board1.push(move1)

            # Opponent's best response: move the trapped piece to its best escape
            piece_color = not user_color
            best_escape = None
            for esc_name in escape_squares:
                esc_sq = chess.parse_square(esc_name)
                if _is_safe_escape(board1, target_square, esc_sq, piece_color, user_color):
                    best_escape = esc_sq
                    break

            if best_escape is None:
                # Already trapped after move 1
                return [reducer["move_san"]]

            # Simulate opponent escaping
            escape_move = chess.Move(target_square, best_escape)
            board2 = board1.copy()
            if board2.turn != piece_color:
                fen_parts = board2.fen().split(' ')
                fen_parts[1] = 'w' if piece_color == chess.WHITE else 'b'
                try:
                    board2 = chess.Board(' '.join(fen_parts))
                except ValueError:
                    continue

            if escape_move not in board2.legal_moves:
                continue
            board2.push(escape_move)

            # Now find our second reducing move
            new_escapes = _get_piece_legal_moves(board2, best_escape, piece_color)
            new_safe = [sq for sq in new_escapes if _is_safe_escape(board2, best_escape, sq, piece_color, user_color)]

            if len(new_safe) <= 1:
                # Check if we can finish the trap
                for move2 in board2.legal_moves:
                    board3 = board2.copy()
                    board3.push(move2)
                    final_safe = _count_safe_escapes_quick(board3, best_escape, piece_color, user_color)
                    if final_safe == 0:
                        try:
                            move2_san = board2.san(move2)
                            return [reducer["move_san"], move2_san]
                        except Exception:
                            pass

        except Exception:
            continue

    return []


# ═══════════════════════════════════════════════════════════════════════
# COACHING MESSAGE + TRACKING (unchanged)
# ═══════════════════════════════════════════════════════════════════════

def generate_trap_coaching_message(trap: TrapOpportunity) -> str:
    """Generate a coaching message for a trap opportunity."""
    if trap.reason:
        return trap.reason

    piece = trap.target_piece
    sq = trap.target_square
    esc = trap.escape_count

    if esc == 0:
        if trap.is_attacked:
            return f"Trapped! Their {piece} on {sq} has nowhere to go. Capture it."
        return f"Their {piece} on {sq} is trapped — no safe squares. Find a way to attack it."

    if trap.is_trappable_in_2 and trap.trap_sequence:
        seq = " → ".join(trap.trap_sequence)
        return f"You can trap their {piece} in {len(trap.trap_sequence)} moves: {seq}."

    if esc == 1:
        escape_sq = trap.escape_squares[0] if trap.escape_squares else "?"
        if trap.reduction_moves:
            reducer = trap.reduction_moves[0]
            return f"Only 1 safe square left ({escape_sq}). {reducer['move_san']} removes it — the {piece} is yours."
        return f"Their {piece} has only 1 safe square: {escape_sq}. Control it and the {piece} is trapped."

    if esc == 2:
        squares = ", ".join(trap.escape_squares[:2])
        if trap.reduction_moves:
            reducer = trap.reduction_moves[0]
            return f"This {piece} has 2 safe squares: {squares}. {reducer['move_san']} blocks one."
        return f"Their {piece} has only 2 safe squares: {squares}. Can you block one?"

    squares = ", ".join(trap.escape_squares[:3])
    return f"Their {piece} has {esc} safe squares: {squares}. Can you reduce them?"


async def track_trap_opportunity(db, user_id: str, session_id: str, trap: TrapOpportunity):
    """Record that a trap opportunity was shown to the user."""
    try:
        from datetime import datetime, timezone
        await db.trap_tracking.insert_one({
            "user_id": user_id,
            "session_id": session_id,
            "target_piece": trap.target_piece,
            "target_square": trap.target_square,
            "escape_count": trap.escape_count,
            "trap_level": trap.trap_level,
            "classification": trap.classification,
            "is_trappable_in_2": trap.is_trappable_in_2,
            "was_exploited": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"Trap tracking insert failed: {e}")


async def mark_trap_exploited(db, user_id: str, session_id: str, target_square: str, exploited: bool):
    """Mark whether the user exploited a trap opportunity."""
    try:
        await db.trap_tracking.update_one(
            {"user_id": user_id, "session_id": session_id, "target_square": target_square, "was_exploited": None},
            {"$set": {"was_exploited": exploited}},
        )
    except Exception as e:
        logger.debug(f"Trap tracking update failed: {e}")


async def get_trap_stats(db, user_id: str) -> dict:
    """Get trap conversion rate for a user."""
    try:
        total = await db.trap_tracking.count_documents({"user_id": user_id})
        exploited = await db.trap_tracking.count_documents({"user_id": user_id, "was_exploited": True})
        missed = await db.trap_tracking.count_documents({"user_id": user_id, "was_exploited": False})

        return {
            "total_opportunities": total,
            "exploited": exploited,
            "missed": missed,
            "conversion_rate": round((exploited / max(total, 1)) * 100, 1),
            "pending": total - exploited - missed,
        }
    except Exception:
        return {"total_opportunities": 0, "exploited": 0, "missed": 0, "conversion_rate": 0, "pending": 0}
